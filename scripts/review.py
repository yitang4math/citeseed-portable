#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把一批论文的候选与证据压缩成「裁决工作台」，供 agent 连续做 A3 裁决。

为什么需要它
------------
`batchrun.py` 每篇都产出了完整的 `seeds_evidence_pack.md`，但那是 ±2 句全量窗口——
一篇几千字，几十篇直接把上下文撑爆，没法逐篇裁决。

本脚本把每篇压到 ~25 行：Top-N 候选 + 每条 1–3 句最强证据 + 题目/闸口/比值。
**10 篇约 250 行 ≈ 4k token**，可以一口气读完并逐篇下结论。

用法
----
    python review.py <BATCH_OUT>                 # 默认每篇取 Top3
    python review.py <BATCH_OUT> --top 5         # 拿不准时看更多候选
    python review.py <BATCH_OUT> --only 001,003  # 只看指定篇（按目录名前缀）

输出 `<BATCH_OUT>/review_digest.md`。

设计约束
--------
- **题录一律取 `refs_nodes.json` 的 `raw`**（R15）。`seeds_ranked.csv` 的「题名」列会退化。
- 证据只取 `[>>]` 目标句 + 前后各 1 句，且裁剪长度——够判断"缺陷属于谁"即可（R17/R18）。
- 每篇都带 PDF 绝对路径 + 产物目录，方便按需回原文深挖。
"""
import argparse
import csv
import json
import os
import re
import sys

CLIP = 190          # 单句裁剪长度
EACH = 3            # 每条证据最多保留几句（前1 + 目标 + 后1）


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_meta(d):
    try:
        return json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    except Exception:
        return {}


def load_raw(d):
    """id -> raw 题录（R15：题录只信 raw）。"""
    try:
        nodes = json.load(open(os.path.join(d, "refs_nodes.json"), encoding="utf-8"))
        return {str(n.get("id")): (n.get("raw") or n.get("label") or "") for n in nodes}
    except Exception:
        return {}


def load_evidence(d):
    """ref_id -> [(章节, 页, [句子...]), ...]  取自 evidence_pack 的 [>>] 窗口。"""
    p = os.path.join(d, "seeds_evidence_pack.md")
    if not os.path.exists(p):
        return {}
    txt = open(p, encoding="utf-8").read()
    out = {}
    blocks = re.split(r"\n### ", txt)
    for b in blocks[1:]:
        m = re.match(r"\[(\d+)\]", b)
        if not m:
            continue
        rid = m.group(1)
        items = []
        # 章节名可能含空格（实测到 `章节=20 Introduction`），故用非贪婪 .*? 吃到「页=」为止
        for em in re.finditer(
                r"\*\*证据 ([\d\-]+)\*\*\s*章节=(.*?)\s*页=(\d+)[^\n]*\n```\n(.*?)\n```",
                b, re.S):
            lines = [ln.strip() for ln in em.group(4).split("\n") if ln.strip()]
            tgt = next((i for i, ln in enumerate(lines) if ln.startswith("[>>]")), None)
            if tgt is None:
                continue
            keep = lines[max(0, tgt - 1): tgt + 2][:EACH]
            keep = [re.sub(r"^\[>>\]\s*", "▶ ", ln)[:CLIP] for ln in keep]
            items.append((em.group(2), em.group(3), keep))
        out[rid] = items[:2]        # 每篇每候选最多 2 条证据
    return out


def main():
    ap = argparse.ArgumentParser(description="生成批量裁决工作台")
    ap.add_argument("batch_out", help="batchrun.py 的输出目录")
    ap.add_argument("--top", type=int, default=3, help="每篇取几个候选（默认 3）")
    ap.add_argument("--only", help="只看指定篇，逗号分隔（目录名前缀）")
    ap.add_argument("--range", dest="rng",
                    help="按序号范围分批，如 1-12 / 13-24（目录名前缀的序号）")
    a = ap.parse_args()

    root = os.path.abspath(a.batch_out)
    csv_path = os.path.join(root, "batch_summary.csv")
    if not os.path.exists(csv_path):
        sys.exit(f"[!!] 找不到 {csv_path} —— 先跑 batchrun.py")

    rows = read_csv(csv_path)
    index = {r["name"]: r for r in rows}
    keys = [k.strip() for k in a.only.split(",")] if a.only else None

    subs = sorted(d for d in os.listdir(root)
                  if os.path.isdir(os.path.join(root, d))
                  and os.path.exists(os.path.join(root, d, "seeds_ranked.csv")))
    if keys:
        subs = [d for d in subs if any(d.startswith(k) for k in keys)]
    if a.rng:
        m = re.match(r"\s*(\d+)\s*[-–]\s*(\d+)\s*$", a.rng)
        if not m:
            sys.exit("[!!] --range 格式应为 1-12")
        lo, hi = int(m.group(1)), int(m.group(2))
        def _idx(name):
            mm = re.match(r"(\d+)", name)
            return int(mm.group(1)) if mm else -1
        subs = [d for d in subs if lo <= _idx(d) <= hi]

    md = [f"# 裁决工作台（{len(subs)} 篇）", "",
          "> 每篇给 Top-N 候选与最强证据句，供逐篇做 A3 裁决。",
          "> **题录取自 `raw`（R15，可信）**；证据句已裁剪，需要完整 ±2 句窗口时",
          "> 读对应篇的 `seeds_evidence_pack.md`。",
          "> 对机器 Top1 必问两句：① 这些缺陷是本文要解决的，还是本文继承的动机？（R18）",
          "> ② 它是数据集/基准类文献吗？看它在不在本文贡献列表里。（R17）", ""]

    for d in subs:
        sd = os.path.join(root, d)
        row = index.get(d, {})
        meta = load_meta(sd)
        raws = load_raw(sd)
        ev = load_evidence(sd)
        ranked = read_csv(os.path.join(sd, "seeds_ranked.csv"))

        gate = row.get("闸口", "")
        ratio = row.get("比值", "")
        md.append(f"## {d}")
        md.append("")
        md.append(f"- **PDF**：`{row.get('PDF','')}`")
        md.append(f"- **书目** {row.get('refs','') or meta.get('n_refs','')}　"
                  f"**上下文** {row.get('ctx','') or meta.get('n_contexts','')}　"
                  f"**制式** {row.get('制式','') or meta.get('style','')}　"
                  f"**闸口** {gate}　**Top1/第4名** {ratio}")
        if ratio:
            try:
                if float(ratio) < 2.0:
                    md.append("- ⚠️ 比值 <2.0：**排序只圈候选，必须逐条裁决**")
                else:
                    md.append("- ✅ 比值 ≥2.0：排序可定序，快速核一遍即可")
            except ValueError:
                pass
        md.append("")

        for i, r in enumerate(ranked[:a.top], 1):
            rid = str(r.get("ref_id", "")).strip()
            raw = re.sub(r"\s+", " ", raws.get(rid, ""))
            md.append(f"**{i}. [{rid}]　{r.get('score','')}　"
                      f"{r.get('主角色','')}　次 {r.get('出现次数','')}**")
            md.append(f"  - {raw[:230]}")
            for sec, pg, sents in ev.get(rid, []):
                md.append(f"  - 证据（§{sec} p.{pg}）：")
                for s in sents:
                    md.append(f"    - {s}")
        md.append("")
        md.append("---")
        md.append("")

    out = os.path.join(root, "review_digest.md")
    open(out, "w", encoding="utf-8").write("\n".join(md))
    n = len(md)
    print(f"[out] {out}  （{len(subs)} 篇，{n} 行，约 {n * 16 // 10 // 100}k 字符）")


if __name__ == "__main__":
    main()
