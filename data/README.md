# 数据目录说明

三份来源候选 CSV 保存在 `processed/`，已有实验划分及特征分别在 `split/`、`features/`；原始数据留在 `raw/`，用于追溯和重新处理。

```text
data/
├── README.md
├── raw/
│   ├── ruc_tree_hole/          # 校园树洞原始 JSONL
│   ├── iad/                    # IAD 原始 XLSX
│   └── chineseharm/            # 四类原始 JSON、上游说明、许可和校验清单
└── processed/
    ├── campus_posts.csv        # 校园留言候选
    ├── iad_spam.csv            # IAD 垃圾候选
    ├── chineseharm_spam.csv     # ChineseHarm 垃圾候选
    ├── chineseharm_report.md   # ChineseHarm 中文统计报告
    ├── split/                 # train.csv、test.csv，字段 content,label,source
    ├── features/              # 训练词表及训练、测试词频矩阵和标签
    ├── extra_test.csv         # 201 条合成补充样本
    └── extra_features/        # 使用训练词表转换的补充测试特征和标签
```

| 文件 | 数量 | 标签与字段 |
| --- | ---: | --- |
| `processed/campus_posts.csv` | 2,588 | 正常候选 2,585、垃圾候选 3；`content,label`。 |
| `processed/iad_spam.csv` | 96 | 垃圾候选；`content,label`。 |
| `processed/chineseharm_spam.csv` | 1,500 | 垃圾候选；`content,label,source`，保留原始类别。 |

三份来源 CSV 保留各自候选样本。当前 `backend/app/ml/dataset.py` 已实现合并、NFKC 及空白规范化、空正文和非法标签排除、规范化后精确去重、冲突标签整组排除，并以种子 42 按标签分层划分约 8:2。`source` 用于追溯，不参与预测特征。

## 当前实验划分与模型

| 文件 | 数量 | 类别 |
| --- | ---: | --- |
| `processed/split/train.csv` | 3,347 | 正常 2,068、垃圾 1,279 |
| `processed/split/test.csv` | 837 | 正常 517、垃圾 320 |
| `processed/extra_test.csv` | 201 | 正常 101、垃圾 100；来源 `chatgpt_synthetic` |

本地已保存训练词表、训练及测试矩阵、`baseline_v1` 模型和两份评估报告。主测试集准确率 98.33%、垃圾类 F1 97.81%，14 条误判；合成补充集准确率 80.60%、垃圾类 F1 77.97%，39 条误判。报告分别在 `artifacts/models/baseline/evaluation/` 和 `extra_evaluation/`，每份含 `metrics.json`、`predictions.csv`、`errors.csv`。

已有实验使用当前候选标签。完整人工确认、敏感信息脱敏、跨来源近似重复及广告模板分组检查仍需完成；现有精确去重及分层划分不等于模板组隔离。补充集是合成样本，不代表独立真实校园数据的效果。以上整理自现有文件，本次未重新训练或评估。

## 处理方法与来源

- 校园树洞：读取 JSONL 的 `detail`，去除首尾空白、空正文和完全重复；辅助初标后剔除 488 条不确定样本。未将所有帖子直接标为正常。
- IAD：提取“广告内容描述”列，排除空值、审核说明及语境不明文本，移除说明前缀并精确去重。5,167 条原始记录只得到 96 条广告候选。
- ChineseHarm：只筛选四个指定类别中的明确广告或引流，标准化、完全去重、模板及近似去重后，按固定种子优先抽取黑产广告。本地统计报告位于 `processed/chineseharm_report.md`。

来源地址和 IAD 论文引用见项目 [README](../README.md#数据集来源)。ChineseHarm 上游 README 声明数据采用 CC BY-NC 4.0，软件 LICENSE 为 MIT，二者分别保留在原始目录。IAD 未声明独立数据集许可证，不擅自推定许可。

处理代码保留在 `scripts/`：`clean_tree_hole.py`、`annotate_tree_hole.py`、`prepare_iad.py`、`prepare_chineseharm.py`。需要复现时使用新的输出目录。

`raw/`、`processed/` 及模型产物由 Git 忽略，需要单独准备。
