#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
seedfinder.py —— 从一篇论文中找出"真正引发该研究"的 1-3 篇核心参考文献（种子文献）。

设计原则（重要，决定了为什么这么分层）：
  1. 纯分类器不可靠：Valenzuela et al. 2015 的 important/incidental 分类器
     只有 P=0.65 @ R=0.90；后续复现研究（arXiv:1707.04207）发现其 12 个特征中
     3 个不可复现、多个不具预测力。→ 规则/统计只用做**候选排序**，不做结论。
  2. "动机鸿沟"（MultiCite, NAACL 2022）：动机(Motivation)类引用很少完整表达在
     带引用标记的那一句话里，17.1% 的引用语境跨多句。→ 必须取 ±2 句窗口。
  3. 结论必须可核查：每条判定都要附**逐字原文 + 章节 + 页码**；证据不足必须弃权。

管线：
  citeparse.py (抽取) → seedfinder.py (排序+证据包) → LLM 裁决 (--llm 或手工粘贴)

用法：
    python seedfinder.py _testout                 # 排序 + 生成证据包与提示词
    python seedfinder.py _testout --top 8         # 证据包取前 8 名
    python seedfinder.py _testout --llm           # 额外调用 LLM 出最终 1-3 篇
    python seedfinder.py _testout --metadata      # 联网补全作者/题名/年份/出处

产出：
    seeds_ranked.csv        全部参考文献的启发强度打分（含各分量，可审计）
    seeds_ranked.md         同上，Markdown
    seeds_evidence_pack.md  前 N 名的完整原文证据（±2 句窗口）
    seeds_prompt.md         可直接粘贴给 LLM 的裁决提示词（已注入证据）
    seeds_llm.json/.md      --llm 时的最终裁决结果
"""
import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 章节归一

SEC_PATTERNS = [
    ("abstract",   r"abstract|摘要|概要"),
    ("motivation", r"motivation|研究动机|动机|问题提出"),
    ("intro",      r"^\s*1\b|introduction|background|引言|绪论|介绍|背景|概述"),
    ("related",    r"related work|related works|literature review|prior work|"
                   r"previous work|background and related|相关工作|文献综述|研究现状|已有工作"),
    ("method",     r"method|approach|model|framework|architecture|proposed|"
                   r"preliminar|notation|方法|模型|本文方法|预备知识|符号"),
    ("experiment", r"experiment|result|evaluation|setup|implementation|benchmark|"
                   r"ablation|实验|结果|评测|实现|设置"),
    ("discussion", r"discussion|analysis|limitation|讨论|分析|消融|局限性"),
    ("conclusion", r"conclusion|future work|summary|结论|总结|展望|结束语"),
]

# 章节基础权重：动机类章节高，实验章节低（实验多为数据集/基线数字）
SEC_BASE = {
    "abstract": 3.0, "motivation": 3.3, "intro": 2.8, "related": 2.0,
    "method": 1.6, "discussion": 1.3, "conclusion": 0.8,
    "experiment": 0.6, "other": 1.0,
}
SEC_CN = {
    "abstract": "摘要", "motivation": "研究动机", "intro": "引言", "related": "相关工作",
    "method": "方法", "discussion": "讨论", "conclusion": "结论",
    "experiment": "实验", "other": "其他",
}
# 强动机章节：只有出现在这些章节，"启发"才有可能成立
MOTIVATION_SECS = {"abstract", "motivation", "intro", "related"}


def norm_section(name: str) -> str:
    s = (name or "").strip().lower()
    for key, pat in SEC_PATTERNS:
        if re.search(pat, s):
            return key
    return "other"


# ---------------------------------------------------------------- 线索词

# 权重设计依据：GAP(揭示空白) 与 INSPIRE(直接说受其启发) 是最强的"引发研究"信号；
# OWN(本文主张) 与之同现，说明该参考文献处在论证链的关键位置。
CUES = [
    ("INSPIRE", 2.6, r"\b(motivated by|inspired by|inspire[sd]?|driven by|prompted by|"
                     r"stem(?:s|med)? from|spurred|take[s]? inspiration|draws? on|"
                     r"build(?:s|ing)? (?:on|upon)|built (?:on|upon)|extend(?:s|ing)?|"
                     r"our work is motivated|this work is motivated|the motivation for)\b|"
                     r"受.{0,10}(启发|激发|驱动)|启发|灵感|动机(来自|源于)|"
                     r"在.{0,12}基础上|借鉴|拓展|延伸|改进了|源于"),
    # 注意统一尾部 \b 的陷阱：写 \b(...|limitation|...)\b 时，\blimitation\b
    # **匹配不到 "limitations"**（词尾是复数 s，不构成词边界）。真实论文里几乎全是复数，
    # 因此所有名词/动词词干都要显式带上屈折后缀，否则线索静默失效。
    ("GAP", 3.0, r"\b(however|yet|unfortunately|whereas|"
                 r"to date|thus far|until now|"
                 r"only been (?:explored|studied|investigated|considered|applied|"
                 r"tested|examined|demonstrated|shown|validated)|"
                 r"(?:explored|studied|investigated|considered|applied|tested) only|"
                 r"(?:has|have) (?:only|rarely|seldom) been|"
                 r"restricted to|confined to|limited (?:to|by)|"
                 r"remains? (?:unclear|open|unexplored|unresolved|challenging|unknown|unaddressed|poorly)|"
                 r"open (?:questions?|problems?|challenges?)|"
                 r"little (?:work|attention|research|is known)|"
                 r"(?:has|have|receive[sd]?) (?:received )?less attention|"
                 r"not (?:been )?(?:well )?(?:explored|studied|addressed|understood|investigated|considered)|"
                 r"fail(?:s|ed|ing)? to|can(?:'?t|not)|unable to|lack(?:s|ed|ing)?|"
                 r"limited (?:to|by)|limitations?|drawbacks?|shortcomings?|suffer(?:s)? from|"
                 r"despite (?:the )?(?:success|progress|advances?|recent)|"
                 r"still (?:remains?|a challenge|an open|largely)|"
                 r"rarely|seldom|ignore[sd]?|overlook(?:s|ed)?)\b|"
                 r"然而|但(.{0,6})?(没有|未能|无法|缺乏|尚未|仍)|尚未|鲜有|少有|"
                 r"缺乏|不足|局限|缺陷|弊端|难以|空白|未解决|仍(是|为一个)(挑战|难题)|"
                 r"尽管.{0,12}(取得|成功)|被忽视|很少(有)?(人)?研究"),
    ("OWN", 2.2, r"\b(we propose|we present|we introduce|we address|we tackle|we aim|we seek|"
                 r"in this (?:paper|work|study|article)|"
                 r"our (?:methods?|approach(?:es)?|models?|frameworks?|goals?|aims?|"
                 r"objectives?|work|contributions?)|"
                 r"to (?:address|bridge|overcome|tackle) (?:this|these))\b|"
                 r"本文提出|我们提出|本文(针对|旨在|尝试)|我们的?(目标|目的|方法|模型)|"
                 r"为了(解决|克服|弥补)|针对这一"),
    ("USE", 1.6, r"\b(we (?:use|adopt|employ|apply|follow|leverage|utilize|build upon)|"
                 r"(?:uses|adopts|employs|applies|follows|leverages|utilizes)|"
                 r"based on|following (?:the )?(?:method|approach|work)|"
                 r"using the (?:method|approach|framework|architecture|model)|as in)\b|"
                 r"我们?(采用|使用|沿用|遵循)|基于.{0,10}(方法|模型|框架)|按照.{0,6}方法|采用.{0,6}方法"),
    ("FUTURE", 1.0, r"\b(future work|future directions?|interesting directions?|we leave|open up)\b|"
                    r"未来工作|后续研究|值得(进一步)?研究|留待"),
    ("BASELINE", 1.4, r"\b(baselines?|compare[sd]? (?:with|to|against)|comparisons?|"
                      r"state of the art|state-of-the-art|outperform(?:s|ed)?|competitive with|"
                      r"unlike|in contrast (?:to|with)|different from|as opposed to|"
                      r"contrary to|whereas)\b|"
                      r"基线|对比|相比|优于|不同于|与之相比|现有(最好|最佳)|当作基准"),
    # 负分：数据集/工具/代码/公开资源 —— 这是"使用"不是"启发"
    ("RESOURCE", -2.2, r"\b(datasets?|benchmark suite|corpora|corpus|toolbox|toolkit|"
                       r"libraries|library|packages?|codebase|code is available|"
                       r"publicly available|we evaluate on|downloaded from|software)\b|"
                       r"数据集|基准数据|语料库|工具包|工具箱|代码库|开源库|公开(数据|资源)"),
]

ROLE_BY_CUE = {
    "GAP": "揭示研究空白",
    "INSPIRE": "提出问题/提供灵感",
    "USE": "提供方法",
    "BASELINE": "作为对比基线",
    "OWN": "本文主张锚点",
    "FUTURE": "指向后续工作",
    "RESOURCE": "数据与资源",
}


def hit_cues(text: str):
    """返回 {线索名: 权重}（只保留命中的）"""
    out = {}
    for name, w, pat in CUES:
        if re.search(pat, text, flags=re.I):
            out[name] = w
    return out


# ---------------------------------------------------------------- 打分

def weighted_cues(target: str, near):
    """线索按距目标句的距离衰减。

    必要性：±2 句窗口是必需的（MultiCite 的"动机鸿沟"），但窗口越宽越容易把邻句的
    GAP/INSPIRE 语言错记到本引用头上（实测把谱图论教科书误判成"揭示研究空白"）。
    因此对非目标句命中的线索做衰减：±1 句 ×0.6，±2 句 ×0.3。
    """
    tot = {}
    for k, v in hit_cues(target).items():
        tot[k] = tot.get(k, 0) + v * 1.0
    for dist, text in near:
        f = 0.6 if dist <= 1 else 0.3
        for k, v in hit_cues(text).items():
            tot[k] = tot.get(k, 0) + v * f
    return {k: round(v, 2) for k, v in tot.items()}


def score_occurrence(ctx, target: str, near):
    """单次引用的启发强度。返回 (分数, 线索字典, 批量折扣系数)"""
    sec = norm_section(ctx.get("section", ""))
    base = SEC_BASE.get(sec, 1.0)
    cues = weighted_cues(target, near)
    cue_sum = sum(cues.values())
    cue_sum = max(-3.0, min(6.0, cue_sum))          # 限幅，避免堆叠

    n_co = len(ctx.get("co_refs", [])) + 1          # 本句共引数量
    if n_co >= 4:
        bulk = 0.35                                  # 批量罗列：强折扣
    elif n_co == 3:
        bulk = 0.60
    elif n_co == 2:
        bulk = 0.85
    else:
        bulk = 1.15                                  # 独占一句：加分

    score = (base + cue_sum) * bulk
    return round(score, 2), cues, bulk, hit_cues(target)


def build_windows(sents, ctxs):
    """为每个上下文取 ±2 句窗口（解决 MultiCite 指出的"动机鸿沟"）。

    返回 target（含引用标记的那一句）与 near=[(距离, 文本)]，
    供 weighted_cues 做距离衰减。
    """
    by_idx = {s["idx"]: s for s in sents}
    wins = []
    for c in ctxs:
        i = c.get("sent_idx")
        if i is None or i not in by_idx:
            wins.append({"ctx": c, "window": c.get("sentence", ""), "idx": i,
                         "target": c.get("sentence", ""), "near": []})
            continue
        lo, hi = max(0, i - 2), min(len(sents) - 1, i + 2)
        parts, near = [], []
        for k in range(lo, hi + 1):
            t = by_idx[k]["text"]
            parts.append(("[>>] " if k == i else "     ") + t)
            if k != i:
                near.append((abs(k - i), t))
        wins.append({"ctx": c, "window": "\n".join(parts), "idx": i,
                     "target": by_idx[i]["text"], "near": near})
    return wins


def rank_refs(nodes, ctxs, sents):
    wins = build_windows(sents, ctxs)
    refs = {}
    for n in nodes:
        refs[n["id"]] = {"meta": n, "occ": []}

    for w in wins:
        c = w["ctx"]
        rid = c.get("ref_id")
        if rid not in refs:
            continue
        sc, cues, bulk, tcues = score_occurrence(c, w["target"], w["near"])
        refs[rid]["occ"].append({
            "score": sc, "cues": cues, "bulk": bulk, "tcues": tcues,
            "section": norm_section(c.get("section", "")),
            "section_raw": c.get("section", ""),
            "page": c.get("page", ""),
            "sentence": c.get("sentence", ""),
            "window": w["window"],
            "n_co": len(c.get("co_refs", [])) + 1,
        })

    results = []
    for rid, bundle in refs.items():
        occ = sorted(bundle["occ"], key=lambda o: -o["score"])
        if not occ:
            continue
        meta = bundle["meta"]
        secs = {o["section"] for o in occ}
        top = occ[:3]
        score = (top[0]["score"] * 1.0
                 + sum(o["score"] for o in top[1:]) * 0.55
                 + min(len(occ), 6) * 0.35)
        if {"abstract", "intro"} <= secs or {"abstract", "motivation"} <= secs:
            score += 1.0                                   # 摘要与引言双现
        if len(secs) >= 3:
            score += 0.8                                   # 跨章节反复出现

        # ---- 角色判定：由命中的线索加权决定主/次角色
        # 只用驱动分数的前 3 次出现定角色：否则一次偶然的邻句泄漏会盖过全部正面证据
        cue_tot = {}
        for o in occ[:3]:
            for k, v in o["cues"].items():
                cue_tot[k] = cue_tot.get(k, 0) + v * o["bulk"]
        cue_tot = {k: round(v, 2) for k, v in cue_tot.items()}
        role_items = sorted(
            [(k, v) for k, v in cue_tot.items() if k != "RESOURCE" and v > 0],
            key=lambda kv: -kv[1])
        primary = ROLE_BY_CUE.get(role_items[0][0], "未分类") if role_items else "未分类"
        secondary = ROLE_BY_CUE.get(role_items[1][0], "") if len(role_items) > 1 else ""
        # 诚实性修正 1：资源性引用优先判为"数据与资源"，防止邻句泄漏的 GAP 抢走角色
        pos_max = max([v for k, v in cue_tot.items() if k != "RESOURCE" and v > 0], default=0.0)
        if cue_tot.get("RESOURCE", 0) <= -1.5 and abs(cue_tot["RESOURCE"]) >= pos_max:
            primary = "数据与资源"
            secondary = ROLE_BY_CUE.get(role_items[0][0], "") if role_items else ""
        # 诚实性修正 2：若所有线索都来自邻句（本句无命中），角色不可信
        elif not any(o.get("tcues") for o in occ):
            primary, secondary = "背景罗列（本句无动机线索）", ""

        # ---- 排除规则（次要文献：仅背景罗列 / 仅数据集 / 仅实验数字）
        reasons = []
        strong = {"GAP", "INSPIRE", "OWN", "USE"}
        has_strong = any(strong & set(o["cues"]) for o in occ)
        if not secs & MOTIVATION_SECS and not has_strong:
            reasons.append("未出现在摘要/引言/相关工作，且无动机类线索")
        if all(o["bulk"] <= 0.35 for o in occ):
            reasons.append("全部出现在批量罗列句中（一句≥4篇）")
        if cue_tot.get("RESOURCE", 0) < -2 and not ({"GAP", "INSPIRE"} & set(cue_tot)):
            reasons.append("主要为数据集/工具/资源性引用")
        if len(occ) == 1 and occ[0]["section"] == "experiment":
            reasons.append("全文仅出现1次且位于实验章节")
        excluded = len(reasons) > 0 and score < 12

        # ---- 把握程度
        n_strong = sum(1 for o in occ if {"GAP", "INSPIRE"} & set(o["cues"]) and o["score"] >= 3)
        meta_ok = bool(meta.get("title")) and bool(meta.get("authors"))
        if n_strong >= 1 and len(secs) >= 2 and meta_ok:
            conf = "高"
        elif n_strong >= 1 or (len(secs) >= 2 and score >= 8) or score >= 10:
            conf = "中"
        else:
            conf = "低"

        # ---- 缺失信息（用于明确说明"证据不足"）
        miss = []
        if not meta_ok:
            miss.append("参考文献条目缺作者/题名（用 --refs 提供 BibTeX 或 --metadata 联网补全）")
        if not secs & MOTIVATION_SECS:
            miss.append("未识别到引言/摘要章节，动机类证据可能整体缺失（检查 PDF 是否为扫描件）")
        if len(occ) == 1:
            miss.append("全文仅 1 处引用，无法判断启发强度")
        if n_strong == 0:
            miss.append("无 GAP/INSPIRE 线索命中，需人工回看原文确认是否为隐性启发")
        if not any(o.get("tcues") for o in occ):
            miss.append("引用本句无任何动机线索（现有线索全部来自邻句），极可能是批量罗列")

        results.append({
            "ref_id": rid, "score": round(score, 2),
            "authors": meta.get("authors", ""), "title": meta.get("title", "") or meta.get("raw", ""),
            "year": meta.get("year", ""), "venue": meta.get("venue", ""),
            "count": len(occ), "sections": sorted(secs),
            "primary_role": primary, "secondary_role": secondary,
            "confidence": conf, "excluded": excluded, "exclude_reasons": reasons,
            "missing": miss, "occ": occ, "cue_tot": cue_tot,
        })

    results.sort(key=lambda r: (-r["score"], r["ref_id"]))
    return results, wins


# ---------------------------------------------------------------- 元数据补全

def enrich_metadata(results, limit=20):
    """Crossref（免 key）优先，OpenAlex（需 OPENALEX_API_KEY）兜底。"""
    try:
        import requests
    except ImportError:
        print("[meta] 未装 requests，跳过")
        return 0
    sess = requests.Session()
    sess.headers.update({"User-Agent": "seedfinder/1.0 (mailto:local@example.com)"})
    key = os.environ.get("OPENALEX_API_KEY")

    done = 0
    for r in results[:limit]:
        if r["authors"] and r["venue"] and r["year"]:
            continue
        q = (r["title"] or "").strip()
        if len(q) < 8:
            continue
        got = None
        try:
            resp = sess.get("https://api.crossref.org/works",
                            params={"query.bibliographic": q[:180], "rows": 1}, timeout=20)
            if resp.status_code == 200:
                items = resp.json().get("message", {}).get("items", [])
                if items:
                    it = items[0]
                    got = {
                        "title": (it.get("title") or [""])[0],
                        "authors": ", ".join(
                            f"{a.get('given','')} {a.get('family','')}".strip()
                            for a in it.get("author", [])[:6]),
                        "venue": (it.get("container-title") or [""])[0],
                        "year": str(it.get("issued", {}).get("date-parts", [[None]])[0][0] or ""),
                        "doi": it.get("DOI", ""),
                    }
        except Exception:
            pass
        if not got and key:
            try:
                resp = sess.get("https://api.openalex.org/works",
                                params={"filter": f"title.search:{q[:120]}", "per-page": 1},
                                headers={"Authorization": f"Bearer {key}"}, timeout=20)
                if resp.status_code == 200:
                    d = (resp.json().get("results") or [None])[0]
                    if d:
                        got = {
                            "title": d.get("title", ""),
                            "authors": ", ".join(
                                a["author"]["display_name"]
                                for a in d.get("authorships", [])[:6]),
                            "venue": ((d.get("primary_location") or {}).get("source") or {}).get("display_name", ""),
                            "year": str(d.get("publication_year", "")),
                            "doi": (d.get("doi") or "").replace("https://doi.org/", ""),
                        }
            except Exception:
                pass
        if got:
            for k, v in got.items():
                if v and not r.get(k):
                    r[k] = v
            done += 1
    print(f"[meta] 补全 {done} 条元数据")
    return done


# ---------------------------------------------------------------- 提示词

PROMPT_TMPL = """你是一位严格的情报分析员。任务：从下面这篇论文的引用中，找出**真正引发该研究**的 1-3 篇核心参考文献（种子文献），排除仅作背景罗列或批量引用的次要文献。

## 判定标准（"启发"的定义）
一篇参考文献只有在满足下列至少一条时才算"引发该研究"：
- A. 提出问题：它提出了本文要解决的那个具体问题/猜想/矛盾。
- B. 揭示空白：本文明确指出它的局限、失败模式或未覆盖的情形，并以此为出发点。
- C. 提供方法：本文的方法是在它的框架/算法上直接改造或扩展。
- D. 作为对比基线：它是本文最主要的比较对象，本文的贡献以超越它来定义。

**不算**启发：仅在引言成组罗列（如"深度学习已广泛用于[X,Y,Z]"）、仅作为数据集/工具/代码库来源、仅在实验表格中出现作数字对比、教科书式通用背景。

## 铁律
1. 每条结论**必须附逐字原文引用**（不得改写、不得概括），并标明章节与页码。
2. 只使用下面【证据】中提供的原文。若某条结论找不到原文支撑，就不要下那条结论。
3. 若整体证据不足，**必须输出 `insufficient: true`** 并在 `missing_information` 中说明缺什么——宁可弃权，不得编造。
4. 排序按启发强度（A/B > C > D），不是按引用次数。
5. 每篇给出把握程度：高 / 中 / 低，并说明升降理由。

## 输出格式（严格 JSON，不要 markdown 代码块以外的任何文字）
{
  "insufficient": false,
  "seeds": [
    {
      "rank": 1,
      "ref_id": 0,
      "authors": "",
      "title": "",
      "year": "",
      "venue": "",
      "role": "提出问题|提供方法|作为对比基线|揭示研究空白",
      "impact": "一句话说明它如何影响本文",
      "evidence": [
        {"section": "", "page": "", "quote": "逐字原文", "why": "这句为什么说明启发作用"}
      ],
      "confidence": "高|中|低",
      "confidence_reason": ""
    }
  ],
  "runners_up": [{"ref_id": 0, "why_not": "为什么降级"}],
  "excluded_examples": [{"ref_id": 0, "reason": "为什么排除"}],
  "missing_information": []
}

## 论文元信息
- 文件：__PDF__
- 引用标记类型：__STYLE__
- 参考文献总数：__NREFS__，抽取到引用上下文：__NCTX__ 条

## 证据（按机器打分排序的前 __TOP__ 名；[>>] 标记的是含该引用的句子，其余为上下文）
__EVIDENCE__
"""


def render_evidence(results, top):
    blocks = []
    for r in results[:top]:
        head = (f"\n### [{r['ref_id']}] 机器分 {r['score']} | 出现 {r['count']} 次 | "
                f"章节 {','.join(SEC_CN.get(s, s) for s in r['sections'])} | "
                f"角色 {r['primary_role']}"
                + (f"/{r['secondary_role']}" if r['secondary_role'] else "")
                + (f" | 疑似次要：{'; '.join(r['exclude_reasons'])}" if r["excluded"] else ""))
        head += f"\n- 题名：{r['title'][:160]}\n- 作者：{r['authors']}　年份：{r['year']}　出处：{r['venue']}"
        if r["missing"]:
            head += "\n- ⚠ 缺失信息：" + "；".join(r["missing"])
        blocks.append(head)
        for i, o in enumerate(r["occ"][:4], 1):
            cues = ",".join(f"{k}{v:+g}" for k, v in sorted(o["cues"].items(), key=lambda kv: -kv[1]))
            blocks.append(
                f"\n**证据 {r['ref_id']}-{i}**　章节={o['section_raw']}　页={o['page']}　"
                f"本节共引={o['n_co']}　线索={cues or '无'}\n```\n{o['window']}\n```")
    return "\n".join(blocks)


# ---------------------------------------------------------------- LLM 调用

def call_llm(prompt):
    import urllib.request
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        print("[llm] 未设置 LLM_API_KEY / OPENAI_API_KEY，已改为只生成提示词")
        return None
    base = (os.environ.get("LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a rigorous scientific evidence analyst. "
                                          "Answer with strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[llm] 调用失败：{e}")
        return None


# ---------------------------------------------------------------- 输出

def write_outputs(out_dir, results, wins, args, sents):
    # CSV
    csv_path = out_dir / "seeds_ranked.csv"
    cols = ["ref_id", "score", "作者", "题名", "年份", "出处", "出现次数", "出现章节",
            "主角色", "次角色", "把握程度", "疑似次要", "排除理由", "缺失信息",
            "最强证据原文", "最强证据章节", "最强证据页码"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in results:
            o = r["occ"][0] if r["occ"] else {}
            w.writerow([
                r["ref_id"], r["score"], r["authors"], r["title"][:200], r["year"], r["venue"],
                r["count"], ",".join(SEC_CN.get(s, s) for s in r["sections"]),
                r["primary_role"], r["secondary_role"], r["confidence"],
                "是" if r["excluded"] else "", "；".join(r["exclude_reasons"]),
                "；".join(r["missing"]),
                (o.get("sentence") or "")[:300], o.get("section_raw", ""), o.get("page", ""),
            ])
    print(f"[out] {csv_path}")

    # Markdown 排行
    md = ["# 种子候选：启发强度排序\n",
          "> 分数是**检索排序**用的人工可审计启发式，不是结论。"
          "最终 1-3 篇必须用 `seeds_prompt.md` 交给 LLM（或人工）依据原文裁决。\n",
          "| 排名 | ref | 分数 | 作者 | 题名 | 年份 | 次数 | 章节 | 角色 | 把握 | 次要? |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results[:30], 1):
        md.append(f"| {i} | {r['ref_id']} | {r['score']} | {r['authors'][:24]} | "
                  f"{(r['title'] or '')[:52]} | {r['year']} | {r['count']} | "
                  f"{','.join(SEC_CN.get(s, s) for s in r['sections'])} | "
                  f"{r['primary_role']} | {r['confidence']} | {'⚠' if r['excluded'] else ''} |")
    (out_dir / "seeds_ranked.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[out] {out_dir/'seeds_ranked.md'}")

    # 证据包
    (out_dir / "seeds_evidence_pack.md").write_text(
        "# 种子候选证据包（±2 句窗口）\n\n> 动机(Motivation)类引用很少完整表达在带标记的那一句里"
        "（MultiCite, NAACL 2022），因此每条证据都给出前后各 2 句。`[>>]` 为含引用标记的句子。\n"
        + render_evidence(results, args.top), encoding="utf-8")
    print(f"[out] {out_dir/'seeds_evidence_pack.md'}")

    # 提示词
    meta = {}
    if (out_dir / "meta.json").exists():
        meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    prompt = (PROMPT_TMPL
              .replace("__PDF__", str(meta.get("pdf", "?")))
              .replace("__STYLE__", str(meta.get("style", "?")))
              .replace("__NREFS__", str(len(results)))
              .replace("__NCTX__", str(len(wins)))
              .replace("__TOP__", str(args.top))
              .replace("__EVIDENCE__", render_evidence(results, args.top)))
    (out_dir / "seeds_prompt.md").write_text(prompt, encoding="utf-8")
    print(f"[out] {out_dir/'seeds_prompt.md'}")


def main():
    ap = argparse.ArgumentParser(description="找出真正引发该研究的核心参考文献")
    ap.add_argument("out_dir", help="citeparse.py 的输出目录")
    ap.add_argument("--top", type=int, default=8, help="证据包/提示词取前 N 名（默认 8）")
    ap.add_argument("--metadata", action="store_true", help="联网补全作者/题名/年份/出处")
    ap.add_argument("--llm", action="store_true", help="调用 LLM 出最终 1-3 篇")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    for fn in ("contexts.json", "refs_nodes.json"):
        if not (out_dir / fn).exists():
            sys.exit(f"[err] 缺少 {out_dir/fn}，请先运行 citeparse.py")
    ctxs = json.loads((out_dir / "contexts.json").read_text(encoding="utf-8"))
    nodes = json.loads((out_dir / "refs_nodes.json").read_text(encoding="utf-8"))
    sents = []
    if (out_dir / "sentences.json").exists():
        sents = json.loads((out_dir / "sentences.json").read_text(encoding="utf-8"))
    else:
        print("[warn] 无 sentences.json（旧版 citeparse 产出），窗口退化为单句。"
              "请重跑 citeparse.py 以获得跨句动机语境。")

    print(f"[in] 参考文献 {len(nodes)} 篇，引用上下文 {len(ctxs)} 条，全文句子 {len(sents)} 句")
    results, wins = rank_refs(nodes, ctxs, sents)

    if args.metadata:
        enrich_metadata(results)

    write_outputs(out_dir, results, wins, args, sents)

    top_clean = [r for r in results if not r["excluded"]][:5]
    print("\n=== 机器排序 Top5（未过滤次要） ===")
    for i, r in enumerate(results[:5], 1):
        print(f"{i}. [{r['ref_id']}] {r['score']:>5} | {r['primary_role']:<8} | "
              f"{r['confidence']} | {(r['title'] or r['authors'])[:56]}")
    print(f"\n剔除次要后候选：{[r['ref_id'] for r in top_clean]}")

    if args.llm:
        prompt = (out_dir / "seeds_prompt.md").read_text(encoding="utf-8")
        raw = call_llm(prompt)
        if raw:
            (out_dir / "seeds_llm_raw.txt").write_text(raw, encoding="utf-8")
            m = re.search(r"\{.*\}", raw, flags=re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                    (out_dir / "seeds_llm.json").write_text(
                        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    lines = ["# 核心参考文献（LLM 裁决）\n"]
                    if data.get("insufficient"):
                        lines.append("> ⚠ 模型判定：**证据不足**。\n")
                    for s in data.get("seeds", []):
                        lines.append(f"\n## {s.get('rank')}. {s.get('title','')} "
                                     f"（{s.get('year','')}）")
                        lines.append(f"- 作者：{s.get('authors','')}")
                        lines.append(f"- 出处：{s.get('venue','')}")
                        lines.append(f"- 角色：{s.get('role','')}")
                        lines.append(f"- 影响：{s.get('impact','')}")
                        lines.append(f"- 把握程度：{s.get('confidence','')}（{s.get('confidence_reason','')}）")
                        for e in s.get("evidence", []):
                            lines.append(f"  - 原文（{e.get('section','')} p.{e.get('page','')}）："
                                         f"“{e.get('quote','')}”")
                            lines.append(f"    → {e.get('why','')}")
                    if data.get("missing_information"):
                        lines.append("\n## 缺失的关键信息\n")
                        for x in data["missing_information"]:
                            lines.append(f"- {x}")
                    (out_dir / "seeds_llm.md").write_text("\n".join(lines), encoding="utf-8")
                    print(f"[out] {out_dir/'seeds_llm.md'}")
                except Exception as e:
                    print(f"[llm] JSON 解析失败：{e}；原始输出见 seeds_llm_raw.txt")


if __name__ == "__main__":
    main()
