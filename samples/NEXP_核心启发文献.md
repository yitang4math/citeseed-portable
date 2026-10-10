# 《Weight Importance Is Not Enough: Neural Expressiveness for Model Compression》核心启发文献

- **论文**：Maroudis A.C., Xydis S., Dimitrakopoulos G.，*IEEE TPAMI* 2026（accepted），DOI `10.1109/TPAMI.2026.3734995`
- **规模**：15 页、参考文献 77 篇、正文抽取到引用上下文 **211 条**
- **方法**：`citeparse.py`（抽取）→ `seedfinder.py`（规则排序，77→8）→ **人工/LLM 依据逐字原文裁决**
- 以下每条结论均附**原文逐字引用 + 章节 + 页码**，可回查。

---

## 一、结论速览（按启发强度）

| 排序 | 文献 | 角色 | 把握 |
|---|---|---|---|
| **1** | **[13]** Frankle & Carbin, *The Lottery Ticket Hypothesis*, **ICLR 2019** | 提供理论基础 + 定义研究问题（何时剪枝） | **高** |
| **2** | **[1]** Achille, Rovere & Soatto, *Critical Learning Periods in Deep Networks*, **ICLR 2019** | 提供理论基础（可塑性的时间维度） | **高** |
| **3** | **[45]** Liu, Sun, Zhou, Huang & Darrell, *Rethinking the Value of Network Pruning*, **ICLR 2019** | 揭示研究空白 / 指出 importance 路线的局限 | **中** |

> **关于 1 与 2 的排序**：二者被**同一句话并列点名**为灵感来源，文中没有任何一句单独抬高其一。
> 把它们判为"共同的首要启发源"把握为**高**；但 **1 与 2 之间的先后**把握只有**中**——
> 我按"被使用的深度"排序（[13] 进入方法篇的实验设计，[1] 主要停留在概念层），换个人或换模型可能给出相反次序。

---

## 二、逐篇依据

### 1. [13] Frankle & Carbin —— Lottery Ticket Hypothesis（ICLR 2019）

**它是怎么引发这项研究的**——本文最核心的那句"立论宣言"把它和信息可塑性一起点名：

> "**Inspired by the concepts of "Information Plasticity" [1] and the "Lottery Ticket Hypothesis" (LTH) [13]**, we aim to address the limitations of previous importance-based methods through elaborating the "Expressiveness" criterion in model compression."
> —— *I. INTRODUCTION*, p.2

**它提供了什么**：LTH 主张子网络在初始化时即已存在。本文据此论证——既然"赢票"结构在训练早期就已埋下，那么衡量神经元能否把信息重新分配出去的能力，就应当能**在训练全过程（含早期）**作为压缩准则，而不必等模型训完再看权重大小。

> "It's essential to note that the network's initialization state influences the formation of those paths, which interestingly enables "Expressiveness" to be a fit criterion for compression **during all time instances of a networks' convergence [13]**, setting a baseline for answering the question of "When to prune?" [54]."
> —— *I. INTRODUCTION*, p.2

**渗透程度最深**——它是三篇里唯一进入方法篇实证设计的：

> "This view is consistent with lottery-ticket and weight-rewinding perspectives [13], [14], where useful subnetworks may be partially exposed at initialization and further selected by the training trajectory."
> —— *III. NEURAL EXPRESSIVENESS*, p.6

> "In summary, under the assumption that the selection of hyperparameters remains congruent with the initialization **[13]**, consistent map measurements between initial and final states can effectively evaluate **NEXP's ability to identify winning tickets**."
> —— *Method*, p.13

**把握：高**。4 处引用横跨引言、方法、实验，且参与定义了"何时剪枝"这个本文明确要回答的问题。

---

### 2. [1] Achille, Rovere & Soatto —— Critical Learning Periods in Deep Networks（ICLR 2019）

**同样被上引的那句 "Inspired by" 点名**（*I. INTRODUCTION*, p.2，原文见上）。

**它提供了什么**：信息可塑性理论指出训练早期阶段对最终表征具有决定性作用。本文把它直接翻译成 NEXP 的时间轴依据——既然早期塑形，**早期就足以估计表达力**：

> "**As derived by [1]**, the early training phase of a model is crucial in shaping its expressiveness, with the formation of critical paths —strong connections that determine the "workload distribution"— being particularly significant during these initial stages."
> —— *I. INTRODUCTION*, p.2

> "This suggests that early neural expressiveness can reveal the formation of critical paths, **in line with the critical-learning period view of Achille et al. [1]**."
> —— *III. NEURAL EXPRESSIVENESS*, p.6

**把握：高**。3 处引用，且第 2 处是本文方法章把自己最重要的实证发现归因到它的理论上——这属于强启发证据。

---

### 3. [45] Liu et al. —— Rethinking the Value of Network Pruning（ICLR 2019）

**它揭示了这个领域的研究空白**，是本文转向"非 importance"路线的直接理由：

> "**Liu et al. [45] have also discussed limitations in the perception of importance** within trained models, i.e. **the authors criticize the ability of network's elements importance to generalize to pruned derivatives**, while also **questioning the necessity of training large-scale models prior pruning**."
> —— *I. INTRODUCTION*, p.2

这句位于紧接 "Inspired by [1] & [13]" 之后、提出 Expressiveness 之前的论证位置：先承认 importance 概念本身站不住（[45]），再给出替代准则。

**把握：中**。理由有二：①**全文仅此 1 处引用**，无法像前两篇那样用"跨章节反复出现"来交叉验证；②文章用 "also"（"也已经讨论过"）措辞，属呼应性引用而非"本工作建立在它之上"。
若只能保留 2 篇，这里是最该被舍弃的一篇。

---

## 三、为什么不是分数更高的那几篇

规则层给分最高的是 **[35] Hao Li et al., *Pruning Filters for Efficient ConvNets* (ICLR 2017)** 14.40 分与 **[48] Molchanov et al., *Importance Estimation for Neural Network Pruning* (CVPR 2019)** 14.11 分——**都略高于** [13] 的 14.02。但它们**不是**启发来源，理由：

- 二者几乎全部出现在**批量罗列**中：`"e.g. [26], [38], [48], [74]"`、`"the magnitude of weights [18], [35]"`（单句 7 篇并列）；或实验章节的基线行。
- 它们是本文**要与之划清界限的那一类方法（importance-based）的代表**，属于"论证对象"而非"思想来源"。相关工作中对 [48] 的叙述是纯描述性的事实陈述，无"局限/受启发"评价。
- 分数虚高的机制：引言在它们附近大量使用质疑性语言（"limitations"、"costly"、"challenging"），而那片总的来说是针对整类 importance 方法，不是针对这两篇。

> 这正是排序层与裁决层必须分开的原因：**规则分数衡量的是"这篇文章在争议语境中被提到的密度"，不等于"它启发了本文"。**
> 且本次 Top1 与 Top4 的差距仅约 3% —— 远低于我在 `SEEDFINDER.md` 校验清单里写的"2 倍"阈值。按那份清单，本例的排序**本就不可直接采信**，必须回到原文裁决。

---

## 四、本次实测暴露的工程问题（已全部修复）

真实 PDF 打碎了三个合成测试没覆盖的假设：

| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | **罗马数字章节标题**（`I. INTRODUCTION`）未被识别 | 引言/相关工作共 123 条上下文全落入 `(正文开头)`（权重 1.0），导致 **Method 章节(1.6) 权重反超 Introduction**，把方法篇的基线文献顶到榜首 | 新增 `HEADING_NUM_RE` + `looks_like_heading()`：编号标题按"左栏→右栏、栏内纵向"恢复阅读序，并要求标题主体基本全大写且 ≤12 词，避免图注碎片误判 |
| 2 | **按 PDF 行切句**，而双栏排版换行 ≠ 句末 | `[45]` 那句被切成 `"Liu et al. [45] have also discussed"` + 无引用标记的后半句，`limitations / criticize` 全部线索丢失 → **[45] 掉到第 43 名、3.57 分** | 改用 blocks 提取并**合并行还原段落**（含连字符断词处理）；参考文献区保持行级并按 `[编号]` 重新切条 |
| 3 | 段落合并把 `REFERENCES` 标题行也并掉 | 参考文献解析归零（0/77） | 合并时排除命中 `REF_SECTION_RE` 的行 |
| 4 | **线索正则尾部 `\b` 使复数失效**：`\blimitation\b` 匹配不到 `limitations` | 即便修复了 #2，`[45]` 仍抓不到 GAP 线索；同一问题波及 `drawbacks / shortcomings / uses / adopts` 等一整批词干 | 线索表全部显式携带屈折后缀（`limitations?`、`shortcomings?`、`ignore[sd]?`、`(?:uses\|adopts\|…)`） |

**修复前后**（第几名 / 分数）：

| 阶段 | [13] | [1] | [45] |
|---|---|---|---|
| 原始 | 2 / 9.40 | 4 / 7.97 | 未进前五 |
| + 章节识别 | 1 / 13.41 | 3 / 11.18 | 43 / 3.57 |
| + 段落合并 | 2 / 13.71 | 4 / 11.42 | 25 / 7.36 |
| + 线索复数修复 | 3 / 14.02 | 4 / 11.73 | **10 / 10.47** |

注意 [13] 的名次从 1 退到 3 —— 不是变差，而是它的**绝对分一直在涨**（13.41→14.02），
只是竞品的句子同样被修复、涨得更多。**召回质量提升，但排序的可分离性依然很差**（Top1–Top4 相差 3%），
这再次印证：这套东西的价值在于把 77 篇缩到 8 篇并给出可核查证据，而不是给出那个数字。

---

## 五、证据缺口声明

- **隐性启发无法覆盖**：若某篇文献从未被点名却实际影响了工作，本流程检不出——需外部共引数据，超出"读单篇"的范围。
- 本文 [45] 仅 1 处引用，其"启发强度"缺乏交叉验证。
- 若需更高的确定性，应做的下一步是把 [1]/[13]/[45] 三篇各自 PDF 取来，反向核对它们的**理论主张是否被本文准确继承**（是否存在误读或过度延伸）。
