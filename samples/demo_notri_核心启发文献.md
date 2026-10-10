# 《No Triangulation Without Representation: Generalization in Topological Deep Learning》核心启发文献

> 样本：arXiv 2605.06467（2026），21 页，`[n]` 制，参考文献 42 条。
> 流程：v2（`autorun.py --force`）→ 闸口 → A3 人工裁决。
> **把握度：中**（闸口 C4 未过 + Top1/第4名 1.63 < 2.0 + `--force`，按 R14 已下调一档）。

---

## 一、机器初筛结果（未经人工修正）

```
[S3] refs=42 ctx=52 被引=37
[S4] C1=OK | C2=OK | C3=OK | C4=FAIL(章节2 引言✓ 相关工作✗ 最大占比47/52) | C5=OK | C6=OK
[S6] Top1/第4名=1.63 → 排序仅用于圈定候选，必须人工裁决
```

| 机器排名 | 编号 | 分数 | 机器判定角色 | 人工裁决 |
|---|---|---|---|---|
| 1 | [5] CW Networks (Bodnar 2021) | 13.44 | 揭示研究空白 | **降级** → 实为被修补的基线 |
| 2 | [16] Topological blindspots (Eitan 2025) | 12.46 | 揭示研究空白 | ✅ 保留，第 2 席 |
| 3 | [29] Pachner 1991 | 11.04 | 数据与资源 | ✅ 保留，第 3 席 |
| 4 | [2] MANTRA (Ballester 2025) | 8.24 | 数据与资源 | **上调** → 实为第 1 席 |

---

## 二、裁决后的三篇核心启发文献

### 第 1 席：[2] MANTRA: The manifold triangulations assemblage

R. Ballester, E. Röell, D. B. Schmid, M. Alain, S. Escalera, C. Casacuberta, B. Rieck. ICLR 2025.

**本文与它的关系：直接母体。** 作者名单里的 Ernst Röell 与 Bastian Rieck 同时是本文作者——这是同一组的延续工作。

**原文支撑：**

> "The MANTRA dataset **[2]** addresses this gap, being the only dataset consisting of inherently higher-order objects, namely combinatorial manifolds. **However, despite providing suitable data, we find that the original MANTRA dataset has several shortcomings in its evaluation methodology, which we address in this work.**"（引言，p.3）

> "**In this work, we extend MANTRA**, a benchmark dataset containing manifold triangulations, to a larger class of manifolds with more diverse homeomorphism types."（引言，p.2）

> "However, **one of the main limitations of MANTRA** is the lack of homeomorphism type labels. In the 2-dimensional part of the dataset, only four manifold types were labeled, leaving 80% of triangulations unlabeled."（p.3）

本文的第一个贡献就是扩展它，研究空白也直接从它的缺陷里来。

> ⚠️ **机器为什么漏判**：`[2]` 出现 4 次（全场最高之一），但 `RESOURCE`（数据与资源）线索给了 **−4.18** 的重罚，把它压到第 4。
> 教训：**"数据集/基准类文献"不等于"背景资源"**——当本文的立足点就是一个数据集时，那个数据集就是核心启发。
> 这条值得考虑写进 SOP 作为 R17。

---

### 第 2 席：[16] Topological blindspots（Eitan et al., ICLR 2025）

Y. Eitan, Y. Gelberg, G. Bar-Shalom, F. Frasca, M. M. Bronstein, H. Maron. *Topological blindspots: Understanding and extending topological deep learning through the lens of expressivity.* ICLR 2025.

**本文与它的关系：站在它肩膀上再推一步。** 它证明 HOMP 学不到某些不变量，本文证明 HOMP 连**理论上能算的**都学不到。

**原文支撑：**

> "In a sense, this **complements the findings by Eitan et al. [16]**, who point out that HOMP models cannot learn certain invariants—**whereas we demonstrate that they do not even learn the ones that they are (theoretically) capable of learning.**"（§5 Discussion, p.10）

> "...leading to criticism concerning the necessity of higher-order representations [32] as well as **concerns about the theoretical expressivity of HOMP [16]**."（引言, p.3）

---

### 第 3 席：[29] Pachner moves（Pachner 1991）

U. Pachner. *P.L. homeomorphic manifolds are equivalent by elementary shellings.* European Journal of Combinatorics, 12(2):129–145, 1991.

**本文与它的关系：方法论工具的直接来源。** 本文的核心工具（用 Pachner moves 生成同胚类型已知的三角剖分）来自这篇 1991 年的组合拓扑经典。

**原文支撑：**

> "• We extend the MANTRA dataset with a fully-characterized set of triangulations in dimensions 2 and 3, **establishing Pachner moves [29]**, i.e., local modifications preserving the homeomorphism type, **as principled data augmentation and evaluation tools**."（贡献列表第 1 条, p.3）

> "To address the dataset imbalance, we need to be able to create new triangulations with known homeomorphism types. We thus employ Pachner moves and connected sums."（p.4）

---

## 三、被机器排第一、人工降级的：[5] CW Networks

Bodnar et al., NeurIPS 2021。机器给了 13.44 分（GAP 线索命中 3 次），但回原文看语境：

> "For greater (combinatorial) expressivity, CIN [5] and CXN [18] operate on cell complexes. **CIN's implementation is memory inefficient and CXN provides none.**"（p.7）

> "Approaches based on the Augmented Hasse diagram, such as GCCN [31] and SMCP [16] are **infeasible to run** on datasets beyond the small TUDatasets [26]."（p.7）

这些 `GAP` 线索命中的是"**现有实现有缺陷**"，即本文要修补的对象——属于**被对比的基线**，不是启发源。机器只看线索词、不看"缺陷属于谁"，就会把"被批评得最多的那篇"排到第一。

> 这正是 R2 阈值（Top1/第4名 ≥ 2.0 才允许用排序定序）存在的意义。本篇比值 1.63，正确触发了人工裁决。

---

## 四、复现命令

```bash
PY="<PY>"
cd <SKILL_DIR>/scripts

$PY autorun.py "<PDF_DIR>/2605.06467.pdf" --out demo_notri --expect 42 --force
# 然后读 demo_notri/seeds_evidence_pack.md 做 A3 裁决
```
