# ML 对接约定 v1

这是后端与 ML 负责人的 Python 模块接口。数据结构和方法签名位于
[`contracts.py`](contracts.py)。当前只定义契约，没有训练、预测实现，也没有注册 ML HTTP 路由。

## 分工与入口

ML 负责人提供 `backend/app/ml/implementation.py`，导出一个无参构造的
`Classifier` 类，实现 `MLBackend` 的三个方法。不强制继承协议类，也不限定分类算法。
分词、特征提取、分类器、模型读写和特征贡献计算均由该类负责。

业务后端负责鉴权、数据库查询与写入、人工审核、训练数据筛选、模型启用与 HTTP 响应。
ML 模块只接收文本、标签和模型路径，不查询数据库、不修改审核状态。
训练和评估是同步调用，未来由业务层放入后台任务，不能直接占用前端的普通请求。

```python
from pathlib import Path
from backend.app.ml import MLBackend
from backend.app.ml.implementation import Classifier  # 由 ML 负责人新增

ml: MLBackend = Classifier()
result = ml.predict(
    "今晚图书馆有人一起自习吗？",
    model_path=Path("artifacts/models/baseline/pipeline.joblib"),
)
# 业务层将这些字段写入 Message，复杂特征列表也已转为 JSON 可存储数据。
prediction_fields = result.model_dump(mode="json")
```

## 1. 预测

`predict(content: str, *, model_path: Path) -> PredictionResult`

- 输入原始留言，长度为 1～2000 字符且不能全为空白。非法输入抛 `ValueError`。
- `model_path` 由后端传入，默认取配置 `MODEL_PATH`；相对路径以项目根目录为基准。
- 标签只使用 `normal`（正常）和 `spam`（垃圾信息）。不包含审核结论。
- `predicted_probability` 固定为 **spam 的概率**，不是预测标签的置信度；范围为 `[0, 1]`。大于等于 `0.5` 判为 spam，否则为 normal。实现必须使用分类器的类别映射取概率，不能假设 spam 总在第 2 列。
- `model_name` 是实际加载的不可变版本名，最长 128 字符，如 `baseline_v1`、`retrained_v2`。
- 特征列表最多 10 项，按 `abs(weight)` 降序。`feature` 为词或特征名，`weight` 为该文本中特征对 spam 评分的带符号贡献：正值支持 spam，负值支持 normal；它不是概率。线性模型可用“特征值 × spam 相对 normal 的系数”。算法无法解释时返回空列表，不能编造依据。

成功返回示例：

```json
{
  "prediction_status": "success",
  "predicted_label": "spam",
  "predicted_probability": 0.93,
  "prediction_explanation": [
    {"feature": "刷单", "weight": 1.28},
    {"feature": "返现", "weight": 0.71}
  ],
  "model_name": "baseline_v1"
}
```

| prediction_status | 含义 | 其他字段 |
| --- | --- | --- |
| `success` | 预测成功 | 标签、概率、版本必填；特征可为空 |
| `no_features` | 文本经过预处理后没有已知有效特征 | 标签、概率为 null，特征为空；保留已加载版本 |
| `no_model` | 指定模型文件不存在 | 标签、概率、版本为 null，特征为空 |
| `error` | 模型损坏、版本不兼容或其他推理失败 | 标签、概率为 null，特征为空；已知版本可保留 |

`pending` 仅是数据库中“尚未预测”的状态，ML 不返回它。预期推理失败用上述状态返回，并记录内部日志；不把异常堆栈写入结果。业务层遇到失败保留留言供人工审核，不能默认标成 normal。

## 2. 训练

`train(request: TrainRequest) -> TrainResult`

| 请求字段 | 约定 |
| --- | --- |
| `model_name` | 新版本名，1～128 位字母、数字、下划线或短横线 |
| `model_path` | 新版本完整输出路径，如 `artifacts/models/retrained_v2/pipeline.joblib` |
| `training_samples` | `[{"content": "…", "label": "normal或spam"}]` |
| `evaluation_samples` | 与训练集隔离的固定评估集，同上格式 |
| `random_state` | 随机种子，默认 42；所有随机步骤都使用它 |

两个数据集都必须包含 normal 和 spam，且各至少两条。每个集合内按去除首尾空白后的文本去重，集合之间也不得出现相同文本；冲突标签应由业务层先处理。样本文本限制与预测一致。

业务层提供初始有标签样本；重训时增加经人工确认的标签，人工标签优先于原始标签。不能把模型预测或“审核通过/拒绝”直接当作训练真值，不能把固定评估集加入重训集。

ML 只能在 `training_samples` 上拟合，包括分词词表、TF-IDF 和分类器；评估集只能 transform 和 predict。输出的 `TrainResult` 包含 `model_name`、`model_path`、`training_sample_count` 和 `metrics`。文件保存成功后才能返回成功结果；名字和路径与请求一致。

模型文件保存完整的预处理/特征提取/分类流水线、标签映射、阈值和版本元数据，加载后能独立预测。建议用 joblib 保存字典，具体内部格式由 ML 负责人维护。禁止覆盖已有模型文件；采用临时文件和原子发布，失败清理临时文件，不留下半成品。文件路径来自业务配置，不接收用户任意输入，也不加载用户上传的 joblib。

训练不会自动切换当前模型；后端确认训练成功后再决定启用哪个版本。缺少数据、保存失败或模型训练失败统一抛 `MLError`，保留原始异常作为 cause。

## 3. 评估与版本比较

`evaluate(request: EvaluateRequest) -> EvaluationResult`

请求包含 `model_path` 和 `samples`（至少一条有标签样本）。返回实际 `model_name` 和 `metrics`，不修改模型、不重新拟合。模型不存在、损坏、评估失败时抛 `MLError`。

训练和独立评估使用同一指标定义，**spam 为正类**：

```json
{
  "accuracy": 0.9,
  "precision": 0.9,
  "recall": 0.9,
  "f1": 0.9,
  "sample_count": 100,
  "confusion_matrix": {"tn": 45, "fp": 5, "fn": 5, "tp": 45}
}
```

指标返回 0～1 的数值，不返回百分数字符串；分母为零时指标取 0（`zero_division=0`）。混淆矩阵为真实 normal/预测 normal 的 `tn`、真实 normal/预测 spam 的 `fp`、真实 spam/预测 normal 的 `fn`、真实 spam/预测 spam 的 `tp`。

评估时遇到无有效特征的样本也必须计入总数，使用模型在全零特征向量上的概率和同一阈值评估，不能静默跳过；线上预测这类文本仍返回 `no_features` 供人工处理。如果模型不支持全零向量，评估整体失败并抛 `MLError`。

初始版本与重训版本必须在同一份冻结的评估集上比较，业务层保存该评估集的版本或内容摘要及两个版本的指标。模型版本和评估集不同的结果不能直接宣称为重训提升。

## 交付验收

ML 负责人交付 `implementation.py`、模型生成方式和所需数据说明，并验证：模型保存后重新加载可预测；正常/垃圾标签映射正确；缺失或损坏模型与无特征文本返回约定状态；训练不覆盖旧版本；固定种子和数据可以复现结果；两个版本能使用固定评估集输出相同结构的指标。

本目录的契约测试只校验数据边界，不代表算法实现或效果已经通过验收。
