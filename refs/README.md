# 单篇论文引用结构梳理：工具选型 + 可操作流程

> **怎么复用这套工具 → 先看 [`复用指南.md`](复用指南.md)**（三个入口的路由表 + 命令 + 回归流程）。
> 本文是选型与原理，不是日常操作手册。
>
> 目标产物两件：
> **① 引用—观点支撑对照表**（每处引用支撑什么）；
> **② 参考文献关系图谱**（传承/改进/印证/分歧/主题聚类）。
>
> 本目录下的 `citeparse.py` + `citegraph.py` 已经写好并跑通，把 PDF 给我即可直接执行。

---

## 1. 任务拆解：两个产物对应两条技术路线

| 产物 | 需要的技术 | 关键难点 |
|---|---|---|
| ① 引用—观点支撑对照表 | **引用上下文抽取** + **引用功能分类** | 上下文要精确到"哪句话、哪一节、第几页"；功能是主观判断，机器只能初筛 |
| ② 参考文献关系图谱 | **关系抽取** + **图聚类/可视化** | 参考文之间的"真实引用边"不在你手上这篇里，必须外部补 |

两件事**没有任何一个现成工具能一次做完**，但各自都有成熟方案，可以拼起来。

---

## 2. 工具与方法对比

### 2.1 引用上下文抽取（第①步的地基）

| 方案 | 输入 | 优点 | 缺点 | 门槛 |
|---|---|---|---|---|
| **GROBID**（Apache-2.0，学术标准） | PDF | 同时输出参考文献条目 + 引用上下文 + 上下文到条目的对齐（F1 0.76–0.91），TEI XML 结构完整 | **要 Java 8+ 或 Docker**（你本机两者都没装）；Windows 支持已不再是官方保证；对扫描件要先 OCR | 免费 / 需部署 / 命令行 |
| **GROBID Tools 在线版**（grobid.org，浏览器内跑） | PDF（≤50MB） | 零安装、本地浏览器处理不上传、直接导出 BibTeX/RIS/CSL-JSON | 只给参考文献条目和元数据，**不给引用上下文**；启发式，精度低于 GROBID 本体 | 免费 / 零门槛 |
| **Docling / Marker / MinerU** | PDF | 版面+表格+公式识别好，出 Markdown/JSON | **不是书目解析器**，参考文献只当纯文本给你，仍需二次解析 | 免费开源 / Python |
| **AnyStyle** | 纯文本参考文献串 | 解析非标准引用格式很强，可自训练 | 不做 PDF 版面分析，要配文本抽取器 | 免费 / Ruby |
| **pymupdf 自研抽取（本脚本）** | PDF | **零额外依赖**（你已装 pymupdf 1.28.2）、中英文都吃、可控可改 | 双栏/脚注/跨页句子会串；上标数字标记可能漏 | 免费 / 需跑命令 |

**结论**：本机没 Java/Docker，走 **pymupdf 自研路线**；若以后装上 Docker，换 GROBID 可把对齐精度从"启发式"提到 0.8+ F1。

### 2.2 引用功能分类（"这处引用在支撑什么"）

| 方案 | 输入 | 优点 | 缺点 | 门槛 |
|---|---|---|---|---|
| **scite 智能引用**（Smart Citations） | DOI / PDF | 1.6B+ 引用陈述，自动分 supporting / contrasting / mentioning，带原文摘录 | **闭源付费 $20/月**；它标的是**别人怎么引这篇**，不是"这篇怎么引它的参考文献"——方向正好相反；独立评测显示细微语境常误判为 mentioning；**中文文献覆盖几乎为零** | 付费 / 零代码 |
| **SciCite / ACT 数据集 + 微调模型**（Cohan et al.） | 引用句文本 | 开源数据+模型，三类：background / method / result | 只分 3 类，覆盖不了"指出局限""数据集来源"；要自己训或找现成 checkpoint | 免费 / 需编程 |
| **规则/线索词打分（本脚本）** | 引用句 + 所在章节 | 零依赖、可解释、可随时加规则、中英双语、**输出置信度**便于人工复核 | 覆盖面受词表限制，长难句会误判；**只能当初筛，不能当结论** | 免费 / 已封装 |
| **LLM 批量分类** | 引用句 + 章节 | 覆盖广、能处理复杂语义，能直接写"支撑的具体观点" | 要 API key、有成本、会幻觉；本机无 GPU 跑不了本地模型 | 付费 / 需编程 |

**推荐组合**：本脚本的规则分类做初筛并给出置信度 → 人工只复核低置信度条目 → 关键条目（尤其是"指出局限""对比/分歧"）回看原文确认。若条目数 > 100，再考虑接 LLM。

### 2.3 参考文献关系图谱

| 方案 | 输入 | 优点 | 缺点 | 门槛 |
|---|---|---|---|---|
| **本脚本 citegraph.py** | refs_nodes.json + contexts.json | 纯离线；四种边：同句共引、方法演进、观点对比、真实引用；Louvain 聚类；出 CSV / GraphML / Mermaid / SVG | 真实引用边需联网 | 免费 / 已封装 |
| **VOSviewer** | RIS/BibTeX/CSV 或 OpenAlex | 聚类与密度视图业界标准，可视化漂亮 | **免费但闭源**；只吃"带参考文献字段"的导入文件；中文编码常出问题 | 免费 / 零代码 |
| **CiteSpace**（陈超美） | WoS / CNKI(Refworks) / Scopus | **唯一把中文库当一等公民**的；共被引聚类、时间线（timezone）、突现词检测，国内发综述的默认工具 | Java 桌面程序；CNKI 数据**必须 Refworks 格式且文件名 `download_*.txt`**，单次导出上限 500 条，要先去重；不做单篇论文的逐条引用功能标注 | 免费 / 零代码 |
| **Gephi / yEd / Cytoscape** | GraphML/CSV | 布局、滤波、统计最专业 | 只是画图器，不管抽取 | 免费 / 零代码 |
| **CNKI 自带引文网络** | 单篇中文文献 | 直接给参考文献/引证文献/共引文献/同被引文献 | 只在其站内，不可导出结构化图 | 免费 / 零代码 |

### 2.4 中文文献的真实情况

- **导入**：CNKI 不支持 BibTeX 直出，走「导出与分析 → Refworks」拿 `.txt`；Zotero 装中文 translator 可从 CNKI 页面抓。万方/维普类似。
- **引用功能分类**：scite、SciCite 这类**对中文基本无效**（训练语料是英文），只能靠规则词表或 LLM。本脚本的线索词表已内置中文（"然而/不同于/基于/改进/局限/验证…"）。
- **共被引聚类**：中文文献的唯一成熟方案是 **CNKI → Refworks → CiteSpace**。注意三个坑：必须 Refworks 格式、文件名 `download_*.txt`、导入前必须去重（否则中文高频词如"研究""对策"会污染聚类）。
- **混合中英文**：把两边分开跑再在 Gephi 里合并，比强行塞进一个工具稳。

---

## 3. 完整操作流程

### 阶段一：准备（5 分钟）

1. 拿到论文 PDF（**必须是文本型 PDF**；扫描件先 OCR）。
2. 参考文献列表：优先用 **BibTeX**（Zotero 选中 → 右键导出 → Better BibTeX），其次 `.txt`（一行一条，可带 `[1]` 编号），实在没有就让脚本从 PDF 尾部自动解析。
3. 确认引用标记类型：`[1]` 数字制 → 默认；`(Author, 2020)` 著者年制 → 加 `--style authoryear`。

### 阶段二：抽引用上下文（1 分钟）

```bash
cd citetool
python citeparse.py <论文>.pdf --refs refs.bib            # 数字制
python citeparse.py <论文>.pdf --refs refs.txt --style authoryear
```

产出 `citation_support.csv` / `.md`，每行 = 一处引用，含：ref 编号、文献、年份、**所在章节**、**页码**、自动功能分类、**置信度**、**上下文原文**，最后一列留空给你写"支撑的具体观点"。

### 阶段三：人工复核（这一步不能省，约 30–60 分钟）

按这个顺序过一遍 CSV：
1. 先筛 `置信度 < 0.7` 的行——这些是机器没把握的，重点看。
2. **"对比/分歧"和"指出局限"两类必须逐条回看原文**：这两类最容易被线索词误触发（比如 "however" 出现在无关位置）。
3. 在「支撑的具体观点(待补)」列写一句话：**这篇引用在这句话里具体支撑了什么**（例："提供 GCN 谱域理论基础，本文方法取其消息传播形式"）。
4. 同一 ref 出现多次时，功能通常不同（引言里是背景、方法里是来源、实验里是佐证）——**保留多行，不要合并**，这正是你要的"逐条标注"。

### 阶段四：构建关系图谱（1 分钟）

```bash
python citegraph.py <输出目录>                 # 纯离线：同句共引 / 演进 / 对比
python citegraph.py <输出目录> --enrich        # 联网补真实引用边（需 OPENALEX_API_KEY）
```

产出：
- `refs_edges.csv` —— 边表，字段 `type`（co_occurrence / evolution / contrast / cites）+ `weight` + `evidence`（原句，可追溯）
- `refs_clusters.md` —— 主题聚类（Louvain）+ 每类内的关系明细 + **按年份的时间线**
- `refs_mindmap.md` —— Mermaid 思维导图，Obsidian / Typora / GitHub 直接渲染
- `refs_network.svg` —— 自绘矢量网络图（不依赖 matplotlib），节点按聚类着色、按被引次数放大
- `refs_graph.graphml` —— 导入 Gephi / yEd / Cytoscape 做深度布局

### 阶段五：读图（产出结论）

- **传承与演进** → 看 `type=evolution` 的边 + 时间线；方向按年份判定（早的在前）。
- **观点分歧** → 看 `type=contrast` 的边，回 `evidence` 看原句。
- **主题聚类** → 看 `refs_clusters.md` 的聚类分块，每个聚类给一个命名（例："谱域方法""采样与可扩展性""评测基准"）。
- **承上启下** → 时间线里最后一年那一簇，通常就是本文的直接对手/起点。

---

## 4. 两个必须知道的概念边界

1. **"同句共引" ≠ 严格意义的"共被引"**。严格共被引 = A、B 被**第三方**论文共同引用，需要外部数据。脚本里的 `co_occurrence` 是**本文内部共现**（同一句话里一起被引），信号强、免费、可解释，但语义上叫"局部共引"更准确。要严格共被引就加 `--enrich` 走 OpenAlex。
2. **自动功能分类是初筛，不是结论**。它给你的是"值得先看哪里"的排序，不是可直接写进综述的判断。所有"对比/分歧""指出局限"必须回原文。

---

## 5. 找出"真正引发该研究"的核心文献（seedfinder）

想回答"是哪 1-3 篇真正启发了这篇论文"，见 **[SEEDFINDER.md](SEEDFINDER.md)**。

```bash
python citeparse.py paper.pdf --refs refs.bib --out out
python seedfinder.py out --top 8 --metadata     # 排序 + 证据包 + 提示词
python seedfinder.py out --llm                  # 直接出最终 1-3 篇（需 LLM_API_KEY）
```

核心设计：规则只做**候选排序**（Valenzuela 2015 的重要引文分类器仅 P=0.65，不能当结论），
证据取 **±2 句窗口**（MultiCite 指出的"动机鸿沟"：17.1% 引用语境跨多句），
最终判定交给 LLM 但**强制附逐字原文**，证据不足必须弃权。

---

## 6. 命令速查

```bash
# 全流程（数字制 + BibTeX 参考文献）
python citeparse.py paper.pdf --refs refs.bib --out out
python citegraph.py out --enrich

# 从 PDF 尾部自动解析参考文献，不额外提供列表
python citeparse.py paper.pdf --out out

# 著者-年份制（自动识别；从 PDF 尾部解析 PubMed 无编号书目也 OK）
python citeparse.py paper.pdf --refs refs.txt --style authoryear --out out

# 参考文献区之后继续抽取附录（竞争者对比常常藏在这里）
python citeparse.py paper.pdf --out out --appendix
```

依赖：`pymupdf`（必需）、`networkx`（建图）、`requests`（仅 --enrich 需要）。
可选：设置 `OPENALEX_API_KEY` 环境变量后 `--enrich` 才能补真实引用边（OpenAlex 自 2026-02 起强制 key，免费申请）。
