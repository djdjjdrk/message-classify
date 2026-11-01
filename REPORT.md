# 校园留言分类与垃圾信息识别系统 — 交付报告

> 课程设计题目 4。技术栈：FastAPI + MySQL + SQLAlchemy 2.x（后端），Vue 3 + Vite（前端），手写多项式朴素贝叶斯（分类）。更新时间：2026-11-01。

## 1. 运行与演示

```powershell
# 依赖（项目根目录）
uv sync --group dev
# 数据库建表，可选交互创建 student/admin 账号
uv run python -m scripts.init_db --seed-users
# 后端 http://127.0.0.1:8000/docs
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
# 前端 http://127.0.0.1:5173
cd frontend; npm ci; npm run dev
```

模型文件：`artifacts/models/baseline/pipeline.joblib`（`baseline_v1`）。缺少该文件时留言仍可发布，只是预测状态记为 `no_model`，全部交人工审核。

## 2. 四个类的职责

| 类 | 位置 | 职责 |
| --- | --- | --- |
| `Message` 留言类 | `backend/app/models/message.py` | 留言表映射：正文、模型预测（标签/概率/模型名/贡献词）、人工标签、审核状态、软删除时间；与用户、标注、审核记录关联。 |
| `TextPreprocessor` 文本预处理类 | `backend/app/ml/preprocessing.py` | 统一 NFKC 规范化、格式字符移除、空白合并与 jieba 分词；离线训练与在线预测共用同一入口，`features.tokenize` 委托给它以兼容已保存向量器。 |
| `MultinomialNaiveBayes` 分类器类 | `backend/app/ml/naive_bayes.py` | 自行实现：类别与词频统计、先验、拉普拉斯平滑、对数得分、数值稳定归一化。不调用 sklearn 的分类器。 |
| `ReviewService` 审核服务类 | `backend/app/service/review.py` | 自动通过（阈值内正常留言）、待审核查询、审核历史、人工通过/驳回；状态与历史在同一事务内提交。 |

调用关系：**Vue → HTTP → FastAPI 路由 → Service → SQLAlchemy → MySQL**；发布时 Service 调用 `predict_text`（内部用 `TextPreprocessor` + 已保存向量器 + `MultinomialNaiveBayes`）。

## 3. 逐项完成情况

| 要求 | 实现 | 位置 |
| --- | --- | --- |
| 留言发布、浏览、检索、删除 | 发布（1–2000 字，空正文拒绝）、本人/公共列表、正文关键词检索、分页、软删除 | `api/messages.py`、`views/MessagesView.vue` |
| 管理分类、审核状态与人工标注 | 全部/未分类/正常/垃圾筛选；人工标签优先，保留模型原始预测；标注历史 | `api/classification.py`、`views/ClassificationView.vue` |
| 待审核列表与审核操作界面 | 待审核列表、通过、驳回（必填原因，≤500 字），已审核再提交返回冲突 | `api/review.py`、`views/ReviewView.vue` |
| 统计数量、类别分布、审核情况 | 单次聚合，排除软删除；分类合计与审核合计分别等于总数 | `api/statistics.py`、`views/StatisticsView.vue` |
| 四张表 | `users`、`messages`、`annotation_records`、`review_records` | `backend/app/models/` |
| 四个类 | 见第 2 节 | — |
| 朴素贝叶斯 + 词袋特征 + 二分类模型 | jieba 分词 → CountVectorizer 词频 → 手写多项式朴素贝叶斯 | `ml/features.py`、`ml/naive_bayes.py` |
| 展示预测结果与主要依据 | 分类标注页与审核页显示：有效分类、模型预测、垃圾概率、模型名、最多 5 个带方向的贡献词 | `components/ClassificationSummary.vue` |
| 支持人工纠正标签 | 标注表单写人工标签，不覆盖模型预测、不改变审核状态 | `api/classification.py`、`components/AnnotationForm.vue` |
| 重新训练后比较模型效果 | 离线脚本导出人工标签、更新/补充训练集、重训并同测试集对照 | `scripts/retrain_from_annotations.py` |
| 训练与预测文本处理一致 | 两者都走 `TextPreprocessor.tokenize`；线上只调用训练词表的 `transform`，不重新拟合 | `ml/preprocessing.py`、`ml/predict.py` |
| 未见词与空文本 | 空白正文返回参数错误；部分未知词忽略未知部分；全部未知词返回 `no_features`，提示人工标注 | `ml/predict.py` |

## 4. 数据来源与规模

| 来源 | 数量 | 标签 | 说明 |
| --- | ---: | --- | --- |
| 人大校园树洞（RUC AI Competition 2025） | 2,588 | 正常 2,585 / 垃圾 3 | 正常留言主要来源 |
| IAD-dataset Part 1 | 96 | 垃圾 96 | 原定约 1,000 条，去重后仅 96 条有效候选 |
| ChineseHarm-Bench | 1,500 | 垃圾 1,500 | 按广告/引流标准筛选 |

合并、规范化、跨来源精确去重、标签冲突整组排除后，固定划分为训练集 3,347 条、测试集 837 条（正常 517 / 垃圾 320）。

## 5. 模型与评估

- 流程：规范化 → jieba 分词 → 仅用训练集拟合词表 → 词频矩阵 → 手写朴素贝叶斯（α=1.0）→ 保存 `pipeline.joblib`。
- 分类阈值 0.5（垃圾概率 ≥0.5 判为垃圾）；发布时另设 `AUTO_APPROVE_SPAM_THRESHOLD=0.25`，正常且垃圾概率 ≤25% 自动通过，其余人工审核。
- 主测试集 837 条：准确率 **98.33%**，垃圾类精确率/召回率/F1 **97.81%**，混淆矩阵 TN=510、FP=7、FN=7、TP=313，全零特征 2 条（按类别先验计入评估）。
- 合成补充集 201 条（`chatgpt_synthetic`）：准确率 80.60%，垃圾类 F1 77.97%，仅作参考，不替代独立真实数据。

## 6. 人工纠正与重训对比

```powershell
uv run python -m scripts.retrain_from_annotations            # 首次
uv run python -m scripts.retrain_from_annotations --overwrite # 补充标注后重跑
```

脚本行为：读取未删除且有人工标签的留言 → 按规范化正文去重 → 与固定测试集重合的正文排除（不参与训练）→ 原训练集已有的正文用人工标签覆盖 → 新增正文追加为 `manual_annotation` → 保存 `data/processed/split/train_corrected.csv` → 用新训练集重新拟合词表并训练 → 两个模型各自用自己的词表转换同一份测试集 → 输出 `artifacts/models/retrained/comparison.json` 与 `comparison.md`。

当前结果（人工标签仅 1 条，尚未形成有效纠正）：

| 指标 | 原模型 baseline_v1 | 重训模型 | 变化 |
| --- | ---: | ---: | ---: |
| 准确率 | 98.33% | 98.33% | +0.00% |
| 垃圾类精确率 | 97.81% | 97.81% | +0.00% |
| 垃圾类召回率 | 97.81% | 97.81% | +0.00% |
| 垃圾类 F1 | 97.81% | 97.81% | +0.00% |
| 误判数 | 14 | 14 | +0 |

> 说明：1 条纠正样本对 3,347 条训练集几乎无影响，因此指标持平。要得到有意义的对照，需先在分类标注页纠正 15–30 条留言（优先纠正模型判错的样本）后重跑脚本。指标持平或下降都如实记录，不以模型预测冒充人工标签。

待标注素材可用脚本生成，脚本只发布正文、不写标签：

```powershell
uv run python -m scripts.seed_annotation_candidates --dry-run      # 先看清单
AUTO_APPROVE_SPAM_THRESHOLD=0 uv run python -m scripts.seed_annotation_candidates --limit 30
```

默认取现模型在合成补充集上的 39 条误判，把正文以 `student` 身份发布，全部落在待审核状态（阈值置 0，避免漏判的垃圾被自动公开），清单同时写到 `artifacts/annotation_worklist.csv`。注意：

- 这批正文来自 `extra_test.csv`（GPT 生成），其标签列只作参考，人工标签必须由管理员在页面上自己点选；
- 这些正文一旦进入训练集，`retrained` 模型在 `extra_test` 上就不能再当作独立评估集，主测试集不受影响；
- 已核对：这 30 条的平均未登录词比例约 19%，误判不是词表过小导致的，而是这类"软性引流"写法与训练集的违法广告文案风格不同。

## 7. 已知局限（需在报告中如实说明）

1. 候选标签未经完整人工复核，敏感信息脱敏未完成。
2. 未实现跨来源近似重复与广告模板分组，训练/测试可能存在模板级重叠，98.33% 偏乐观。
3. 正常样本几乎全部来自树洞、垃圾样本几乎全部来自 ChineseHarm，来源可分性会使指标虚高。
4. IAD 有效候选只有 96 条，未达原定抽样目标，也未用重复采样补足。
5. 当前没有在线训练、模型版本管理页面；重训为离线脚本。

## 8. 测试

```powershell
uv run python -m pytest -q      # 后端 323 项通过
npm --prefix frontend test      # 前端 22 项通过
npm --prefix frontend run build # 生产构建
```
