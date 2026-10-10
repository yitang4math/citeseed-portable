#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键驱动：把 SOP v1 的 S1(体检) / S2(制式) / S3(抽取) / S4(闸口) / S5(排序) / S6(复核)
折叠为**一次调用**，并只输出精简报告（目标 < 5k 字符）。

用法：
    python autorun.py <PDF> --out <OUT> [--expect N] [--refs F] [--style S] [--appendix] [--top 8]

设计原则（降本）：
  1. 中间产物全部落盘，不进上下文；
  2. 只把「判据结论 + Top N 精简行 + 最强证据句（截断）」打印出来；
  3. 判据不通过时，打印**该做什么**而不是原始数据。
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sh(args):
    p = subprocess.run([PY] + args, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    return (p.stdout or "") + (p.stderr or "")


def clip(s, n):
    s = re.sub(r"\s+", " ", (s or "")).strip()
    return s[:n] + ("…" if len(s) > n else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect", type=int, default=0, help="人工目测的参考文献总数（P5）")
    ap.add_argument("--refs", default=None)
    ap.add_argument("--style", default=None)
    ap.add_argument("--appendix", action="store_true")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--evlen", type=int, default=150, help="证据句截断长度")
    ap.add_argument("--force", action="store_true",
                    help="闸口未通过仍继续（仅用于已按异常表评估风险后的场景）")
    a = ap.parse_args()

    out = []
    def P(s=""):
        # 实时打印：中途崩溃时 stdout 仍保留已完成的步骤（批量模式靠它诊断）。
        # 曾踩坑：P 只累积、末尾统一 print，一篇崩溃就整份输出丢失，
        # 汇总行全空而闸口因默认值被误判 OK。
        out.append(s)
        print(s)

    # ---------- S1 体检 + S2 制式 ----------
    import pymupdf
    d = pymupdf.open(a.pdf)
    npage = len(d)
    p0 = len(d[0].get_text("text"))
    body = "".join(pg.get_text("text") for pg in d)
    # 制式判据与 citeparse.py 保持一致（直接复用它的函数，避免两处实现漂移）：
    #   括号数字必须打得过作者-年，且编号形状不像公式编号（1..max 被用满 = 公式）
    from citeparse import paren_nums, looks_like_eq_numbering
    nums = paren_nums(body[:60000])
    np_ = len(nums)
    nn = len(re.findall(r"\[\d{1,3}\]", body[:60000]))
    na = len(re.findall(r"et al\.\s*\(\d{4}\)|\(\s*[A-Za-z]+[^)]{0,60}(?:19|20)\d{2}\s*\)", body[:60000]))
    # 方括号 [n] 是明确信号，优先；只有它缺席时才考虑括号数字。
    # （数学稿的公式编号 "(1)" 会大量命中括号数字，必须先让 [n] 压过它）
    if nn >= 5 or nn >= max(np_, na):
        style_guess = "numeric"
    elif np_ >= 5 and np_ > na and not looks_like_eq_numbering(nums):
        style_guess = "paren"
    else:
        style_guess = "authoryear"
    ok_text = "OK" if p0 >= 300 else "FAIL(疑似扫描件,先OCR)"
    P(f"[S1] pages={npage} 首页字符={p0} 文本层={ok_text}")
    P(f"[S2] numeric={nn} authoryear={na} → 推测制式={style_guess}")
    if ok_text.startswith("FAIL"):
        print("\n".join(out)); return

    # ---------- S3 抽取 ----------
    args = ["citeparse.py", a.pdf, "--out", a.out]
    if a.refs: args += ["--refs", a.refs]
    if a.style: args += ["--style", a.style]
    if a.appendix: args += ["--appendix"]
    sh(args)

    try:
        meta = json.load(open(os.path.join(HERE, a.out, "meta.json"), encoding="utf-8"))
        refs = json.load(open(os.path.join(HERE, a.out, "refs_nodes.json"), encoding="utf-8"))
        ctxs = json.load(open(os.path.join(HERE, a.out, "contexts.json"), encoding="utf-8"))
    except Exception as e:
        P(f"[FATAL] 抽取失败: {e}")
        print("\n".join(out)); return

    n_refs, n_ctx = meta["n_refs"], meta["n_ctx"]
    covered = len({c["ref_id"] for c in ctxs})
    secs = collections.Counter(c["section"] for c in ctxs)

    # ---------- S4 闸口 ----------
    def intro_ok():
        return any(re.search(r"INTRODUCT|引言|I\.\s", s, re.I) for s in secs)
    def rw_ok():
        return any(re.search(r"RELATED|BACKGROUND|相关工作|背景", s, re.I) for s in secs)
    top_sec, top_n = (secs.most_common(1)[0] if secs else ("-", 0))
    c1 = ("SKIP(未提供--expect)" if not a.expect
          else ("OK" if abs(n_refs - a.expect) <= 2 else f"FAIL(解析{n_refs} vs 基线{a.expect})"))
    c2 = "OK" if covered >= 0.5 * max(n_refs, 1) else f"FAIL(覆盖{covered}/{n_refs}<50%)"
    # 短文（书目 <25 条）引用密度天然偏低，1.2× 会把正常稿判死；这里降到 1.0×
    ratio = 1.0 if n_refs < 25 else 1.2
    c3 = "OK" if n_ctx >= ratio * n_refs else f"FAIL(ctx={n_ctx}<{ratio}×{n_refs})"
    # Science/Nature/数学稿常没有独立的 Related Work 章节（引言兼做相关工作），
    # 因此"引言 或 相关工作"有其一即可，不再要求两者齐备。
    c4 = "OK" if (len(secs) >= 3 and top_n < 0.8 * max(n_ctx, 1)
                  and (intro_ok() or rw_ok())) \
        else f"FAIL(章节{len(secs)} 引言{'✓' if intro_ok() else '✗'} 相关工作{'✓' if rw_ok() else '✗'} 最大占比{top_n}/{n_ctx})"
    c5 = "OK" if meta["style"] == style_guess else f"WARN(脚本判定={meta['style']})"
    bad_year = sum(1 for r in refs if not r.get("year"))
    c6 = "OK" if bad_year < 0.1 * max(len(refs), 1) else f"WARN(缺年份{bad_year}/{len(refs)})"
    fails = [k for k, v in [("C1", c1), ("C2", c2), ("C3", c3), ("C4", c4), ("C5", c5), ("C6", c6)]
             if v.startswith(("FAIL", "FATAL"))]
    P(f"[S3] refs={n_refs} ctx={n_ctx} 被引={covered}")
    P(f"[S4] C1={c1} | C2={c2} | C3={c3}")
    P(f"     C4={c4}")
    P(f"     C5={c5} | C6={c6}")
    if fails:
        P(f"[!!] 未通过 {','.join(fails)} → 建议先按异常表处理（常见：--refs 提供外部书目 / --style 显式指定）")
        if not a.force:
            return
        P("[!!] --force 已开启：带缺陷继续，结论把握程度需整体下调一档")

    # ---------- S5 排序 + S6 复核 ----------
    sh(["seedfinder.py", a.out, "--top", str(a.top)])
    rows = list(csv.DictReader(open(os.path.join(HERE, a.out, "seeds_ranked.csv"),
                                    encoding="utf-8-sig")))
    if not rows:
        # 抽取为空（书目/上下文 0 条）时不要崩：要明确报 FATAL，让批量模式能把它
        # 标成失败而非静默通过。实测 arxiv 批里约 10% 的稿会走到这里。
        P(f"[FATAL] 无候选（refs={n_refs} ctx={n_ctx}）：本篇抽取失败，"
          f"请用 citeparse.py 分步排查版式，或提供 --refs 外部书目")
        return
    i4 = min(3, len(rows) - 1)
    ratio = float(rows[0]["score"]) / max(float(rows[i4]["score"]), 1e-9)
    verdict = "排序可用于定序" if ratio >= 2.0 else "排序仅用于圈定候选，必须人工裁决"
    P(f"[S6] Top1/第4名={ratio:.2f} → {verdict}")
    P(f"[TOP{len(rows)}]")
    for i, r in enumerate(rows[:a.top], 1):
        flag = "次要" if r["疑似次要"] == "是" else "    "
        P(f" {i:>2}.[{r['ref_id']:>2}] {float(r['score']):>6} {r['把握程度']:<2} "
          f"{r['主角色']:<14}{flag} 次{r['出现次数']:>2} {clip(r['题名'], 42)}")
    P("[EV ] 最强证据（逐字，供人工回查）")
    for i, r in enumerate(rows[:min(a.top, 8)], 1):
        P(f" {i:>2}.[{r['ref_id']:>2}] §{r['最强证据章节']} p.{r['最强证据页码']} :: "
          f"{clip(r['最强证据原文'], a.evlen)}")
    P("[NEXT] 下一步：对 Top3 逐条回 PDF 原文核实；凑不满 3 篇就交 1-2 篇并写明缺失信息。")

    print(f"\n[report bytes = {len(chr(10).join(out).encode('utf-8'))}]")


if __name__ == "__main__":
    main()
