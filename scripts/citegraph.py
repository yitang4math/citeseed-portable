#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
citegraph.py — 由参考文献 + 引用上下文构建「参考文献关系图谱」

输入: citeparse.py 产出的 refs_nodes.json / contexts.json
用法:
    python citegraph.py citetool_out
    python citegraph.py citetool_out --enrich          # 联网补真实引用边（需 OPENALEX_API_KEY）

产出:
    refs_edges.csv        边表（type: co_occurrence / evolution / contrast / cites）
    refs_graph.graphml    可导入 Gephi / yEd / Cytoscape
    refs_clusters.md      主题聚类 + 时间线
    refs_mindmap.md       Mermaid 思维导图（Typora/Obsidian/GitHub 可直接渲染）
    refs_network.svg      自绘矢量网络图（无需 matplotlib）

边型说明:
    co_occurrence  同一句话里被共同引用 —— 局部共引，主题相近的强信号
    evolution      同句共引且句含 "extends / improves / 基于 / 改进" 等演进线索
    contrast       同句共引且句含 "however / unlike / 然而 / 不同于" 等对比线索
    cites          真实引用边（A 的参考文献里有 B），需 --enrich 联网获取
"""
import re
import os
import csv
import json
import math
import argparse
from pathlib import Path
from collections import defaultdict, Counter

import networkx as nx

EVOLUTION_CUE = re.compile(
    r'\b(extend\w*|improv\w*|build(s|ing)? on|based on|variant of|generaliz\w+|'
    r'advance\w*|successor|follow\w* ?up|refine\w*|scale[sd]? up|surpass\w*)\b|'
    r'改[进良]|扩展|推广|基于.{0,12}(方法|模型|工作)|在.{0,10}基础上|继承|衍生|超越', re.I)

CONTRAST_CUE = re.compile(
    r'\b(however|unlike|in contrast|whereas|on the other hand|rather than|'
    r'instead of|differ\w+|disagree\w+|conflict\w+|fail(s|ed)? to|cannot|'
    r'limitation|drawback|shortcoming)\b|'
    r'然而|但[是]?|不同于|相反|相较|存在分歧|争议|局限|不足', re.I)

CLUSTER_COLORS = ["#185FA5", "#0F6E56", "#993C1D", "#534AB7",
                  "#A32D2D", "#3B6D11", "#854F0B", "#993556"]
EDGE_STYLE = {
    "co_occurrence": ("#B4B2A9", 0.7, ""),
    "evolution": ("#185FA5", 1.6, ""),
    "contrast": ("#A32D2D", 1.6, "5,3"),
    "cites": ("#0F6E56", 1.2, ""),
}


# ---------------------------------------------------------------- 建图

def build_graph(nodes, contexts, window_sentences=1):
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], **{k: n.get(k, "") for k in
                               ("label", "raw", "year", "title", "authors", "venue", "times_cited")})
    edges = defaultdict(lambda: {"weight": 0, "evidence": [], "types": Counter()})
    for c in contexts:
        src = c["ref_id"]
        for dst in c.get("co_refs", []):
            if dst == src or dst not in G:
                continue
            a, b = (src, dst) if src < dst else (dst, src)
            e = edges[(a, b)]
            e["weight"] += 1
            e["types"]["co_occurrence"] += 1
            if EVOLUTION_CUE.search(c["sentence"]):
                e["types"]["evolution"] += 1
            if CONTRAST_CUE.search(c["sentence"]):
                e["types"]["contrast"] += 1
            if len(e["evidence"]) < 2:
                e["evidence"].append(f"p{c.get('page','?')}: {c['sentence'][:150]}")
    for (a, b), e in edges.items():
        primary = "co_occurrence"
        if e["types"]["evolution"]:
            primary = "evolution"
        elif e["types"]["contrast"]:
            primary = "contrast"
        G.add_edge(a, b, weight=e["weight"], type=primary,
                   types=json.dumps(dict(e["types"]), ensure_ascii=False),
                   evidence=" | ".join(e["evidence"]))
    return G


def enrich_cites(G, nodes):
    """用 OpenAlex 补真实引用边。需要环境变量 OPENALEX_API_KEY。"""
    try:
        import requests
    except ImportError:
        print("[enrich] 未装 requests，跳过")
        return 0
    key = os.environ.get("OPENALEX_API_KEY")
    if not key:
        print("[enrich] 未设置 OPENALEX_API_KEY，跳过真实引用边补全")
        return 0
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {key}"})
    id_of = {}
    for n in nodes:
        q = n.get("doi") or n.get("title")
        if not q:
            continue
        try:
            if n.get("doi"):
                r = sess.get(f"https://api.openalex.org/works/doi:{n['doi']}", timeout=20)
            else:
                r = sess.get("https://api.openalex.org/works",
                             params={"filter": f"title.search:{q[:120]}", "per-page": 1}, timeout=20)
            if r.status_code == 200:
                d = r.json()
                d = d if isinstance(d, dict) else (d["results"][0] if d.get("results") else None)
                if d:
                    id_of[n["id"]] = (d["id"].split("/")[-1], set(d.get("referenced_works") or []))
        except Exception:
            continue
    added = 0
    for a, (aid, refs) in id_of.items():
        for b, (bid, _) in id_of.items():
            if a != b and bid in refs:
                if G.has_edge(a, b):
                    G[a][b]["type"] = "cites"
                    td = json.loads(G[a][b].get("types") or "{}")
                    td["cites"] = td.get("cites", 0) + 1
                    G[a][b]["types"] = json.dumps(td, ensure_ascii=False)
                else:
                    G.add_edge(a, b, weight=1, type="cites",
                               types=json.dumps({"cites": 1}), evidence="OpenAlex")
                added += 1
    print(f"[enrich] OpenAlex 命中 {len(id_of)}/{len(nodes)} 篇，新增/升级引用边 {added} 条")
    return added


# ---------------------------------------------------------------- 产出

def write_edges(G, out):
    rows = []
    for a, b, d in G.edges(data=True):
        rows.append({"source": a, "target": b, "type": d.get("type", ""),
                     "weight": d.get("weight", 1), "types": d.get("types", ""),
                     "evidence": d.get("evidence", "")})
    rows.sort(key=lambda r: (-r["weight"], r["source"]))
    with open(out / "refs_edges.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["source", "target", "type", "weight", "types", "evidence"])
        w.writeheader()
        w.writerows(rows)
    return rows


def write_graphml(G, out):
    nx.write_graphml(G, str(out / "refs_graph.graphml"))


def cluster(G):
    try:
        comms = nx.community.louvain_communities(G, seed=42, weight="weight")
    except Exception:
        comms = [{n} for n in G.nodes()]
    order = sorted(range(len(comms)), key=lambda i: -len(comms[i]))
    part = {}
    for rank, i in enumerate(order):
        for n in comms[i]:
            part[n] = rank
    return part, [comms[i] for i in order]


def write_clusters(G, part, groups, out):
    lines = ["# 参考文献主题聚类与时间线\n",
             "> 聚类基于「同句共引 + 演进/对比线索」的加权图做 Louvain 社区发现；\n"
             "> 时间线按年份排列，用于看方法脉络的先后顺序。\n"]
    for rank, grp in enumerate(groups):
        items = sorted(grp, key=lambda n: str(G.nodes[n].get("year", "")))
        evo = sum(1 for a in items for b in items
                  if a < b and G.has_edge(a, b) and G[a][b].get("type") == "evolution")
        con = sum(1 for a in items for b in items
                  if a < b and G.has_edge(a, b) and G[a][b].get("type") == "contrast")
        lines.append(f"\n## 聚类 {rank + 1}　（{len(grp)} 篇，演进边 {evo}，对比边 {con}）\n")
        lines.append("| ref | 文献 | 年份 | 被引次数 | 聚类内主要关系 |")
        lines.append("|---|---|---|---|---|")
        for n in items:
            rel = []
            for m in items:
                if m != n and G.has_edge(n, m):
                    t = G[n][m].get("type", "")
                    tag = {"evolution": "演进", "contrast": "对比",
                           "cites": "真实引用", "co_occurrence": "共引"}.get(t, t)
                    rel.append(f"{m}({tag})")
            lines.append(f"| {n} | {G.nodes[n].get('label','')} | {G.nodes[n].get('year','')} "
                         f"| {G.nodes[n].get('times_cited',0)} | {', '.join(rel[:6])} |")
    years = sorted({str(G.nodes[n].get("year", "")) for n in G.nodes() if str(G.nodes[n].get("year", ""))})
    lines.append("\n## 时间线\n")
    lines.append("| 年份 | 文献 |")
    lines.append("|---|---|")
    for y in years:
        ns = [n for n in G.nodes() if str(G.nodes[n].get("year", "")) == y]
        lines.append(f"| {y} | " + "；".join(f"[{n}] {G.nodes[n].get('label','')}" for n in ns) + " |")
    (out / "refs_clusters.md").write_text("\n".join(lines), encoding="utf-8")


def sanitize(s, n=26):
    s = re.sub(r'[()\[\]{}"#]', " ", str(s))
    s = re.sub(r'\s+', " ", s).strip()
    return s[:n]


def write_mindmap(G, part, groups, out):
    lines = ["```mermaid", "mindmap", "  root((参考文献关系))"]
    for rank, grp in enumerate(groups):
        items = sorted(grp, key=lambda n: str(G.nodes[n].get("year", "")))
        lines.append(f"    聚类{rank+1}_{sanitize(items[0] if items else '', 12)}")
        for n in items:
            y = G.nodes[n].get("year", "")
            lines.append(f"      [{n}] {sanitize(G.nodes[n].get('label',''), 22)} {y}")
    lines.append("```")
    (out / "refs_mindmap.md").write_text("\n".join(lines), encoding="utf-8")


def write_svg(G, part, out, W=1120, H=820):
    n = len(G.nodes())
    if n == 0:
        return
    pos = nx.spring_layout(G, seed=42, k=1.4 / math.sqrt(max(n, 4)), iterations=120)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    sx = (xmax - xmin) or 1
    sy = (ymax - ymin) or 1
    M, TOP, BOT = 70, 60, 70
    cw, ch = W - 2 * M - 160, H - TOP - BOT

    def XY(node):
        x, y = pos[node]
        return (M + (x - xmin) / sx * cw, TOP + (y - ymin) / sy * ch)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
             '<rect width="100%" height="100%" fill="#ffffff"/>',
             f'<text x="{M}" y="34" font-size="16" font-weight="500" fill="#2C2C2A">参考文献关系图谱</text>']
    for a, b, d in G.edges(data=True):
        color, wdt, dash = EDGE_STYLE.get(d.get("type", "co_occurrence"), EDGE_STYLE["co_occurrence"])
        x1, y1 = XY(a)
        x2, y2 = XY(b)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{color}" stroke-width="{wdt}"{da} opacity="0.8"/>')
    for node in G.nodes():
        x, y = XY(node)
        r = 4 + 2.4 * math.sqrt(G.nodes[node].get("times_cited", 0) or 0)
        c = CLUSTER_COLORS[part.get(node, 0) % len(CLUSTER_COLORS)]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{c}" stroke="#ffffff" stroke-width="1"/>')
        if n <= 70:
            parts.append(f'<text x="{x + r + 3:.1f}" y="{y + 4:.1f}" font-size="11" fill="#444441">'
                         f'{sanitize(G.nodes[node].get("label", node), 24)}</text>')
    lx, ly = W - 160, TOP + 10
    parts.append(f'<text x="{lx}" y="{ly}" font-size="13" font-weight="500" fill="#2C2C2A">图例</text>')
    legend = [("co_occurrence", "同句共引"), ("evolution", "方法演进/改进"),
              ("contrast", "观点对比/分歧"), ("cites", "真实引用边(OpenAlex)")]
    for i, (k, label) in enumerate(legend):
        color, wdt, dash = EDGE_STYLE[k]
        yy = ly + 26 + i * 24
        da = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+26}" y2="{yy}" stroke="{color}" stroke-width="{wdt}"{da}/>')
        parts.append(f'<text x="{lx+32}" y="{yy+4}" font-size="12" fill="#444441">{label}</text>')
    for i in range(len(set(part.values()))):
        yy = ly + 26 + (len(legend) + i) * 24
        parts.append(f'<circle cx="{lx+13}" cy="{yy-4}" r="5" fill="{CLUSTER_COLORS[i % len(CLUSTER_COLORS)]}"/>')
        parts.append(f'<text x="{lx+32}" y="{yy}" font-size="12" fill="#444441">聚类 {i+1}</text>')
    parts.append("</svg>")
    (out / "refs_network.svg").write_text("\n".join(parts), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("indir")
    ap.add_argument("--enrich", action="store_true")
    args = ap.parse_args()

    out = Path(args.indir)
    nodes = json.loads((out / "refs_nodes.json").read_text(encoding="utf-8"))
    contexts = json.loads((out / "contexts.json").read_text(encoding="utf-8"))

    G = build_graph(nodes, contexts)
    print(f"[graph] 节点 {G.number_of_nodes()}，边 {G.number_of_edges()}")
    if args.enrich:
        enrich_cites(G, nodes)

    rows = write_edges(G, out)
    write_graphml(G, out)
    part, groups = cluster(G)
    write_clusters(G, part, groups, out)
    write_mindmap(G, part, groups, out)
    write_svg(G, part, out)
    nx.set_node_attributes(G, {n: part.get(n, 0) for n in G.nodes()}, "cluster")
    write_graphml(G, out)

    cnt = Counter(d.get("type", "") for _, _, d in G.edges(data=True))
    print("[edges] " + ", ".join(f"{k}={v}" for k, v in cnt.items()))
    print(f"[out] {out/'refs_edges.csv'}")
    print(f"[out] {out/'refs_graph.graphml'}")
    print(f"[out] {out/'refs_clusters.md'}")
    print(f"[out] {out/'refs_mindmap.md'}")
    print(f"[out] {out/'refs_network.svg'}")


if __name__ == "__main__":
    main()
