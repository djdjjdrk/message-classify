# 校园留言分类与垃圾信息识别系统 — 交付报告

> 课程设计题目 4。技术栈：FastAPI + MySQL + SQLAlchemy 2.x（后端），Vue 3 + Vite（前端），sklearn Pipeline + 手写多项式朴素贝叶斯（分类）。更新时间 2026-11-10。

## 1. 运行与演示

```powershell
# 依赖（项目根目录）
uv sync --project backend --group dev
# 数据库建表，可选交互创建 student/admin 账号
uv run --project backend python -m backend.app.commands.init_db --seed-users
# 后端 http://127.0.0.1:8000/docs
uv run --project backend uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
# 前端 http://127.0.0.1:5173
cd frontend; npm ci; npm run dev
```

模型文件：`backend/artifacts/models/final/pipeline.joblib`（`campus_spam_final_v1`）。缺少该文件时留言仍可发布，只是预测状态记为 `no_model`，全部交人工审核。

## 2. 核心类与审核服务

| 类或模块 | 位置 | 职责 |
| --- | --- | --- |
| `Message` 留言类 | `backend/app/models/message.py` | 留言表映射：正文、模型预测（标签/概率/模型名/贡献词）、人工标签、审核状态、软删除时间；与用户、标注、审核记录关联。 |
| `TextPreprocessor` 文本预处理类 | `backend/app/ml/preprocessing.py` | 统一 NFKC 规范化、格式字符移除、空白合并与 jieba 分词；离线训练与在线预测共用同一入口，`features.tokenize` 将分词结果交给 Pipeline 中的 TF-IDF 向量器。 |
| `MultinomialNaiveBayes` 分类器类 | `backend/app/ml/naive_bayes.py` | 自行实现：类别与特征权重统计、先验、拉普拉斯平滑、对数得分、数值稳定归一化。不调用 sklearn 的分类器。 |
| 审核服务函数 | `backend/app/service/review.py` | 自动通过、待审核查询、审核历史和人工审核，使用普通函数接收数据库会话，审核状态与历史在同一事务内提交。 |

调用关系：**Vue → HTTP → FastAPI 路由 → Service → SQLAlchemy → MySQL**；发布时 Service 调用 `predict_text`（内部用 `TextPreprocessor` + 已保存向量器 + `MultinomialNaiveBayes`）。

## 3. 逐项完成情况

| 要求 | 实现 | 位置 |
| --- | --- | --- |
| 留言发布、浏览、检索、删除 | 发布（1–2000 字，空正文拒绝）、本人/公共列表、正文关键词检索、分页、软删除 | `api/messages.py`、`views/MessagesView.vue` |
| 管理分类、审核状态与人工标注 | 全部/未分类/正常/垃圾筛选；人工标签优先，保留模型原始预测；标注历史 | `api/classification.py`、`views/ClassificationView.vue` |
| 待审核列表与审核操作界面 | 待审核列表、通过、驳回（必填原因，≤500 字），已审核再提交返回冲突 | `api/review.py`、`views/ReviewView.vue` |
| 统计数量、类别分布、审核情况 | 单次聚合，排除软删除；分类合计与审核合计分别等于总数 | `api/statistics.py`、`views/StatisticsView.vue` |
| 四张表 | `users`、`messages`、`annotation_records`、`review_records` | `backend/app/models/` |
| 核心类与审核服务 | 见第 2 节 | — |
| 朴素贝叶斯 + 词袋特征 + 二分类模型 | jieba 分词 → 词级 TF-IDF + 广告信号 token → 手写多项式朴素贝叶斯 | `ml/features.py`、`ml/naive_bayes.py`、`backend/app/ml/train.py` |
| 展示预测结果与主要依据 | 分类标注页与审核页显示：有效分类、模型预测、垃圾概率、模型名、最多 5 个带方向的贡献词 | `components/ClassificationSummary.vue` |
| 支持人工纠正标签 | 标注表单写人工标签，不覆盖模型预测、不改变审核状态 | `api/classification.py`、`components/AnnotationForm.vue` |
| 重新训练后比较模型效果 | 离线脚本导出人工标签、更新/补充训练集、重训并同测试集对照 | `backend/app/commands/retrain_from_annotations.py` |
| 训练与预测文本处理一致 | 两者都走 `TextPreprocessor.tokenize` 和同一组广告信号规则；线上只调用训练词表的 `transform`，不重新拟合 | `ml/preprocessing.py`、`ml/features.py`、`ml/predict.py` |
| 未见词与空文本 | 空白正文返回参数错误；部分未知词忽略未知部分；全部未知词返回 `no_features`，提示人工标注 | `ml/predict.py` |

## 4. 数据来源与规模

| 来源 | 数量 | 标签 | 说明 |
| --- | ---: | --- | --- |
| 人大校园树洞（RUC AI Competition 2025） | 2,588 | 正常 2,585 / 垃圾 3 | 正常留言主要来源 |
| IAD-dataset Part 1 | 96 | 垃圾 96 | 原定约 1,000 条，去重后仅 96 条有效候选 |
| ChineseHarm-Bench | 1,500 | 垃圾 1,500 | 按广告/引流标准筛选 |

合并并规范化后共 4,184 条。按模板及近似重复连通分量分组，将 96 条 IAD 广告整体留出；其余数据按固定种子 42、5 折第一折作为测试。原始固定训练集 3,271 条（正常 2,068、垃圾 1,203），同分布测试 817 条（正常 517、垃圾 300）。最终模型另从 ChineseHarm 原始语料自动补充 1,551 条规则弱标注广告，并对 649 条校园交易类正常样本重复 2 倍，最终训练 6,120 条；测试集和 IAD 留出集未参与训练。

## 5. 模型与评估

规范化 → jieba 分词 + 通用广告信号 token → 只用训练正文拟合词级 TF-IDF → 手写多项式朴素贝叶斯（α=1，类别先验 0.5/0.5）。阈值在训练集内部按模板组切出的 965 条验证集上选择，使用 sklearn TunedThresholdClassifierCV，目标为精确率达标优先、F2 最高，最终取 0.36；固定测试集和 IAD 来源留出集未参与阈值选择、词表拟合或标签修改。弱标注样本由规则自动筛选，未逐条人工复核。

训练与评估的精确正文、模板及规则检出的近似重复组交叉均为 0。模板分组使用字符 2–4 gram TF-IDF 余弦≥0.70、序列相似度≥0.90，按连通分量隔离；该查重词表不进入分类模型。

| 评估口径 | 样本 | 准确率 | 平衡准确率 | 垃圾精确率 | 垃圾召回率 | 垃圾 F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 模板隔离同分布测试 | 817 | 98.16% | 98.55% | 95.24% | 100.00% | 97.56% |
| IAD 来源压力测试 | 613 | 94.29% | 88.13% | 83.52% | 79.17% | 81.28% |

同分布混淆矩阵：TN=502、FP=15、FN=0、TP=300。来源压力测试混淆矩阵：TN=502、FP=15、FN=20、TP=76。

来源压力测试由 517 条留出校园正常样本和 96 条从未参与本次训练的 IAD 广告组成，与同分布测试共享正常样本，不能合并计分，也不能声称为完全独立的双类别外部测试。IAD 单独召回率为 76/96=79.17%，漏判 20 条。平衡准确率为两类召回率的平均，更能反映类别数量不均衡下的效果。

高同分布准确率的主要原因是正常和垃圾样本的来源、风格差别大：只用训练集统计的来源多数标签，同分布测试就能达到 100%。此前 98.33% 的计算可以复现，但不能代表真实校园泛化效果；检查还发现旧划分中 6 条测试样本与训练侧处于同一模板/近似重复组。当前重新隔离后高分仍存在，说明仅去重无法消除来源偏差。

训练入口：`uv run --project backend python -m backend.app.ml.train`。当前唯一线上模型目录为 `backend/artifacts/models/final/`，内含完整 Pipeline、训练摘要和两种评估的指标、分类报告及预测明细。固定划分位于 `backend/data/split/`，弱标注快照位于 `backend/data/processed/weak_spam.csv`。

## 6. 人工纠正与重训

`uv run --project backend python -m backend.app.commands.retrain_from_annotations` 从数据库读取人工标签，按正文更新或补充训练集，并排除与两种固定评估集关联的精确正文、模板和近似重复组。新模型及纠正快照保存在独立目录，用同一测试集输出前后对照；不会自动切换线上模型。

只使用人工标签，不使用模型预测作真值。当前没有积累足够人工纠正数据，不能声称重训必然提升，不保留缺乏有效纠正的旧对照表。

## 7. 局限与答辩说明

- 当前标签仍为辅助候选标签，未完成逐条人工复核与完整脱敏；最终模型额外使用的 1,551 条正样本由规则弱标注，可能含噪声。
- 训练数据中正常与垃圾来源严重混杂；即使补充弱标注广告和校园交易困难负样本，仍需要真实校园广告和含广告词的正常反例。
- IAD 仅 96 条正类，外部负类不足，来源留出测试只能反映部分分布变化。
- 同分布测试仍有 15 条正常误判为垃圾；线上自动通过要求预测正常且垃圾概率 ≤25%，这些边界样本会进入人工审核，不会被直接公开。
- 分组阈值只防止规则检出的近似重复，不能保证覆盖所有语义改写。
- 线上全未知词转人工；离线按先验预测并计入评估，二者口径分别记录。垃圾概率是模型后验输出，未经概率校准，不能当成真实正确率。

答辩可据实说明：“我们发现随机划分高分受来源偏差影响，因此固定模板分组并将 IAD 整来源留出。最终模型在 IAD 新来源广告上召回率为 79.17%，同分布垃圾精确率为 95.24%；训练中还使用了规则弱标注广告，未逐条人工复核，因此这些数字仍需真实校园数据进一步验证。”

## 8. 验证

```powershell
uv run --project backend python -m pytest -q
npm --prefix frontend test
```

本次验证：后端 321 项、前端 22 项测试全部通过；已检查最终模型加载、默认配置、弱标注候选与测试/来源留出集的正文及模板不交叉，以及训练不含 IAD 来源。
