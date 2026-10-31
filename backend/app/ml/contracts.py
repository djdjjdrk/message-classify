"""ML 数据契约；不依赖数据库、FastAPI 或具体分类算法。"""

from pathlib import Path
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Label = Literal["normal", "spam"]
PredictionStatus = Literal["success", "no_features", "no_model", "error"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FeatureContribution(Contract):
    feature: str = Field(min_length=1)
    weight: float


class PredictionResult(Contract):
    """字段与 Message 对齐；probability 始终表示 spam 的概率。"""

    prediction_status: PredictionStatus
    predicted_label: Label | None = None
    predicted_probability: float | None = Field(default=None, ge=0, le=1)
    prediction_explanation: list[FeatureContribution] = Field(
        default_factory=list, max_length=10
    )
    model_name: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_prediction(self) -> Self:
        if self.prediction_status == "success":
            if self.predicted_probability is None or self.model_name is None:
                raise ValueError("预测成功必须包含概率和模型版本")
            if self.predicted_probability >= 0.5:
                expected = "spam"
            else:
                expected = "normal"
            if self.predicted_label != expected:
                raise ValueError("预测标签必须与 spam 概率及 0.5 阈值一致")
        elif (
            self.predicted_label is not None
            or self.predicted_probability is not None
            or self.prediction_explanation
        ):
            raise ValueError("预测未成功时不得返回标签、概率或特征贡献")
        return self


class LabeledSample(Contract):
    content: str = Field(min_length=1, max_length=2000)
    label: Label

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("样本文本不能为空白")
        return value


class ConfusionMatrix(Contract):
    # spam 为正类，normal 为负类。
    tn: int = Field(ge=0)
    fp: int = Field(ge=0)
    fn: int = Field(ge=0)
    tp: int = Field(ge=0)


class ModelMetrics(Contract):
    accuracy: float = Field(ge=0, le=1)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    sample_count: int = Field(gt=0)
    confusion_matrix: ConfusionMatrix

    @model_validator(mode="after")
    def validate_sample_count(self) -> Self:
        matrix = self.confusion_matrix
        total = matrix.tn + matrix.fp + matrix.fn + matrix.tp
        if total != self.sample_count:
            raise ValueError("混淆矩阵数量之和必须等于评估样本数")
        return self


class TrainRequest(Contract):
    model_name: str = Field(
        min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    model_path: Path
    training_samples: list[LabeledSample] = Field(min_length=2)
    evaluation_samples: list[LabeledSample] = Field(min_length=2)
    random_state: int = Field(default=42, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def validate_datasets(self) -> Self:
        for samples in (self.training_samples, self.evaluation_samples):
            labels = set()
            texts = []
            for sample in samples:
                labels.add(sample.label)
                texts.append(sample.content.strip())

            if labels != {"normal", "spam"}:
                raise ValueError("训练集和评估集都必须包含 normal、spam 两类")
            if len(set(texts)) != len(texts):
                raise ValueError("每个数据集内必须按去除首尾空白后的文本去重")

        training_texts = set()
        for sample in self.training_samples:
            training_texts.add(sample.content.strip())
        for sample in self.evaluation_samples:
            if sample.content.strip() in training_texts:
                raise ValueError("训练集与评估集不得包含相同文本")
        return self


class TrainResult(Contract):
    model_name: str = Field(min_length=1, max_length=128)
    model_path: Path
    training_sample_count: int = Field(ge=2)
    metrics: ModelMetrics


class EvaluateRequest(Contract):
    model_path: Path
    samples: list[LabeledSample] = Field(min_length=1)


class EvaluationResult(Contract):
    model_name: str = Field(min_length=1, max_length=128)
    metrics: ModelMetrics


class MLError(RuntimeError):
    """训练、评估失败；业务层负责日志和 HTTP 错误转换。"""


class MLBackend(Protocol):
    """由 ML 负责人实现；调用方只依赖此协议。"""

    def predict(self, content: str, *, model_path: Path) -> PredictionResult:
        """预测 1～2000 字的非空白留言；预期失败返回状态，非法输入抛 ValueError。"""
        ...

    def train(self, request: TrainRequest) -> TrainResult:
        """训练、保存并评估新版本；失败抛 MLError，不覆盖已有模型文件。"""
        ...

    def evaluate(self, request: EvaluateRequest) -> EvaluationResult:
        """只评估已保存模型，不拟合或修改模型；失败抛 MLError。"""
        ...
