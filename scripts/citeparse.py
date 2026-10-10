#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
citeparse.py — 从论文 PDF 抽取「引用 — 观点支撑」对照表

用法:
    python citeparse.py paper.pdf                         # 参考文献列表从 PDF 尾部解析
    python citeparse.py paper.pdf --refs refs.bib         # 用 BibTeX 提供参考文献
    python citeparse.py paper.pdf --refs refs.txt         # 一行一条
    python citeparse.py paper.pdf --style authoryear      # 著者-年份制（默认 numeric）
    python citeparse.py paper.pdf --out out_dir           # 指定输出目录

产出:
    citation_support.csv   引用—观点支撑对照表（Excel 可直接打开）
    citation_support.md    同上，Markdown 版，便于阅读与人工补写
    refs_nodes.json        参考文献节点（供 citegraph.py 使用）
    contexts.json          全部引用上下文原文（含页码/章节）

依赖: pymupdf, pandas(可选)
"""
import re
import os
import io
import csv
import json
import argparse
import bisect
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


# ---------------------------------------------------------------- 文本层

ABBREV_END = re.compile(
    r'\b(et al|e\.g|i\.e|cf|vs|Fig|Eq|Ref|No|approx|Dr|St|Prof)\.$', re.I)

HEADING_RE = re.compile(
    r'^\s*(\d+(\.\d+)*\.?\s+)?(abstract|introduction|related work|background|'
    r'preliminar\w+|method\w*|approach|model|framework|experiment\w*|'
    r'result\w*|discussion|conclusion|future work|appendix|'
    r'摘要|引言|绪论|相关工作|背景|预备知识|方法|模型|框架|实验|结果|讨论|结论|展望|附录)\s*:?\s*$',
    re.I)

# 编号型标题通用规则：IEEE/ACM 稿件用罗马数字（"I. INTRODUCTION"），
# ACL/Springer 用阿拉伯数字（"1 Introduction"）。前者 HEADING_RE 认不出来，
# 会导致整个引言/相关工作被并进"(正文开头)"——实测在真实 PAMI 论文上，
# 这一条让 Method 章节的权重反超了 Introduction，排序完全失真。
HEADING_NUM_RE = re.compile(
    r'^\s*(?:\d+|[IVXL]+)(?:\.\d+)*\.?\s+[A-Z][\w\-—–,\'\u4e00-\u9fff]'
    r'(?:[\w\-—–,\'\u4e00-\u9fff]|\s){0,58}$')

def looks_like_heading(line: str) -> bool:
    """是否为章节标题。

    编号型标题再收紧一层：要求标题主体基本全大写（IEEE/ACM 风格），
    或含中文（CN 稿件），且词数不多。否则 '10. The figure compares mini-batch…'
    这类图注碎片会被误判成标题。
    """
    if len(line) > 90:
        return False
    if HEADING_RE.match(line):
        return True
    if not HEADING_NUM_RE.match(line):
        return False
    if re.search(r'[\u4e00-\u9fff]', line):
        return len(line) <= 30
    if len(line.split()) > 12:
        return False
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.6


# 附录/补充材料的开头词（LaTeX 稿的附录常不用 "Appendix" 而用语义标题）
APPENDIX_START_RE = re.compile(
    r'^(appendix|supplementary|additional|further (?:results|experiments|details)|'
    r'extended|acknowledg\w+|broader impact|limitation|ethic\w*|implementation details|'
    r'a\.?\d+\s|补充|附录|致谢)\b', re.I)


def starts_like_heading(line: str) -> bool:
    """合并后的单元可能"标题 + 正文首句"连成一行（长度远超 90），
    此时 looks_like_heading 会失效 —— 只看开头 80 字符是否为标题。"""
    if looks_like_heading(line):
        return True
    return bool(APPENDIX_START_RE.match(line[:80].strip()))


REF_SECTION_RE = re.compile(
    r'^\s*(references|bibliography|works cited|reference list|参考文献|引用文献)'
    r'(?:\s+(?:and|&)\s+(?:notes|further\s+reading))?\s*:?\s*$',
    re.I)

STOP_AFTER_RE = re.compile(
    r'^\s*(appendix|supplementary|acknowledg\w+|附[录录]|补充材料|致谢)\s*:?\s*$', re.I)

NUM_MARK = re.compile(
    r'\[\s*(\d{1,3}(?:\s*(?:[,;，、]|[-–—]|--)\s*\d{1,3})*)\s*\]')

# 括号数字制（Science/Science Advances/Nature/Cell/PNAS/eLife 常见的上标引用）：
# "…T-maze and open-field tasks (31)." / "(42–49)" / "(47, 48, 53)"
# —— 正文里没有任何 [n]，原先整篇会判成 authoryear，上下文抽到 0 条。
PAREN_NUM_MARK = re.compile(
    r'\(\s*(\d{1,3}(?:\s*(?:[,;，、]|[-–—]|--)\s*\d{1,3})*)\s*\)')

def paren_nums(text):
    """抽出文本里所有括号数字（`(31)`、`(42–49)`、`(47, 48, 53)`）的编号序列。"""
    nums = []
    for m in PAREN_NUM_MARK.finditer(text):
        for tok in re.split(r'\s*(?:[,;，、]|[-–—])\s*', m.group(1)):
            tok = tok.strip()
            if tok.isdigit() and 1 <= int(tok) <= 300:
                nums.append(int(tok))
    return nums


def looks_like_eq_numbering(nums):
    """公式编号的形状判据：**1..max 被用满，没有空洞**。

    公式编号每个数至少会被引用一次 → distinct == max（实测 GSVD 11/11、DiffLift 7/7）；
    真实引用编号必然有空洞（Nakai 49/59，缺 8、16–18、21、24…）。
    GSVD 稿正文是作者-年制，但公式编号 22 处 > 作者年 17 处，只靠计数竞争会被
    误判成 paren；靠这个形状判据否决掉。
    """
    if len(nums) < 6:
        return False
    mx = max(nums)
    if mx < 5:
        return False
    return len(set(nums)) >= 0.95 * mx


AUTHOR_YEAR = re.compile(
    r'[\(（]\s*('
    r'[A-Z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\-\'’\.]*'
    r'(?:\s+(?:and|&|和)\s+[A-Z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff\-\'’\.]*)?'
    r'(?:\s*(?:et\s+al\.?|等))?'
    r'[\s,，]*'
    r'    (?:19|20)\d{2}[a-z]?'
    r'(?:\s*[;,;]\s*[^)）]{0,60})?'
    r')\s*[\)）]')


# 书目条目的"作者列表开头"： Surname, Given ... / Given Surname and X / 张三, 李四
AUTHSTART_RE = re.compile(
    r"^[A-Z\u00C0-\u024F\u4e00-\u9fff][\w\u00C0-\u024F\u4e00-\u9fff\-\.'’]*"
    r"(?:\s+[A-Z\u00C0-\u024F\u4e00-\u9fff][\w\u00C0-\u024F\u4e00-\u9fff\-\.'’]*)*"
    r"(?:\s*,|\s+and\b|\s+&\b)")


# 作者-年制引用：叙述式放在前面（优先级高），括号式兜底
AY_CITE_RE = re.compile(
    r"(?P<narr>[A-Z\u00C0-\u024F][\w\u00C0-\u024F\-'’]+"
    r"(?:\s+(?:and|&)\s+[A-Z\u00C0-\u024F][\w\u00C0-\u024F\-'’]+)?"
    r"(?:\s+et\s+al\.?)?)"
    r"\s*[\(（]\s*(?P<y1>(?:19|20)\d{2})[a-z]?\s*[\)）]"
    r"|[\(（](?P<blob>[^)）]{1,300})[\)）]")

# 作者串里的虚词，避免把 "et al." / "and" 当成姓氏去匹配
AY_STOPWORDS = {"et", "al", "and", "the", "of", "for", "with", "from", "in", "on",
                "van", "der", "del", "de", "du", "da", "von", "di", "dos", "le",
                "la", "den", "ter", "bin", "el", "two", "see", "fig", "figure",
                "table", "appendix", "section", "sec", "eq", "e"}


ABSTRACT_HEAD_RE = re.compile(r'^(Abstract)\s*[—–\-:]\s*(.*)$', re.I)


def extract_units(pdf_path):
    """返回 [(page_no, 段落文本), ...]。

    关键改动（在真实双栏论文上被迫修的）：
    原来直接按 page.get_text("text") 的**行**切分，而两栏排版下换行 ≠ 句末，
    导致句子被拦腰截断——实测把 "Liu et al. [45] have also discussed limitations…"
    拆成两段，后半句因不含引用标记而与 [45] 完全脱离，所有"局限/批评"线索丢失，
    该文献从第 3 名掉到第 43 名。
    现在：①用 blocks 按「先左栏后右栏、栏内按纵向」排序恢复阅读顺序；
          ②把行合并回段落（处理连字符断词）；③标题行保持独立单元。
    """
    doc = pymupdf.open(pdf_path)
    per_page = []
    for pno in range(len(doc)):
        page = doc[pno]
        width = page.rect.width
        blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        items = []
        for b in blocks:
            x0, y0, x1, text = b[0], b[1], b[2], b[4]
            # 用**左边缘**而非中心点判栏：超长行溢出页宽时中心点会落到右半边，
            # 被误判成右栏而排到最后（实测会丢掉整段正文）。
            col = 0 if x0 < width / 2 else 1
            items.append((col, round(y0, 1), round(x0, 1), text))
        items.sort(key=lambda z: (z[0], z[1], z[2]))

        lines = []
        for col, y, x, text in items:
            for ln in text.split("\n"):
                ln = ln.strip()
                if ln:
                    lines.append(ln)
        per_page.append((pno + 1, lines))
    doc.close()

    # 页眉/页脚：**同一短行在多页重复出现**即判定为装饰性文本。
    # ICLR 稿的 "Published as a conference paper at ICLR 2026" 会串进每页首段，
    # 实测把参考文献首条污染成 "Published as ... Jie Chen, Tengfei Ma, ..."，
    # 使该条目无法被"作者串开头"识别，整表解析失败。
    counter = {}
    for _, lines in per_page:
        for ln in set(lines):
            if len(ln) <= 90:
                counter[ln] = counter.get(ln, 0) + 1
    thr = max(3, int(len(per_page) * 0.3))
    boiler = {ln for ln, c in counter.items() if c >= thr}

    units = []
    for pno, lines in per_page:
        for k, ln in enumerate(lines):
            # 装饰性文本：跨页重复的页眉页脚、页码。
            # 页码不能"见数字就删"—— LaTeX 稿常把章节编号单独排一行（"3"），
            # 误删后方法章标题就退化成 "DIFFERENTIABLE LIFTING"，与正文混成一个
            # 单元，整章引用被计入上一章节。判据改为：**纯粹数字行 + 位于页首/页尾**。
            if ln in boiler:
                continue
            if re.fullmatch(r'\d{1,4}', ln) and (k == 0 or k == len(lines) - 1
                                                 or int(ln) == pno):
                continue
            # IEEE 稿的摘要通常内联为 "Abstract—正文…"，拆出不丢正文
            m = ABSTRACT_HEAD_RE.match(ln)
            if m:
                units.append((pno + 1, m.group(1)))
                ln = m.group(2).strip()
                if not ln:
                    continue
            if not units:
                units.append((pno + 1, ln))
                continue
            pprev, prev = units[-1]
            # LaTeX 稿常把章节编号单独排成一行（"3" + 换行 + "DIFFERENTIABLE LIFTING"），
            # 而编号型标题的正则要求编号与标题同行 —— 不合并就识别不出方法章，
            # 方法部分的引用会被错误地计入上一个章节（实测 DIFFERENTIABLE LIFTING
            # 整章的上下文都被算进了 BACKGROUND）。
            if (pprev == pno + 1 and len(prev) <= 6 and len(ln) <= 90
                    and re.fullmatch(r'(?:\d+|[IVXL]+|[A-Z])(?:\.\d+)*\.?', prev)):
                units[-1] = (pprev, prev + ' ' + ln)
                continue
            # 标准去换行规则：**只有前一行不以句末标点结尾时才合并**。
            # 少了这条判据，单栏文档（每行就是完整句子）会一路串成巨型单元，
            # 正文与参考文献混在一起——实测合成样本因此只剩 1 篇参考文献。
            ends_sentence = bool(re.search(r'[.!?。！？;；:：]$', prev))
            if (pprev == pno + 1 and not ends_sentence
                    and not looks_like_heading(prev) and not looks_like_heading(ln)
                    and not REF_SECTION_RE.match(prev) and not REF_SECTION_RE.match(ln)
                    and len(prev) >= 12):
                units[-1] = (pprev, prev[:-1] + ln) if prev.endswith('-') \
                    else (pprev, prev + ' ' + ln)
            else:
                units.append((pno + 1, ln))
    return units


def build_body(units):
    """把 units 拼成全文，并返回 (full_text, offsets, page_at)。"""
    parts, offsets, pages = [], [], []
    pos = 0
    for pno, line in units:
        parts.append(line)
        offsets.append(pos)
        pages.append(pno)
        pos += len(line) + 1
    return "\n".join(parts), offsets, pages


def find_headings(units, offsets):
    """识别章节标题，返回 [(offset, heading_text)]。"""
    heads = []
    for i, (pno, line) in enumerate(units):
        if len(line) > 90:
            continue
        if line.endswith(('.', '。', ',', '，', ';')):
            continue
        if looks_like_heading(line):
            heads.append((offsets[i], line.strip()))
    return heads


def split_line_sentences(line):
    """单行内切句（PDF 行本身已是排版行，heading 不会被并进来）。"""
    spans, start = [], 0
    for m in re.finditer(r'[.!?。！？](?:\s|$)', line):
        end = m.end()
        s = line[start:end].strip()
        if s:
            spans.append(s)
        start = end
    if start < len(line):
        tail = line[start:].strip()
        if tail:
            spans.append(tail)
    out = []
    for s in spans:
        if out and ABBREV_END.search(out[-1].rstrip()):
            out[-1] = out[-1] + " " + s
        else:
            out.append(s)
    return out or ([line] if line.strip() else [])


def split_sentences(full):
    """按中英文句末标点切句，返回 [(start, end, text)]。"""
    spans, start = [], 0
    for m in re.finditer(r'[.!?。！？](?:\s|$)', full):
        end = m.end()
        s = full[start:end].strip()
        if s:
            spans.append([start, end, s])
        start = end
    if start < len(full):
        tail = full[start:].strip()
        if tail:
            spans.append([start, len(full), tail])
    merged = []
    for sp in spans:
        if merged and ABBREV_END.search(merged[-1][2].rstrip()):
            merged[-1][1] = sp[1]
            merged[-1][2] = merged[-1][2] + " " + sp[2]
        else:
            merged.append(sp)
    return [tuple(x) for x in merged]


# ---------------------------------------------------------------- 参考文献列表

def find_ref_range(units):
    """参考文献区所在的 unit 下标区间 [start, stop)；找不到返回 None。

    结束判据两条：
      ① 附录/补充材料的语义标题。注意**不能**用 looks_like_heading 兜底 ——
         IEEE 稿的表格列名 "Model" 恰好命中 heading 关键词表，会把 77 条
         参考文献截断成 6 条。
      ② 连续两条"又长又无年份"的单元 —— 单条不算（书目里常见不含年份的续行）。
    """
    n = len(units)
    start_idx = None
    # 原来只在文档后 55% 里找 REFERENCES —— 单页或参考文献靠前的稿子会漏。
    # 改为全文扫描并取**最后一次**出现（"References" 一词通常只在参考区）。
    for i in range(n):
        if REF_SECTION_RE.match(units[i][1]):
            start_idx = i
    if start_idx is None:
        return None
    stop, n_bad = n, 0
    for i in range(start_idx + 1, n):
        line = units[i][1]
        if STOP_AFTER_RE.match(line) or APPENDIX_START_RE.match(line[:80].strip()):
            stop = i
            break
        reflike = (len(line) <= 150
                   or bool(re.search(r'(?:19|20)\d{2}', line))
                   or bool(re.match(r'^\[\d', line)))
        if i - start_idx - 1 < 5:
            continue
        if reflike:
            n_bad = 0
        else:
            n_bad += 1
            if n_bad >= 2:
                stop = i - 1
                break
    return (start_idx, stop)


def parse_refs_from_pdf(units, offsets):
    """从 PDF 尾部解析参考文献条目，返回 [(number, text)]。

    两种书目版式：
      A. 带编号（IEEE/Nature/arXiv 默认）： "[1] Author..." → 按 [n] 切条；
      B. **无编号**（ICLR/ACL 常见的作者列表式）：整节只有 "Surname, Given..."，
         靠"作者串开头 + 含年份"判定条目边界。原实现只支持 A，遇到 B 直接返回
         0 条 —— 实测 ICLR 2026 的 DiffLift 稿就是 B 版式，整条管线因此空转。
    """
    rng = find_ref_range(units)
    if rng is None:
        return []
    start_idx, stop_idx = rng
    tail = [units[i][1] for i in range(start_idx + 1, stop_idx)]
    blob = " ".join(tail)
    marks = list(re.finditer(r'\[(\d{1,3})\]\s*', blob))
    if marks:
        entries = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(blob)
            text = re.sub(r'\s+', ' ', blob[m.end():end]).strip()
            if STOP_AFTER_RE.match(text):
                break
            entries.append((int(m.group(1)), text))
        return entries
    # C. 裸数字编号（Science/Science Advances/Springer/中文期刊常见）："1. Author..."
    #    —— 原来只认 [n]，遇到 C 会掉进 parse_refs_unnumbered，条目被整节粘成 1-2 条。
    bare = parse_refs_bare_numbered(tail)
    if len(bare) >= 5:
        return bare
    return parse_refs_unnumbered(tail)


BARE_NUM_RE = re.compile(r'^\s*(\d{1,3})\s*[.)]\s+(.*)$')


def parse_refs_bare_numbered(tail):
    """裸数字编号书目：按行首 `N.` / `N)` 切条，保留原编号。

    编号必须**递增**（允许跳号 ≤3），否则正文里的编号列表会被误当书目。
    返回 [(原编号, 条目文本)]；条目数 < 5 时调用方回退到无编号解析。
    """
    entries, cur, curnum, last = [], None, None, 0
    for raw in tail:
        line = re.sub(r'\s+', ' ', raw).strip()
        if not line:
            continue
        m = BARE_NUM_RE.match(line)
        if m and last < int(m.group(1)) <= last + 3:
            if cur is not None:
                entries.append((curnum, cur))
            curnum, cur, last = int(m.group(1)), m.group(2).strip(), int(m.group(1))
        elif cur is not None:
            cur = cur + ' ' + line
        elif curnum is None:
            cur, curnum = line, None
    if cur is not None:
        entries.append((curnum, cur))
    keep = [(n, t) for n, t in entries
            if len(t) >= 40 or re.search(r'(?:19|20)\d{2}', t)]
    return keep


def parse_refs_unnumbered(tail):
    """无编号书目：按"作者串开头"切条，返回 [(1..N, text)]。

    新条目判据 = **看起来是作者列表开头** 且 **本句或上一条含有年份**。
    反例（会被判为续行而接回上一条）：
      "net/forum?id=0JsRZEGZ7L."   → 换行被切断的 URL
      "//proceedings.mlr.press/v251/bernardez24a.html." → URL 续行
      "robust node embeddings. Advances in ..." → 题名续行
    """
    entries, cur = [], None
    for line in tail:
        line = re.sub(r'\s+', ' ', line).strip()
        if not line or re.fullmatch(r'[\d\.\-–— ]{1,6}', line):
            continue
        has_year = bool(re.search(r'(?:19|20)\d{2}', line))
        prev_has_year = bool(cur and re.search(r'(?:19|20)\d{2}', cur))
        is_new = bool(AUTHSTART_RE.match(line)) and (cur is None or has_year or prev_has_year)
        if is_new:
            if cur is not None:
                entries.append(cur)
            cur = line
        elif cur is None:
            cur = line
        else:
            cur = cur + ' ' + line
    if cur:
        entries.append(cur)
    # 过滤明显不是文献条目的碎片（过短且无年份）
    keep = [t for t in entries
            if len(t) >= 40 or re.search(r'(?:19|20)\d{2}', t)]
    return list(enumerate(keep, start=1))


def parse_bib(path):
    """极简 BibTeX 解析，返回 [(number, text)]（按出现顺序编号）。"""
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    entries = []
    for m in re.finditer(r'@(\w+)\s*\{\s*([^,]+),(.*?)\n\}', raw, re.S):
        body = m.group(3)
        field = {}
        for fm in re.finditer(r'(\w+)\s*=\s*\{(.*?)\}(?:,|$)', body, re.S):
            field[fm.group(1).lower()] = re.sub(r'\s+', ' ', fm.group(2)).strip('{}')
        for fm in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', body):
            field.setdefault(fm.group(1).lower(), fm.group(2))
        author = field.get("author", "")
        title = field.get("title", "")
        year = field.get("year", "")
        venue = field.get("journal") or field.get("booktitle") or field.get("venue") or ""
        entries.append({
            "number": len(entries) + 1,
            "authors": author,
            "title": title,
            "year": year,
            "venue": venue,
            "doi": field.get("doi", ""),
            "raw": f"{author} {title} {venue} {year}".strip(),
        })
    return [(e["number"], e["raw"]) for e in entries], entries


def build_ay_index(ref_map):
    """作者-年制的姓氏索引： {surname_lower: {ref_id: 首次出现位置}}。

    索引的是条目**前 170 字符**（作者区通常落在这里）里的每个首字母大写词 ——
    这样无论文献表写作 "Given Surname" 还是 "Surname, Given"，正文里的姓氏
    都能命中。位置用于消歧：同姓多篇时，出现在作者区更靠前的更可能是第一作者。
    """
    idx = {}
    for rid, meta in ref_map.items():
        head = (str(meta.get("raw", "")) or "")[:170]
        for mm in re.finditer(r"[A-Za-z\u00C0-\u024F][\w'’-]{1,}", head):
            tok = mm.group(0)
            if tok.lower() in AY_STOPWORDS:
                continue
            idx.setdefault(tok.lower(), {}).setdefault(rid, mm.start())
    return idx


def iter_ay_citations(stext):
    """产出 [(作者串, 年份)]，覆盖两种作者-年制写法：
      HAL 形式 "(Hajij et al., 2022; Telyatnikov et al., 2025)"
      叙述形式 "Hajij et al. (2022)" / "Bodnar and Rieck (2023)"
    一次 finditer 天然去重，叙述形式优先，不会重复计数。
    """
    out = []
    for m in AY_CITE_RE.finditer(stext):
        if m.group("y1"):
            out.append((m.group("narr"), m.group("y1")))
            continue
        blob = m.group("blob") or ""
        for piece in re.split(r'[;；]', blob):
            ys = re.findall(r'(?:19|20)\d{2}', piece)
            if not ys:
                continue
            out.append((piece[:piece.find(ys[0])], ys[0]))
    return out


def match_ay(stext, ref_map, ay_index):
    """把一句里的作者-年引用映射到 ref_id。"""
    hits = []
    for nm, year in iter_ay_citations(stext):
        toks = [t for t in re.findall(r"[A-Za-z\u00C0-\u024F][\w'’-]{1,}", nm)
                if t.lower() not in AY_STOPWORDS]
        best, bestkey = None, None
        n_cand = set()
        for t in toks:
            for rid, pos in ay_index.get(t.lower(), {}).items():
                n_cand.add(rid)
                y = str(ref_map.get(rid, {}).get("year", ""))
                # 条目缺年份时不惩罚（不少书目用 "to appear"）
                ymatch = (y == year) or not y
                key = (1 if ymatch else 0, -pos)
                if bestkey is None or key > bestkey:
                    bestkey, best = key, rid
        # 只在"年份对得上"或"候选唯一"时才认 —— 否则宁可不标
        if best is not None and (bestkey[0] == 1 or len(n_cand) == 1):
            hits.append(best)
    return hits


def parse_txt_refs(path):
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    out, meta = [], []
    for i, line in enumerate(raw.split("\n")):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r'^\s*[\[\(]?(\d{1,3})[\]\.\)]\s+(.*)$', line)
        num = int(m.group(1)) if m else i + 1
        text = m.group(2) if m else line
        out.append((num, text))
        meta.append({"number": num, "raw": text})
    return out, meta


def load_refs(path, fallback_from_pdf):
    """统一返回 ([(number, text)], [meta dict])。"""
    if not path:
        pdf_entries = fallback_from_pdf
        return pdf_entries, [{"number": n, "raw": t} for n, t in pdf_entries]
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".bib":
        return parse_bib(p)
    if suf == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        entries = []
        for i, d in enumerate(data):
            num = int(d.get("number", i + 1))
            raw = d.get("raw") or f"{d.get('authors','')} {d.get('title','')} {d.get('year','')}"
            entries.append((num, raw))
            d["number"] = num
            d["raw"] = raw
        return entries, data
    return parse_txt_refs(p)


def split_bib_entry(raw):
    """把一条书目原文拆成 (authors, title, venue)。

    原实现用 `^(.*?)\\.\\s` 取作者 —— 非贪婪，遇到 "M. Zaheer, S. Kottur, ..."
    这类缩写起头的条目只截到 "M"，导致作者、题名双双退化（题名兜底是 raw[:120]，
    实测 ICLR 稿的 57 条里题名字段全是整条书目原文）。
    现在：作者区截止到**第一个**满足「位置 ≥12 且句号前不是单个大写缩写」的 ". "。
    """
    s = (raw or "").strip()
    def _cut(text, start=0):
        for m in re.finditer(r'\.\s+', text):
            i = m.start()
            if i < start:
                continue
            if i >= 1 and text[i - 1].isalpha() and text[i - 1].isupper() \
                    and (i < 2 or text[i - 2] in ' ,'):
                continue                       # 缩写首字母 "A. / S. "
            return i
        return None
    c1 = _cut(s, start=12)
    if c1 is None:
        return s[:80], s[:120], ""
    authors = s[:c1].strip()
    rest = s[c1 + 1:].strip()
    c2 = _cut(rest, start=6)
    if c2 is None:
        return authors, rest, ""
    return authors, rest[:c2].strip(), rest[c2 + 1:].strip()


def enrich_ref_fields(meta_list):
    """从条目原文里补出 year / 作者串 / 短标题。"""
    for e in meta_list:
        raw = e.get("raw", "")
        if not e.get("year"):
            ys = re.findall(r'(?:19|20)\d{2}', raw)
            e["year"] = ys[-1] if ys else ""
        au, ti, ve = split_bib_entry(raw)
        # 保护：拆出来的题名几乎不含字母（多半是纯年份/纯标点）说明切点找错了，
        # 此时退回旧行为，避免标题退化成 "2023."
        if len(re.findall(r'[A-Za-z\u4e00-\u9fff]', ti or "")) < 3:
            ti = raw[:120]
        if not e.get("authors") or len(str(e.get("authors"))) < 6:
            e["authors"] = au
        if not e.get("title") or len(str(e.get("title"))) >= min(len(raw), 120):
            e["title"] = ti
        if not e.get("venue"):
            e["venue"] = ve
        a1 = re.split(r'[,;]', str(e.get("authors", "")))[0].strip()
        e["short"] = (a1 or raw[:24])[:28]
    return meta_list


# ---------------------------------------------------------------- 功能分类

# (类别, 正则, 权重)
CUE_RULES = [
    ("指出局限", r'\b(limitation|drawback|shortcoming|weakness|fail(s|ed)? to|'
                 r'cannot|unable to|suffer(s)? from|lack(s|ing)?|only (?:work|applie|consider)|'
                 r'ignor\w+|assum\w+ that|limited to|inadequat\w+|poor|suboptimal)\b|'
                 r'局限|不足|缺[点陷]|未能|难以|无法|忽视|假[设定]', 3),
    ("对比/分歧", r'\b(however|unlike|in contrast|contrary|whereas|on the other hand|'
                  r'differ\w+|disagree\w+|debate|conflict\w+|argue[sd]?|challenge[sd]?|'
                  r'contradict\w+|outperform\w+|rather than|instead of|but not)\b|'
                  r'然而|但[是]?|不同于|相反|与之相比|争议|存在分歧|挑战|反驳', 3),
    ("方法改进/演进", r'\b(extend\w*|improv\w*|variant of|generaliz\w+|advance\w*|'
                     r'refine\w*|build(s|ing)? on|successor|surpass\w*)\b|'
                     r'改[进良]|扩展|推广|衍生|在.{0,10}基础上', 3),
    ("佐证实验结果", r'\b(consistent with|in line with|confirm\w+|corroborat\w+|'
                    r'as (?:reported|observed|shown) (?:by|in)|reproduc\w+|replicat\w+|'
                    r'similar (?:result|trend|observ\w+)|agree\w+ with|empirically)\b|'
                    r'与.{0,8}一致|验证|证[实明]|复现|同样地观察到|结果表[明]', 3),
    ("方法来源", r'\b(we (?:use|adopt|employ|follow|apply|leverage)|'
                 r'based on|following|using the (?:method|approach|framework|architecture|model) of|'
                 r'as in|according to the method|the method of|implemented (?:by|as)|we follow)\b|'
                 r'我们?采用|我们?使用|基于.{0,10}方法|按照|沿用', 3),
    ("数据与资源", r'\b(dataset|benchmark|corpus|database|suite of tasks|evaluation (?:set|protocol))\b|'
                   r'数据集|基准|语料|评测集', 2),
    ("工具与实现", r'\b(library|toolkit|package|framework|code (?:is|available)|implementation of|'
                   r'we use the .{0,20}(?:library|toolbox)|pytorch|tensorflow)\b|'
                   r'工具[包库]|代码|开源实现', 2),
    ("理论基础", r'\b(theory|theorem|lemma|proof|formal\w*|it (?:has been|is) (?:shown|proved|established)|'
                 r'classical|seminal|pioneer\w+|foundation|grounded in|rooted in)\b|'
                 r'定理|引理|证明|理论|经典|奠基', 2),
    ("背景综述", r'\b(related work|previous work|prior work|literature|survey|review|'
                 r'have been (?:proposed|studied|explored)|a (?:large|growing) body)\b|'
                 r'已有研究|相关工作|综述|文献', 1),
]

SECTION_PRIOR = {
    "related": "背景综述", "background": "背景综述", "introduction": "背景综述",
    "method": "方法来源", "approach": "方法来源", "model": "方法来源", "framework": "方法来源",
    "experiment": "佐证实验结果", "result": "佐证实验结果", "ablation": "佐证实验结果",
    "discussion": "对比/分歧", "limitation": "指出局限", "conclusion": "对比/分歧",
}

FUNC_ORDER = ["方法改进/演进", "理论基础", "方法来源", "对比/分歧", "佐证实验结果",
              "指出局限", "数据与资源", "工具与实现", "背景综述", "未分类"]


def classify(sentence, section):
    """返回 (功能, 置信度 0-1)。规则优先，章节其次。"""
    low = sentence.lower()
    scores = {}
    for cat, pat, w in CUE_RULES:
        hits = len(re.findall(pat, low))
        if hits:
            scores[cat] = scores.get(cat, 0) + w * min(hits, 2)
    sec_low = (section or "").lower()
    for key, cat in SECTION_PRIOR.items():
        if key in sec_low:
            scores[cat] = scores.get(cat, 0) + 1.0
            break
    if not scores:
        return "未分类", 0.2
    best = max(scores.items(), key=lambda kv: (kv[1], -FUNC_ORDER.index(kv[0])))
    total = sum(scores.values())
    conf = round(min(0.95, 0.4 + 0.6 * best[1] / max(total, 1)), 2)
    return best[0], conf


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--refs", default=None, help="BibTeX / txt / json 参考文献列表")
    ap.add_argument("--style", default="auto",
                    choices=["auto", "numeric", "paren", "authoryear"])
    ap.add_argument("--out", default="citetool_out")
    ap.add_argument("--appendix", action="store_true",
                    help="参考文献区之后继续扫描附录（启发性证据常藏在这里的对比讨论里）")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    units = extract_units(args.pdf)
    full, offsets, pages = build_body(units)
    heads = find_headings(units, offsets)
    head_off = [h[0] for h in heads]

    def page_at(pos):
        i = bisect.bisect_right(offsets, pos) - 1
        return pages[max(i, 0)]

    def section_at(pos):
        i = bisect.bisect_right(head_off, pos) - 1
        return heads[i][1] if i >= 0 else "(正文开头)"

    refs_pairs, refs_meta = load_refs(args.refs, parse_refs_from_pdf(units, offsets))
    refs_meta = enrich_ref_fields(refs_meta)
    ref_map = {int(n): m for n, m in zip([p[0] for p in refs_pairs], refs_meta)}
    print(f"[refs] 载入 {len(ref_map)} 条参考文献")
    ay_index = build_ay_index(ref_map)

    style = args.style
    if style == "auto":
        head = full[:max(2000, len(full) // 3)]
        n_bracket = len(NUM_MARK.findall(head))
        nums = paren_nums(head)
        n_paren = len(nums)
        # 作者-年命中数必须与括号数字竞争：数学/理论稿的公式编号 "(1)(2)(3)" 会大量
        # 命中括号数字，只看 n_paren 会把 authoryear 稿误判成 paren（实测 DiffLift 就是这样
        # 从 82 条上下文掉到 11 条）。
        na = len(re.findall(r'et al\.\s*\(\d{4}\)'
                            r'|\(\s*[A-Za-z][^)]{0,60}(?:19|20)\d{2}\s*\)', head))
        if n_bracket >= 5 or n_bracket >= n_paren:
            style = "numeric"
        elif n_paren >= 5 and n_paren > na and not looks_like_eq_numbering(nums):
            style = "paren"
        else:
            style = "authoryear"
    print(f"[style] 引用标记类型: {style}")

    ref_rng = find_ref_range(units)
    ref_start_off = offsets[ref_rng[0]] if ref_rng else None
    body_last = len(units) if args.appendix else (ref_rng[0] if ref_rng else len(units))

    rows, contexts, seen_ctx, all_sents = [], [], set(), []
    seen_ref = {}
    cur_section = "(正文开头)"

    for i, (pno, line) in enumerate(units):
        if ref_rng and ref_rng[0] <= i < ref_rng[1]:
            # 参考文献区本体：不参与正文抽取（但 --appendix 时会越过它继续往后扫）
            if not args.appendix:
                break
            cur_section = "APPENDIX（附录）"
            continue
        if i >= body_last:
            break
        if looks_like_heading(line):
            cur_section = line.strip()
            continue
        page, section = pno, cur_section
        for stext in split_line_sentences(line):
            if not stext:
                continue
            sent_idx = len(all_sents)
            all_sents.append({"idx": sent_idx, "page": page, "section": section,
                              "text": stext, "refs": []})
            marks = []
            if style in ("numeric", "auto"):
                for m in NUM_MARK.finditer(stext):
                    for tok in re.split(r'\s*[,;，、]\s*', m.group(1)):
                        if re.fullmatch(r'\d{1,3}', tok.strip()):
                            marks.append(int(tok))
                        else:
                            r = re.match(r'(\d{1,3})\s*[-–—|-]\s*(\d{1,3})', tok)
                            if r:
                                marks.extend(range(int(r.group(1)), int(r.group(2)) + 1))
            elif style == "paren":
                # 括号数字必须落在书目编号范围内，否则是年份/统计数字（如 "(2024)"、"(n = 5)"）
                upper = max(len(ref_map), 1)
                for m in PAREN_NUM_MARK.finditer(stext):
                    for tok in re.split(r'\s*[,;，、]\s*', m.group(1)):
                        tok = tok.strip()
                        if re.fullmatch(r'\d{1,3}', tok) and 1 <= int(tok) <= upper:
                            marks.append(int(tok))
                        else:
                            r = re.match(r'(\d{1,3})\s*[-–—|-]\s*(\d{1,3})', tok)
                            if r and int(r.group(1)) <= upper:
                                marks.extend(range(int(r.group(1)),
                                                   min(int(r.group(2)), upper) + 1))
            if style == "authoryear":
                marks.extend(match_ay(stext, ref_map, ay_index))
            all_sents[sent_idx]["refs"] = sorted(set(marks))
            for rid in sorted(set(marks)):
                meta = ref_map.get(rid)
                if meta is None and 1 <= rid <= len(ref_map):
                    meta = {"number": rid, "raw": "", "short": f"[{rid}]", "year": ""}
                    ref_map[rid] = meta
                if meta is None:
                    continue
                dedup = (rid, page, stext)
                if dedup in seen_ctx:
                    continue
                seen_ctx.add(dedup)
                func, conf = classify(stext, section)
                seen_ref[rid] = seen_ref.get(rid, 0) + 1
                rows.append({
                    "ref_id": rid,
                    "参考文献": meta.get("short", f"[{rid}]"),
                    "年份": meta.get("year", ""),
                    "章节": section,
                    "页码": page,
                    "引用功能(自动)": func,
                    "置信度": conf,
                    "上下文原文": stext,
                    "支撑的具体观点(待补)": "",
                })
                contexts.append({
                    "ref_id": rid, "page": page, "section": section,
                    "sentence": stext, "func": func, "conf": conf,
                    "co_refs": sorted(set(marks) - {rid}),
                    "sent_idx": sent_idx,
                })

    rows.sort(key=lambda r: (r["ref_id"], r["页码"]))
    print(f"[ctx] 抽取引用上下文 {len(rows)} 条，覆盖 {len(seen_ref)} 篇参考文献")

    fieldnames = ["ref_id", "参考文献", "年份", "章节", "页码",
                  "引用功能(自动)", "置信度", "上下文原文", "支撑的具体观点(待补)"]
    with open(out_dir / "citation_support.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    md = ["# 引用 — 观点支撑对照表\n",
          f"> 论文：`{Path(args.pdf).name}`　引用标记类型：{style}\n",
          "> 「支撑的具体观点」一列需人工逐条补写；自动分类只是初筛，务必回看上下文。\n",
          "| ref | 参考文献 | 年份 | 章节 | 页 | 功能(自动) | 置信度 | 上下文原文 | 支撑的具体观点(待补) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ctx = r["上下文原文"].replace("|", "/")
        ctx = ctx if len(ctx) <= 220 else ctx[:220] + "…"
        md.append(f"| {r['ref_id']} | {r['参考文献']} | {r['年份']} | {r['章节']} | {r['页码']} "
                  f"| {r['引用功能(自动)']} | {r['置信度']} | {ctx} |  |")
    (out_dir / "citation_support.md").write_text("\n".join(md), encoding="utf-8")

    nodes = []
    for rid, meta in sorted(ref_map.items()):
        nodes.append({
            "id": rid,
            "label": meta.get("short", f"[{rid}]"),
            "raw": meta.get("raw", ""),
            "year": meta.get("year", ""),
            "title": meta.get("title", ""),
            "authors": meta.get("authors", ""),
            "venue": meta.get("venue", ""),
            "doi": meta.get("doi", ""),
            "times_cited": seen_ref.get(rid, 0),
        })
    (out_dir / "refs_nodes.json").write_text(
        json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "contexts.json").write_text(
        json.dumps(contexts, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "sentences.json").write_text(
        json.dumps(all_sents, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps({"pdf": str(args.pdf), "style": style,
                    "n_refs": len(ref_map), "n_ctx": len(contexts),
                    "n_sent": len(all_sents)}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"[out] {out_dir/'citation_support.csv'}")
    print(f"[out] {out_dir/'citation_support.md'}")
    print(f"[out] {out_dir/'refs_nodes.json'}")
    print(f"[out] {out_dir/'contexts.json'}")
    print(f"[out] {out_dir/'sentences.json'}  ({len(all_sents)} 句，供 seedfinder 取跨句动机语境)")


if __name__ == "__main__":
    main()
