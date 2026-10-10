# 《Differentiable Lifting for Topological Neural Networks》核心启发文献分析

> 论文：Jorge Luiz Franco, Gabriel Duarte, Alexander Nikitin, Moacir Ponti, Diego Mesquita, Amauri H. Souza
> **Differentiable Lifting for Topological Neural Networks（∂lift / DiffLift）**，ICLR 2026，arXiv:2608.01160
> 分析方式：`citetool` 管线（citeparse + seedfinder）+ 逐条回到原文核验
> 数据规模：58 条参考文献 / 102 条引用上下文（含附录）/ 覆盖 53 篇

---

## 结论速览

| 排序 | 文献 | 年份·出处 | 对本研究的作用 | 把握 | 机器分 |
|---|---|---|---|---|---|
| 1 | **Battiloro et al. — From latent graph to latent topology inference: Differentiable cell complex module（DCM）** | 2024 · ICLR | 揭示研究空白 + 唯一直接基线 | **高** | 15.68 |
| 2 | **Hajij et al. — Topological deep learning: Going beyond graph data** | 2022 · arXiv:2206.00606 | 提供问题框架与术语（为何 lifting 必须被学习） | **中高** | 13.24 |
| 3 | *证据不足，无法确认* | — | 见下文"未定席位"一节 | 低 | — |

**明确排除**（高频但不是启发）：

- **Bodnar et al. 2021a — Weisfeiler and Lehman Go Cellular: CW Networks**：出现 **12 次，全篇最高**，但它是本文的**评估骨干网络与静态 lifting 基线**（"+45%" 就是在 CWN 上取得的），属于论证对象与实验载体，不是思想来源。
- **Papillon et al. 2025 — TopoTune**（机器排第 3，11.03 分）：工具自己标注为"背景罗列（本句无动机线索）"，其证据句 "Papillon et al. (2025) also use GNNs to enhance TDL…" 是呼应性的 "also"，不构成启发。
- **Telyatnikov et al. 2025 — TopoBench**（出现 10 次）：表格分数的数据来源与 benchmark 框架，属资源类引用。

---

## 1. Battiloro et al. 2024 —— 唯一的可微提升工作（把握：高）

**完整题录**：Claudio Battiloro, Indro Spinelli, Lev Telyatnikov, Michael M. Bronstein, Simone Scardapane, and Paolo Di Lorenzo. *From latent graph to latent topology inference: Differentiable cell complex module.* In International Conference on Learning Representations (ICLR), 2024.

**影响类型**：揭示研究空白 + 提供唯一可比对的 prior art（同时是实验基线）。

**逐字原文证据**

1. **引言（Introduction, p.3）** —— 定义本文要填的那个空白：

   > "To date, differentiable lifting has only been explored in the context of cell complexes (Battiloro et al., 2024)."

   "To date" 加 "only been explored"，直接把本文的工作空间界定为 cell complex 之外的所有拓扑域。

2. **引言（Introduction, p.3）** —— 本文自己给它贴的标签：

   > "…∂lift achieves competitive performance relative to static lifting methods and outperforms **DCM (Battiloro et al., 2024) (a differentiable lifting baseline)** overall."

3. **相关工作（4 RELATED WORKS, p.7）** —— 把它放进学习式 lifting 的谱系位置：

   > "This lifting process can be either predefined – e.g., based on structural features like node proximity or the presence of cycles – or **learned directly from the data (Battiloro et al., 2024; Kazi et al., 2022)**."

4. **实验（5.2 NODE CLASSIFICATION, p.9）** —— 唯一的同代 baseline：

   > "We also compare our method (for cell domains) against the learnable approach in (Battiloro et al., 2024), called **Differentiable Cell Complex Module (DCM)**, which was originally evaluated on node classification tasks."

**把握为何是"高"**：四项证据分布在引言、相关工作、实验三个不同章节，且都是含判断的陈述句而非罗列句；其中"a differentiable lifting baseline"和"the learnable approach"是本文给出的**独家身份认定**，不是推测。

---

## 2. Hajij et al. 2022 —— 问题框架与术语来源（把握：中高）

**完整题录**：Mustafa Hajij, Ghada Zamzmi, Theodore Papamarkou, Nina Miolane, Aldo Guzmán-Sáenz, Karthikeyan Natesan Ramamurthy, Tolga Birdal, Tamal K. Dey, Soham Mukherjee 等. *Topological deep learning: Going beyond graph data.* arXiv preprint arXiv:2206.00606, 2022.

**影响类型**：提供研究动机的问题陈述（"lifting 不受任务监督"）+ combinatorial complex 与 cycle lifting 的定义基础。

**逐字原文证据**

1. **引言（Introduction, p.3）** —— 本文的动机句本身（注意与 Telyatnikov et al., 2025 并列）：

   > "Strikingly, **despite the high impact of the lifting operation on TNNs, most lifting methods are not supervised and thus not informed by the task at hand (Hajij et al., 2022; Telyatnikov et al., 2025), which may lead to suboptimal architectures.**"

   这句话决定了本文要做什么：把 lifting 变成受任务监督、端到端可学习的。

2. **引言（Introduction, p.2）** —— 提供具体的 lifting 机制：

   > "…clique lifting (Bodnar et al., 2021b) produces a simplicial complex by leveraging cliques in the input graph while **cycle lifting (Hajij et al., 2022)** detects cycles to create a cell complex."

3. **背景（BACKGROUND, p.4）** —— 提供本文建模对象的形式化定义：

   > "A **combinatorial complex (CC) (Hajij et al., 2022)** is a tuple (V, K, rk) where V is a finite set, K ⊆ 2^V \ ∅ comprises a set of cells, and rk : K → Z≥0 is a ranking function…"

**把握为何降到"中高"**：关键动机句是与 Telyatnikov et al. (2025) **并列**引用，功劳无法单独归给它；它 7 次出现里有 3 次是纯定义性引用；且它本身是定位性综述，本文依赖的是它建立的问题话语而非具体技术。若只能留 1 篇，应留第 1 条。

---

## 3. 未定席位：证据不足

| 候选 | 现有证据 | 缺什么 | 判定 |
|---|---|---|---|
| **Kazi et al. 2022 — Differentiable graph module (DGM) for graph convolutional networks** | p.7："…or **learned directly from the data (Battiloro et al., 2024; Kazi et al., 2022)**" | 仅 2 次出现，其一为 7 篇批量罗列；**本文从未说明继承了它的哪种机制** | `insufficient` |
| **Qian et al. 2024 — Probabilistic graph rewiring via virtual nodes（IPR-MPNN）** | 附录 E.4："…**(iii) Sampling strategy: both use differentiable k-subset sampling**, but IPR-MPNN samples node-to-virtual-node assignments while ∂lift samples which higher-order cells to include…" | 正文只出现 1 次（批量罗列）；整套比较只在**附录**；本文从未承认采样机制源自它 | `insufficient` |
| **Telyatnikov et al. 2025 — TopoBench** | 与上条 #2 同句支撑动机 | 其余出现全是数据来源引用 | 并入 #2，不占第三席 |

---

## 必须知道的两个边界

### ① 分数不能用于细粒度排名

第 1 名 15.68 分 vs 第 2 名 13.24 分，比值 **1.18**，远低于校验清单里自订的"2 倍"可信阈值。按分数，#1 与 #2 的顺序本不可直接采信；本例的最终顺序是靠逐字原文证据敲定的——尤其是 "To date … only been explored" 与 "a differentiable lifting baseline" 这两个**独家表述**。

另外注意：**出现次数最多的文献（Bodnar 2021a，12 次）不是答案，真正的种子只被引用 4 次**。频率与启发强度在本例上呈反向关系。

### ② 附录-only 的隐性启发是结构性盲区

IPR-MPNN 与本文**共用 differentiable k-subset sampling**，且附录 E.4 用一整节讨论二者的四点区别——这是最接近的方法论亲缘线索，却**只存在于附录**。原管线在 REFERENCES 处停止扫描，这类证据天然不可见。

本次为管线新增 `--appendix`：越过参考区继续抽取附录文本，并以 `APPENDIX（附录）` 作为独立章节标注。开启后 IPR-MPNN 从"完全不可见"变为可列出的第 10 名（分数仍低）。

> 任何声称"从引用上下文推断思想来源"的工具，只要不读附录，就一定漏掉这一类。

---

## 本轮测试暴露的工具缺陷（8 个）

上一轮在 IEEE 双栏稿（PAMI）上修过 6 个；这一轮在 ICLR 单栏 LaTeX 稿上又暴露 8 个——**没有一个能在合成样本上复现**。

| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | 参考文献表**无编号**（ICLR/ACL 的作者列表式），而解析器只认 `[n]` 切条 | **0 条参考文献**，整条管线空转 | 新增 `AUTHSTART_RE` + `parse_refs_unnumbered`：按"作者串开头 + 含年份"判定条目边界 |
| 2 | 跨页重复的**页眉**（"Published as a conference paper at ICLR 2026"）未过滤 | 污染每页首段；参考区首条变成 "Published as … Jie Chen, …" 而无法识别 | 统计跨页重复短行，作为装饰性文本剔除 |
| 3 | LaTeX 把**章节编号单独排成一行**（"3" 换行接 "DIFFERENTIABLE LIFTING"） | 方法章标题识别失败，**整章引用被计入 BACKGROUND** | 编号行与紧随其后的一行合并，再交给编号标题正则 |
| 4 | 页码过滤写成"见数字就删"（修 #3 时引入） | 章节编号 "3" 被误删，退回 #3 的失效状态 | 判据收紧为**页首/页尾位置**或等于当前页码 |
| 5 | **作者-年匹配**用"作者串前 12 字符比对" | 对 "Surname, Given" 与 "M. Zaheer, S. …" 型几乎全部失配，抽到 0 条上下文 | 改为**姓氏索引**（条目前 170 字符内所有首字母大写词）+ 年份约束 + 位置消歧 |
| 6 | 书目条目拆分用非贪婪 `^(.*?)\.\s` | "M. Zaheer, S. Kottur…" 的作者只截到 "M"，题名退化成整条原文 | 新增 `split_bib_entry`：第一个"位置 ≥12 且非缩写句点"作为作者区边界 |
| 7 | 参考区结束判据误用了 `looks_like_heading` | IEEE 稿的表格列名 **"Model"** 命中标题关键词表，**77 条被截断成 6 条** | 改为附录语义关键词 + "连续两条长且无年份"双重判据 |
| 8 | GAP 线索字典缺 `to date` / `only been explored` | 标准化的空白陈述句得 **0 分**，真正的种子从第 1 名掉到第 5 名 | 增补 `to date\|thus far\|until now`、`only been (explored\|studied\|considered\|…)`、`restricted to` 等 |

另外新增 `--appendix` 开关（见边界②）。三份样本（ICLR 单栏、IEEE 双栏、合成）已全部回归通过。
