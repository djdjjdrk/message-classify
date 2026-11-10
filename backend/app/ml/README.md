# 模型训练与评估

模型采用 sklearn Pipeline，依次执行 TF-IDF 和手写多项式朴素贝叶斯。

## 代码分工

| 文件 | 职责 |
| --- | --- |
| train.py | make_pipeline 组织训练，TunedThresholdClassifierCV 选择阈值 |
| features.py | jieba 分词、广告信号和 TfidfVectorizer 配置 |
| dataset.py | pandas 读写训练 CSV，统一文本格式 |
| naive_bayes.py | 手写先验、平滑、条件概率和预测得分 |
| grouping.py | sklearn 相似度检索、分组划分和 SciPy 连通分量 |
| predict.py | 加载 Pipeline、处理未知词并展示贡献词 |
| evaluate.py | sklearn 指标和分类报告，pandas 整理、导出预测明细 |

## 训练

在包含 backend、frontend 的目录执行以下命令。

~~~powershell
uv run --project backend python -m backend.app.ml.train --overwrite
~~~

训练读取 backend/data/split/train.csv 和 backend/data/processed/weak_spam.csv。
后者是已准备好的 1,551 条规则弱标注广告快照，尚未逐条人工复核。
困难正常样本额外重复两次，最终训练记录共 6,120 条。

内部验证采用模板分组隔离，选择精确率达标优先、F2 最高的阈值。
当前阈值约为 0.36，类别先验为 0.5/0.5，平滑参数为 1。
保存的 pipeline.joblib 是完整 sklearn Pipeline，包含向量器、手写分类器及模型名称和阈值。

## 预测和评估

~~~powershell
uv run --project backend python -m backend.app.ml.predict "图书馆几点关门"
uv run --project backend python -m backend.app.ml.evaluate
uv run --project backend python -m backend.app.ml.evaluate --test-csv backend/data/split/source_holdout.csv --output-dir backend/artifacts/models/final/source_evaluation
~~~

评估目录输出 metrics.json、report.txt、predictions.csv 和 errors.csv。
同分布测试准确率为 98.16%，IAD 来源压力测试垃圾召回率为 79.17%。
两种评估共享正常样本，分别报告。来源偏差及弱标注噪声仍需在真实校园数据上检验。
线上全未知词返回 no_features，离线全零特征按类别先验计分。

## 人工纠正后重训

~~~powershell
uv run --project backend python -m backend.app.commands.retrain_from_annotations
~~~

人工纠正更新训练快照后，复用同一套 Pipeline 和阈值选择流程。
新模型及对照结果保存于 backend/artifacts/models/retrained/。
