# 文件夹模式实测：magnitude 专题 5 篇的核心启发文献

> 输入：`<PDF_DIR>/`（该目录共 18 篇，本次取前 5 篇）
> 流程：`batchrun.py --dir` → `review.py`（裁决工作台）→ 逐篇 A3 裁决
> **每篇都走了完整流程（含人工裁决）**，不是初筛。

---

## 汇总

| # | 论文 | 书目/上下文 | 比值 | 机器 Top1 | 裁决后 | 是否改判 |
|---|---|---|---|---|---|---|
| 001 | Asymptotic Magnitude (Leinster & Willerton) | 20 / 45 | 1.83 | [15] Meckes | **[13] Leinster → [17] Solow&Polasky** | ✅ 改判（反向引用） |
| 002 | Magnitude of Spheres/Surfaces (Willerton) | 15 / 47 | 1.46 | [14] Spread | **[7] Leinster&Willerton**（[14] 并列） | ⚠️ 部分改判 |
| 003 | The Magnitude of a Graph (Leinster) | 22 / 23 | 2.05 | [22] Willerton | **[22] Willerton ✅ 维持** | — |
| 004 | Magnitude of Metric Spaces（综述） | 41 / 105 | 1.33 | [28] Meckes | **[19] Leinster**（[28] 第 2） | ⚠️ 改判 |
| 005 | Magnitude of Odd Balls via Hankel | 26 / 47 | 2.29 | [3] Barceló & Carbery | **[3] ✅ 维持**（有 "inspired by"） | — |

5 篇里 **3 篇需要人工干预**（机器 Top1 不可直接采信），与「6/8 篇比值 <2.0」的既往统计一致。

---

## 001 · On the Asymptotic Magnitude of Metric Spaces

Leinster & Willerton（即 002、003 作者的前作）。书目 20 / 上下文 45 / 比值 1.83。

### ❌ 机器 Top1 [15] Meckes —— 反向引用，已降级

证据句：

> "Motivated by our work, Meckes **[15]** proved that this was indeed the case and that
> our methods do indeed give unique results."

**这是本文启发了 Meckes，不是 Meckes 启发了本文。** `INSPIRE` 线索只看 "motivated by" 这个
短语、不判方向，就会把本文的**下游**文献排到第一。

> 🆕 这条值得立为 **R19**：`INSPIRE` 线索不判方向。
> "Motivated by our work, X…" / "Following our paper, X…" 指的是**本文的下游**，应剔除。

### 裁决

1. **[13] T. Leinster, The magnitude of metric spaces**（作者自己前作）
   本文是它的延续——从"有限度量空间的 magnitude"推进到"紧空间的渐近 magnitude"。
   角色在机器判定里是"作为对比基线"（11.99，出现 6 次），但它是本文的理论前提。
2. **[17] A. Solow & S. Polasky, Measuring biological diversity (1994)**
   > "The magnitude of a finite metric space actually **first appeared in the biodiversity
   > literature [17]**, under the name 'effective number of species'。"
   概念的**起源文献**。本文把它从生态学里抽出来做数学理论。
3. **[20] S. Willerton, On the magnitude of spheres, surfaces and other homogeneous spaces**
   合作者的前作，本文的计算方法与之同源。

---

## 002 · On the Magnitude of Spheres, Surfaces and Other Homogeneous Spaces

S. Willerton。书目 15 / 上下文 47 / 比值 1.46。

| 候选 | 分数 | 次数 | 说明 |
|---|---|---|---|
| [14] Spread（Willerton 自己前作） | 17.21 | 3 | 机器第 1 |
| [13] Heuristic and computer calculations | 16.82 | 9 | 机器第 2 |
| [7] On the asymptotic magnitude（Leinster & Willerton，即 001） | 16.1 | **14** | 机器第 3 |

**机器给 [14] 第一，但它只出现 3 次；[7] 出现 14 次却排第 3。**

[14] 的证据是"本文方法可推广到 spread"——方向是本文 → spread，属于本文的**外延贡献**，
不是启发源（与 001 的反向引用同型，只是更弱）。

### 裁决（把握度：中）

1. **[7] Leinster & Willerton, On the asymptotic magnitude of metric spaces** —— 被引 14 次，
   是本文最直接的理论前提（本文算球面/曲面，正是 [7] 渐近理论的具体实例）。
2. **[13] S. Willerton, Heuristic and computer calculations** —— 本文的数值方法来源
   （"can be implemented on a computer to obtain approximations… as in [13]"）。
3. **[14] S. Willerton, Spread** —— 本文方法的外延对象。

> ⚠️ 本篇第 1/2 席的判断有主观成分：三篇都是作者自己或合作者的前作，属**自身研究线延续**，
> 严谨说不存在单一的"外部启发源"。若要更确定，需读 Introduction 首段确认本文自我定位。

---

## 003 · The Magnitude of a Graph

T. Leinster。书目 22 / 上下文 23 / **比值 2.05（≥2.0，可定序）**。

### ✅ 维持机器 Top1：[22] S. Willerton, *Re: Tutte polynomials and magnitude functions*

> "Speyer and Willerton showed that even in the case of connected graphs, this last
> hypothesis cannot be dropped **[17, 22]**."
> "This strategy for showing that magnitude is not a specialization of the Tutte polynomial
> was **suggested by Speyer [17]**, and the first example of such a pair was found by
> **Willerton [22]**."

1. **[22] Willerton（博客评论）** —— 本文主定理 5.2 的反例由他给出。
2. **[17] D. Speyer（同为博客评论）** —— 证明策略的提出者。
3. **[15] G.-C. Rota, On the foundations of combinatorial theory I（1964）** —— Möbius 反演，
   本文" enriched category"框架的理论源头。

> 注意 [22]/[17] 都是**博客评论**（n-Category Café），不是正式论文——R16 的正确应用：
> 不要因为题录"不像论文"就剔除。

---

## 004 · The Magnitude of a Metric Space（综述，1606.00095）

书目 41 / 上下文 105 / 比值 1.33（最低，最需人工）。

### ⚠️ 改判：机器 [28] → 人工 [19]

机器给 Meckes [28] 17.52（15 次）第一。它的证据：

> "The paper **[28]** introduced yet another equivalent approach to magnitude for compact
> spaces, which makes magnitude more accessible to a wide variety of analytic techniques."
> "In particular, the topology used in [28] can be dualized… **here we will go straight to
> the dual version**."

→ [28] 是本文采纳的**分析框架/工具**，重要但不是"起源"。

而 [19]（Leinster 自己 2013，10 次）：

> "Shortly thereafter, the paper **[19]** appeared which **laid out for the first time the
> general theory of the magnitude of finite metric spaces**."

### 裁决

1. **[19] T. Leinster, The magnitude of metric spaces (2013)** —— 理论起点。综述的叙事
   （从范畴论到几何测度论）正是从它出发。
2. **[28] M. W. Meckes, Magnitude, diversity, capacities, and dimensions of metric spaces (2015)**
   —— 本文采用的分析框架。
3. **[3] Barceló & Carbery, On the magnitudes of compact sets in Euclidean spaces** —— 8 次，
   几何测度论一侧的关键前作。

---

## 005 · The Magnitude of Odd Balls via Hankel Determinants

书目 26 / 上下文 47 / **比值 2.29（≥2.0，可定序）**。

### ✅ 维持机器 Top1：[3] Barceló & Carbery

证据是**明确的 "inspired by"**，方向正确：

> "A key ingredient will be what is basically a special function identity, which we shall
> prove in Section 3 using **PDE methods inspired by [3]**."

1. **[3] J. A. Barceló & A. Carbery, On the magnitudes of compact sets in Euclidean spaces**
   —— 12 次，本文 PDE 方法直接来自它。
2. **[20] A. Sokal, Coefficientwise total positivity…（Hankel 矩阵）** —— 本文的
   Hankel 行列式工具来源。
3. **[25] S. Willerton, SageMath worksheet** —— 数值验证来源（非论文，符合 R16）。

> 另注：本文提到 "Magnitude was originally introduced by Leinster [10]"——[10] 是领域奠基，
> 但**不是本文的启发源**（那是领域常识性引用）。这类"领域起源引用"要从候选里剔除。

---

## 本轮暴露的新规则（建议写入 SOP）

| # | 规则 |
|---|---|
| **R19** | **`INSPIRE` 线索不判方向**。"Motivated by our work, X…" / "Following our paper, X…" 指的是**本文的下游**被引，不是启发源。实测 001 的 [15] 因此被误排第一。裁决时对每个 `INSPIRE` 命中都要确认主语是"本文启发了谁"还是"谁启发了本文"。 |
| **R20** | **区分"本文方法的来源"与"本文方法的外延"**。同作者前作常出现在"本文方法可推广到 X"的语境里（002 的 [14]、004 的 [28] 部分），那是本文的**贡献外延**，不是启发源。 |
| **R21** | **"领域起源引用"不是本文的启发源**。如 005 的 [10] Leinster（magnitude 概念首创）、001 的 [17]（概念在生态学的首次出现）——后者**例外**：当本文正是要把某领域的概念移植过来时，那篇起源文献**就是**核心启发。判据：本文是否明确说"这个概念来自 X 领域"。 |
