# 两种流程对比测试：lit 库三篇不同主题样本

> 测试日期：2026-10-10　工具：`citetool/`（citeparse + seedfinder + autorun）
> 目的：在同一代码版本下，用**v1 分步流程**与**v2 一键流程**各跑三篇不同主题的论文，比对结论一致性、轮次与上下文开销。

---

## 一、样本选择

从 `<LITDB>`（本机的 lit.db）（3051 篇，2571 篇 PDF 实际存在）中挑选，标准是**主题跨度大 + 书目版式跨度大**，以压力测试解析器：

| 编号 | 论文 | 主题 | 书目制式 | 规模 |
|---|---|---|---|---|
| **P1** | Leinster, *The magnitude of a graph* (2014, arXiv:1401.4623) | 纯数学（magnitude 不变量） | `[n]` 方括号 | 19 页 / 22 条 / 23 上下文 |
| **P2** | Nakai et al., *Distinct manifold encoding… subiculum and hippocampus* (Sci. Adv. 2024) | 计算神经科学（海马表征几何） | **`1.` 裸数字 + 正文 `(31)` 括号数字** | 17 页 / 82 条 / 195 上下文 |
| **P3** | Li et al., *Visualizing the Loss Landscape of Neural Nets* (NeurIPS 2018) | 深度学习（损失景观几何） | `[n]` 方括号 | 18 页 / 42 条 / 60 上下文 |

三个主题彼此无交集（代数不变量 / 在体电生理 / 优化与泛化），版式覆盖三种主流制式。

> 备选 Courellis et al. (Nature 2024) 被弃用：该 PDF 全文无 "References" 字样，只有正文 + Extended Data + Reporting Summary，**书目被从 PDF 里裁掉了**，不适合做本测试（记入异常表）。

---

## 二、执行记录

### v1（分步：citeparse → 闸口检查 → seedfinder → 读证据包 → 裁决）

| 步骤 | P1 | P2 | P3 |
|---|---|---|---|
| S1 citeparse | 1 | 1（→0 条，诊断） | 1 |
| S2 读 meta / 章节分布 | 2 | 2 | 2 |
| S3 诊断修复 | 1 | 2 | 1 |
| S4 seedfinder | 1 | 1 | 1 |
| S5 读 ranked.csv + evidence_pack | 1 | 1 | 1 |
| **合计** | **6** | **7** | **5** |

稳态（不计首次遇到的缺陷修复）：P1 6 / P2 4 / P3 5 = **15 轮**。

### v2（autorun 一键）

| | P1 | P2 | P3 |
|---|---|---|---|
| autorun 默认 | 1（C4 FAIL） | 1（全绿） | 1（C4 FAIL） |
| `--force` 续跑 | 1 | — | 1 |
| **合计** | **2** | **1** | **2** |

**合计 5 轮**。

### 开销对比

| 指标 | v1 | v2 | 变化 |
|---|---|---|---|
| 轮次（稳态 3 篇） | 15 | 5 | **−67%** |
| agent 读入字节 | ≈22 KB（3 份 evidence_pack + csv） | 7.9 KB（2684+2409+2801） | **−64%** |
| 折合 token/篇 | ~25–35k | ~8–12k | **约 −65%** |

---

## 三、结论一致性：三篇全部逐项相同

两流程在**同一代码版本**下产出完全一致的中间量与排序：

| 项 | P1 v1 / v2 | P2 v1 / v2 | P3 v1 / v2 |
|---|---|---|---|
| 参考文献数 | 22 / 22 | 82 / 82 | 42 / 42 |
| 上下文数 | 23 / 23 | 195 / 195 | 60 / 60 |
| 被引覆盖 | 17 (77%) / 同 | 82 (100%) / 同 | 42 (100%) / 同 |
| Top1 | [22] 11.09 / 同 | [31] 11.59 / 同 | [13] 13.34 / 同 |
| Top2 | [17] 8.61 / 同 | [48] 9.45 / 同 | [21] 13.27 / 同 |
| Top3 | [15] 6.56 / 同 | [58] 9.39 / 同 | [24] 10.19 / 同 |
| Top1/第4名 | 2.05 / 同 | 1.24 / 同 | 1.48 / 同 |
| R2 判定 | 可定序 / 同 | 须人工裁决 / 同 | 须人工裁决 / 同 |

**v2 没有改动任何判据、阈值或打分逻辑**，只把 S1–S6 折叠进一个入口，并在报告里补了逐字证据句。省的是轮次，不是信息。

---

## 四、三篇的核心启发文献（人工裁决，两流程一致）

### P1 · The magnitude of a graph

| 席位 | 文献 | 把握 | 逐字证据 |
|---|---|---|---|
| 1 | **[22]** Willerton, *Re: Tutte polynomials and magnitude functions*（博客评论） | 中（`--force` 降档） | "This was **conjectured by Willerton** [22]."（本文第二主定理 5.2）；"the first example of such a pair was **found by Willerton** [22]" |
| 2 | **[17]** Speyer, 同题评论 | 中 | "This strategy … was **suggested by Speyer** [17]" |
| 3 | **[8]** Leinster, *The magnitude of metric spaces* (2013) | 中低（隐性传承） | "The full definition of magnitude is framed in the very wide generality of enriched categories [8]" |

注：本文两个主定理之一来自博客评论区而非期刊论文，机器排序把它排到第一是对的——**启发强度与文献正式程度无关**。

### P2 · Distinct manifold encoding (Sci. Adv. 2024)

| 席位 | 文献 | 把握 | 逐字证据 |
|---|---|---|---|
| 1 | **[31]** Kitanishi et al., *Robust information routing by dorsal subiculum neurons* (Sci. Adv. 2021) | 高 | "In contrast to such representations at the single-neuron level, **data for this at the population level remain limited**"（紧跟 [31] 之后，本文 gap 的直接来源）；讨论部分两处 "consistent with / differs from the present result" |
| 2 | **[48]** Nieh et al., *Geometry of abstract learned knowledge in the hippocampus* (Nature 2021) | 中高 | "Neural manifolds in the CA1 … an accumulating-tower task in a virtual space (48) represent physical and abstract variables" |
| 3 | **[47]** Rubin et al. (Nat. Commun. 2019) | 中 | 同句中的 CA1 流形线性轨道任务研究 |

### P3 · Visualizing the Loss Landscape (NeurIPS 2018)

| 席位 | 文献 | 把握 | 逐字证据 |
|---|---|---|---|
| 1 | **[13]** Goodfellow et al., *Qualitatively characterizing neural network optimization problems* (ICLR 2015) | 高 | "The 1D linear interpolation method **suffers from several weaknesses** … Indeed, Goodfellow et al. [13] found that loss functions appear to lack local minima along the minimization trajectory" |
| 2 | **[21]** Im et al., *An empirical analysis of deep network loss surfaces* (2016) | 中高 | "the filter-wise normalization is **different from that of [21]**"（本文方法与其明确区分） |
| 3 | **[24]** Keskar et al., *On large-batch training for deep learning* (2017) | 中 | "As observed by [24], the small-batch solution is quite wide, while the large-batch solution is sharp" |

**三篇的机器 Top1 与人工第一席全部吻合。** 且 P2/P3 的 Top1/4 比值（1.24、1.48）均 < 2.0，R2 阈值正确触发"必须人工裁决"——上一轮测试中"机器会把真正灵感来源排到第 2"的情况，这次靠比值预警 + 逐字证据避免了误信排序。

---

## 五、本轮暴露的缺陷（D3–D9）

### 已修复（5 项）

| ID | 症状 | 影响样本 | 修复 |
|---|---|---|---|
| **D3** | C3 阈值 `1.2×n_refs` 对短文（<25 条）过严 | P1（23 < 26.4） | `n_refs<25` 时降到 `1.0×` |
| **D5** | 书目标题 `REFERENCES AND NOTES`（Science 系列）不识别 → 0 条 | P2 | `REF_SECTION_RE` 增加 `and notes` 分支 |
| **D6** | 裸数字编号书目 `1. Author…` 不识别 → 条目粘成 2 条 | P2（82→2） | 新增 `parse_refs_bare_numbered()`，编号必须递增（防正文编号列表误判），条目数 <5 时回退原逻辑 |
| **D7** | 正文括号数字引用 `(31)` / `(42–49)` 不识别 → 0 条上下文，制式误判为 authoryear | P2（195→0） | 新增 `paren` 制式 + `PAREN_NUM_MARK`，编号须落在书目范围内（排除 `(2024)` 年份、`(n = 5)` 统计量） |
| **D8** | C4 要求"引言 **且** 相关工作"章节齐备，Science/Nature/数学稿无独立相关工作 → 必然 FAIL | P2、P1、P3 | 改为"引言 **或** 相关工作"有其一即可 |

### 修复过程中自己引入并已修（1 项）

| ID | 症状 | 修复 |
|---|---|---|
| **D9** | autorun 的制式推测未同步 `paren`，且数学论文的公式编号 `(1)` 大量命中括号数字 → P1 被误判为 paren（C5 WARN） | 方括号 `[n]` 命中 ≥5 时优先判 numeric，括号数字仅在其缺席时启用 |

### 已知未修（1 项，影响面最大）

| ID | 症状 | 影响 |
|---|---|---|
| **D4** | **章节标题的编号与标题分居两行**（LaTeX 双栏与数学论文的常见文本层表现）时识别失败：<br>`1⏎Introduction`、`2⏎Theoretical Background` | P1：518 句中 512 句归为 Introduction；P3：285 句中 270 句归为 Introduction。**章节权重（SEC_BASE）实质失效**，闸口 C4 报警 |

**为什么先不修**：可行判据是"孤立编号行 + 下一行像标题 + 编号递增"，但实测 P3 第 4–7 页的图区存在 `5⏎Loss`、`100⏎Accuracy` 这类坐标轴标签，形状与真章节标题难以区分（`Loss` 与 `Conclusion` 同为单词、首字母大写、无句号）。误判会把图注当成章节，**比现在的失效更危险**——现在至少由 C4 报警、人工介入。

**降损方案（已验证有效）**：P1/P3 在章节权重失效的情况下，机器 Top1 依然命中正确（靠线索词得分 + 出现次数），说明 SEC_BASE 是增强项而非决定项。C4 报警后按 SOP 处理即可。

### 再次被印证的老缺陷

- **D1（题录字段错位）**：P1 的 [22]/[12] 题名均为 "Re: Tutte polynomials…"（同一条被拆）、[17] 的题名字段是 "Comments at"；P2 的 [31] 题名="Sci. Adv"、[48] 题名="Nature 595, 80–84 (2021)"（**出处被当成题名**）。R15「题录一律取 `raw`」必须执行，否则裁决时会拿着错字段下判断。

---

## 六、结论

1. **v2 可以替代 v1 做常规单篇处理**：三篇不同主题、不同版式下结论逐项一致，轮次 −67%、上下文开销 −64%。v1 保留为排障版（需要单独重跑某一步、或要调 `--refs`/`--style`/`--appendix` 时用）。
2. **闸口仍然有用**：三篇里 P2 触发 0 次失败、P1/P3 各触发 1 次（均为 C4-D4），报警原因可解释、可预期，没有静默出错。
3. **纯数学稿要额外留意**：`--force` 后把握度整体降一档是必要的——P1 的启发文献是博客评论，题录字段本身也不规整。
4. **建议后续**：修 D4 需要图区/正文区的版面区分（如按字号或文本块 bbox 判断），建议单独开一轮做，修完用本次三篇 + 既有三篇（NEXP / DiffLift / GSVD / IDM）做回归。
