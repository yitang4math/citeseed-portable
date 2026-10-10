#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""批量跑 v2 流程：对多份 PDF 各跑一次 autorun.py，汇总成一张表。

定位：**批量初筛**。机器负责圈定候选 + 标记风险，人只看被标记的那几篇。
每篇的完整产物仍落在 <OUT>/<name>/ 下，需要深挖时按 v2 的 A3 直接读。

用法
----
  # 1) 直接吃一个文件夹（最常用）
  python batchrun.py --dir "/path/to/papers/TDA" --out batch_tda
  python batchrun.py --dir "/path/to/2026批次" --recursive --out batch_x   # 含子目录

  # 2) 从文件清单跑（每行一个绝对路径）
  python batchrun.py --list pdfs.txt --out batch_topo

  # 3) 从 glob 跑
  python batchrun.py --glob "/path/to/pdfs/*.pdf" --out batch_mag

  # 4) 从 lit.db 跑（按 SQL 条件筛，只取 PDF 真实存在的）
  python batchrun.py --db /path/to/lit.db \
      --where "q_tag='拓扑深度学习'" --out batch_topo

  # 5) 带人工目测的参考文献条数映射（启用 C1 判据）
  python batchrun.py --list pdfs.txt --expect expect.csv --out batch_x

可选参数
--------
  --jobs N      并行数（默认 4；PDF 解析是 IO+CPU 混合，4 通常够）
  --force       闸口失败也继续（默认开启，见下方说明）
  --no-force    闸口失败即停，汇总表只标 GATE_FAIL，不出 Top 榜
  --limit N     只跑前 N 篇（试水 / 分批处理用）
  --skip-done   续跑：同一 --out 下已有产物的篇自动跳过，汇总表仍包含它们
                分批处理的正确用法：--limit 逐段加大 + --skip-done，不会重跑已完成的

关于 --force
------------
批量场景默认**开启**：目的是把候选圈出来，闸口失败只作为「需人工关注」的标记，
不阻断。代价是把握度整体降一档，汇总表 `判定` 列会写出来。
若要严格按 SOP 走（闸口不过就不出结论），加 `--no-force`。

汇总表列
--------
  name / refs / ctx / 覆盖 / 制式 / 闸口 / Top1 / 分数 / 比值 / 把握 / 结论处理方式 / PDF
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
AUTORUN = os.path.join(HERE, "autorun.py")

RE_S1 = re.compile(r"\[S1\] pages=(\d+)")
RE_S3 = re.compile(r"\[S3\] refs=(\d+) ctx=(\d+) 被引=(\d+)")
RE_STYLE = re.compile(r"\[S2\].*?推测制式=(\w+)")
RE_GATE = re.compile(r"未通过 ([\w,]+)")
RE_RATIO = re.compile(r"Top1/第4名=([\d.]+)")
RE_TOP1 = re.compile(r"^\s*1\.\[\s*(\d+)\]\s+([\d.]+)\s+(\S+)\s+(\S+?)\s+次\s*(\d+)\s+(.*)$",
                     re.M)


def run_one(task):
    pdf, out, expect, force = task
    cmd = [PY, AUTORUN, pdf, "--out", out]
    if expect:
        cmd += ["--expect", str(expect)]
    if force:
        cmd += ["--force"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=HERE, timeout=600)
        txt = r.stdout or ""
    except subprocess.TimeoutExpired:
        txt = "[TIMEOUT] 超过 600s"
    except Exception as e:
        txt = f"[ERR] {e}"
    # 保存原始报告：--skip-done 续跑时要靠它重建汇总行，不用重跑
    try:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "autorun_stdout.txt"), "w", encoding="utf-8") as f:
            f.write(txt)
    except Exception:
        pass
    return pdf, out, txt, None


def parse(txt):
    """从 autorun 报告里抽汇总所需的字段。"""
    d = {"pages": "", "refs": "", "ctx": "", "covered": "", "style": "",
         "gate": "OK", "fails": "", "ratio": "", "top1": "", "score": "",
         "role": "", "times": "", "title": ""}
    m = RE_S1.search(txt);  d["pages"] = m.group(1) if m else ""
    m = RE_S3.search(txt)
    if m:
        d["refs"], d["ctx"], d["covered"] = m.group(1), m.group(2), m.group(3)
    m = RE_STYLE.search(txt); d["style"] = m.group(1) if m else ""
    m = RE_GATE.search(txt)
    if m:
        d["gate"] = "FAIL"
        d["fails"] = m.group(1)
    m = RE_RATIO.search(txt); d["ratio"] = m.group(1) if m else ""
    m = RE_TOP1.search(txt)
    if m:
        d["top1"], d["score"], d["role"], d["times"] = m.group(1), m.group(2), m.group(4), m.group(5)
        d["title"] = m.group(6).strip()[:46]
    # 静默失败必须显式标出来：报告为空 / 崩溃 / 超时 都可能让上面各字段抽不到，
    # 而 gate 默认值是 "OK" —— 不拦住的话，失败篇会混在"闸口 OK"里被当成可信结果。
    if (not txt.strip()) or "FATAL" in txt or txt.startswith("[ERR]") \
            or "[TIMEOUT]" in txt or "Traceback" in txt:
        d["gate"] = "FATAL"
    return d


def verdict(d, force):
    """结论处理方式：批量初筛后，这一篇该怎么处置。"""
    if d["gate"] == "FATAL":
        return "低", "抽取失败，回退 v1 逐项排查"
    if d["gate"] == "FAIL":
        return "低", f"闸口 {d['fails']} 未过，须 A3 人工读证据" + ("（已 --force）" if force else "")
    try:
        r = float(d["ratio"])
    except (TypeError, ValueError):
        return "低", "无排序输出，须 A3 人工读证据"
    if r >= 2.0:
        return "中高", "排序可定序，A3 核 Top3 即可"
    return "中", "比值 <2.0，排序只圈候选，A3 必须逐条看证据"


def load_expect(path):
    """expect.csv：两列 `pdf_path,expect`（可只写文件名）。"""
    if not path:
        return {}
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip() and row[1].strip().isdigit():
                out[os.path.basename(row[0].strip())] = int(row[1].strip())
    return out


def collect(args):
    """按 --dir / --list / --glob / --db 收集 PDF 绝对路径。"""
    pdfs = []
    if args.dir:
        root = os.path.abspath(args.dir)
        if not os.path.isdir(root):
            sys.exit(f"[!!] --dir 不是目录：{root}")
        if args.recursive:
            for dp, _, fns in os.walk(root):
                pdfs += [os.path.join(dp, f) for f in fns if f.lower().endswith(".pdf")]
        else:
            pdfs += [os.path.join(root, f) for f in os.listdir(root)
                     if f.lower().endswith(".pdf")]
    if args.list:
        with open(args.list, encoding="utf-8") as f:
            pdfs += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if args.glob:
        import glob as _g
        pdfs += sorted(_g.glob(args.glob, recursive=True))
    if args.db:
        con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        where = args.where or "1=1"
        for (p,) in con.execute(
                f"select pdf_path from papers where pdf_path is not null and pdf_path!='' and ({where})"):
            pdfs.append(p)
        con.close()
    seen, uniq = set(), []
    for p in pdfs:
        p = os.path.abspath(p)
        if p.lower().endswith(".pdf") and p not in seen and os.path.exists(p):
            seen.add(p)
            uniq.append(p)
    return uniq


def safe_name(pdf, i):
    base = os.path.splitext(os.path.basename(pdf))[0]
    base = re.sub(r"[^\w\u4e00-\u9fff.-]", "_", base)[:48]
    return f"{i:03d}_{base}"


def main():
    ap = argparse.ArgumentParser(description="批量跑 v2 流程并汇总")
    ap.add_argument("--out", required=True, help="输出目录")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dir", help="文件夹：直接吃里面的 .pdf（加 --recursive 可递归子目录）")
    g.add_argument("--list", help="PDF 路径清单（每行一个）")
    g.add_argument("--glob", help="PDF 的 glob 模式")
    g.add_argument("--db", help="lit.db 路径（配合 --where）")
    ap.add_argument("--where", help="lit.db 的 SQL 条件，如 \"q_tag='拓扑深度学习'\"")
    ap.add_argument("--recursive", action="store_true",
                    help="配合 --dir：递归子目录（默认只看该层）")
    ap.add_argument("--expect", help="expect.csv：pdf 路径/文件名,参考文献条数")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-done", action="store_true",
                    help="续跑：同一 --out 下已有产物的篇跳过（分批处理的正确用法）")
    ap.add_argument("--force", dest="force", action="store_true", default=True)
    ap.add_argument("--no-force", dest="force", action="store_false")
    a = ap.parse_args()

    pdfs = collect(a)
    if a.limit:
        pdfs = pdfs[:a.limit]
    if not pdfs:
        print("[FATAL] 没有可用的 PDF")
        return
    exp = load_expect(a.expect)
    root = os.path.abspath(a.out)
    os.makedirs(root, exist_ok=True)

    tasks = []
    names = []
    for i, p in enumerate(pdfs, 1):
        n = safe_name(p, i)
        names.append((n, p))
        # --skip-done：同一 OUT 目录续跑时跳过已有产物的篇（排序稳定 → 序号一致）
        # 判据是「报告存在且非空」：空报告 = 上轮崩溃，必须重跑，否则失败会被永久跳过。
        if a.skip_done:
            fp = os.path.join(root, n, "autorun_stdout.txt")
            if os.path.exists(fp) and os.path.getsize(fp) > 0:
                continue
        tasks.append((p, os.path.join(root, n),
                      exp.get(os.path.basename(p)), a.force))

    n_skip = len(names) - len(tasks)
    print(f"[batch] 共 {len(names)} 篇，本次跑 {len(tasks)} 篇"
          f"{f'（跳过已完成 {n_skip}）' if n_skip else ''}，并行 {a.jobs}，force={a.force}")
    results = {}
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        for (p, o, txt, _x) in ex.map(run_one, tasks):
            results[os.path.abspath(o)] = txt

    rows = []
    for name, pdf in names:
        out = os.path.join(root, name)
        txt = results.get(os.path.abspath(out))
        if txt is None:  # 本次没跑 = 已完成的，从存下来的报告重建
            fp = os.path.join(out, "autorun_stdout.txt")
            txt = open(fp, encoding="utf-8").read() if os.path.exists(fp) else ""
        d = parse(txt)
        conf, action = verdict(d, a.force)
        rows.append({
            "name": name, "refs": d["refs"], "ctx": d["ctx"], "覆盖": d["covered"],
            "制式": d["style"], "闸口": d["gate"],
            "Top1": d["top1"], "分数": d["score"], "比值": d["ratio"],
            "把握": conf, "结论处理方式": action,
            "Top1题名(截断)": d["title"], "PDF": pdf,
        })

    csv_path = os.path.join(root, "batch_summary.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    md = [f"# 批量初筛汇总（{len(rows)} 篇）", "",
          "| # | 样本 | 书目 | 上下文 | 制式 | 闸口 | Top1 | 分数 | 比值 | 处置 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        md.append(f"| {i} | {r['name'][:34]} | {r['refs']} | {r['ctx']} | {r['制式']} | "
                  f"{r['闸口']} | [{r['Top1']}] | {r['分数']} | {r['比值']} | {r['结论处理方式'][:26]} |")
    need = [r for r in rows if r["闸口"] != "OK" or (r["比值"] and float(r["比值"] or 0) < 2.0)]
    md += ["", f"## 需人工关注（{len(need)}/{len(rows)}）", ""]
    for r in need:
        md.append(f"- **{r['name']}**：{r['结论处理方式']}　PDF `{r['PDF']}`")
    md += ["", "> 完整产物在各自子目录；深挖时按 v2 的 A3 直接读 `refs_nodes.json` / `seeds_evidence_pack.md`。"]
    md_path = os.path.join(root, "batch_summary.md")
    open(md_path, "w", encoding="utf-8").write("\n".join(md))

    print(f"[out] {csv_path}")
    print(f"[out] {md_path}")
    print(f"[!! ] 需人工关注 {len(need)}/{len(rows)} 篇")


if __name__ == "__main__":
    main()
