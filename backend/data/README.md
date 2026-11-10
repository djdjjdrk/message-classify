# 数据说明

来源候选和训练快照采用 `content,label,source` 字段。标签为 `0=正常`、`1=垃圾`，来源用于追溯和评估分析。

| 文件 | 数量 | 标签 |
| --- | ---: | --- |
| `processed/campus_posts.csv` | 2,588 | 正常 2,585、垃圾 3 |
| `processed/chineseharm_spam.csv` | 1,500 | 广告/引流候选 |
| `processed/iad_spam.csv` | 96 | 广告候选，仅用于来源留出 |

原始文件保留在 `raw/ruc_tree_hole/`、`raw/chineseharm/` 和 `raw/iad/`，用于来源追溯。ChineseHarm 统计见 `processed/chineseharm_report.md`。

## 当前固定划分

固定划分位于 `backend/data/split/`，最终 Pipeline 和评估结果位于 `backend/artifacts/models/final/`。

| 文件 | 数量 | 类别 |
| --- | ---: | --- |
| `split/train.csv` | 3,271 | 正常 2,068、垃圾 1,203 |
| `split/test.csv` | 817 | 正常 517、垃圾 300 |
| `split/source_holdout.csv` | 613 | 正常 517、IAD 垃圾 96 |

来源留出集与同分布测试共享 517 条校园正常样本，不是两份完全独立测试集。IAD 96 条记录及其关联模板组不参与训练。模板归一化与字符近似匹配只用于划分，不改写分类正文或标签；同组记录整体放在同一侧。

所有 4,184 条固定候选保留为来源 CSV，其中 3,271 条训练、817 条同分布测试、96 条 IAD 独立留出。额外的 1,551 条规则弱标注广告保存于 `processed/weak_spam.csv`，筛选时排除了与测试及留出集正文、模板重合的样本。训练入口读取这些固定快照，并将校园交易类正常样本额外重复两次，最终训练记录为 6,120 条。`split/group_assignments.csv` 记录固定划分归属。

## 来源处理

- `backend/app/commands/clean_tree_hole.py`、`backend/app/commands/annotate_tree_hole.py`：提取树洞 `detail`，清理空值和完全重复，保守辅助初标，排除 488 条不确定样本。未将所有帖子直接标为正常。
- `backend/app/commands/prepare_chineseharm.py`：从黑产广告、欺诈、博彩、低俗色情中筛选明确广告或商业引流，模板/近似去重后固定种子抽样；`source` 保留原始类别。
- `backend/app/commands/prepare_iad.py`：仅提取广告描述，排除审核说明、语境不明文本及重复；5,167 条记录得到 96 条候选，不重复采样补足。

来源地址及 IAD 论文引用见项目 [README](../../README.md#数据与训练)。ChineseHarm 上游 README 声明数据采用 CC BY-NC 4.0，软件 MIT 许可另存。IAD 的数据许可需参考上游说明。

候选标签未经完整人工复核，完整脱敏尚未完成；最终模型额外使用的 1,551 条广告正样本为规则弱标注，仍未逐条人工复核。当前没有足够真实校园垃圾样本来消除来源偏差。原始数据和生成产物由 Git 忽略，需单独准备；当前结果见 [最终模型报告](../artifacts/models/final/evaluation/report.txt) 和 [交付报告](../../REPORT.md)。
