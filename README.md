# citeseed（便携版 v1.2）

找出一篇论文的 1–3 篇「核心启发文献」——即真正引发这项研究的种子文献，并给出原文支撑句。

**用法与完整流程见 [`SKILL.md`](SKILL.md)，从「〇、安装与首次适配」开始读。**

---

## 三分钟跑起来

```bash
# 1) 装依赖（唯一必需的是 pymupdf）
python -m pip install -r requirements.txt

# 2) 冒烟测试 —— 30 秒确认环境没问题
cd scripts
python autorun.py "../smoke_assets/DiffLifting.pdf" --out smoke
```

期望输出（三个数字必须对上，对不上说明环境有问题）：

```
[S3] refs=58 ctx=82 被引=45
[S6] Top1/第4名=1.41 → 排序仅用于圈定候选，必须人工裁决
[report bytes = 2667]
```

## 这个版本和原版有什么不同

只有一处：**移除了回归策略**（`regress.py` / `regress_baseline.json` / `_regress_tmp`）。
它们依赖原作者本机的 7 篇 PDF，无法随包分发。改代码后的防退化改用冒烟测试兜底，
期望值写在 SKILL.md 第〇节。核心功能、判据、流程与原版 v1.2 完全一致。

想恢复完整回归：把覆盖不同版式的 PDF 放进 `smoke_assets/`，自己记一份期望值清单，
改完脚本逐篇比对即可（版式覆盖建议见 `refs/复用指南.md` 第五节）。

## 目录

| 路径 | 作用 |
|---|---|
| `SKILL.md` | **主文档**，安装 + 单篇流程 + 批量流程，照做即可 |
| `requirements.txt` | 依赖：pymupdf（必需）、networkx（仅 citegraph）、pandas（可选） |
| `scripts/` | 6 个脚本：autorun / batchrun / citeparse / seedfinder / review / citegraph |
| `smoke_assets/` | 冒烟测试样本 PDF（不需要可整目录删） |
| `refs/` | SOP、判据细节、实测报告——排障与调参时读 |
| `samples/` | 三篇已交付的结论文档，当作输出格式范例 |

## 需要知道的两件事

1. **机器 Top1 约 3/4 不可直接采信。** 实测 Top1/第4名比值 <2.0 时排序只圈候选，
   必须人工读证据裁决（SKILL.md 第二步）。跑了不裁决，等于没跑。
2. **一批 10–15 篇最佳，单次 ≤40 篇。** 不是容量限制，是裁决质量——
   约 68% 的篇必须逐条回原文核实。超过 60 篇建议改用 `citegraph.py` 或抽样。
