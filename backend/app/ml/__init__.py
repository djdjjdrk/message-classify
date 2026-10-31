"""ML 公共接口，具体实现由 ML 负责人提供。"""

from backend.app.ml.contracts import (
    ConfusionMatrix,
    EvaluateRequest,
    EvaluationResult,
    FeatureContribution,
    Label,
    LabeledSample,
    MLBackend,
    MLError,
    ModelMetrics,
    PredictionResult,
    PredictionStatus,
    TrainRequest,
    TrainResult,
)

__all__ = [
    "ConfusionMatrix", "EvaluateRequest", "EvaluationResult",
    "FeatureContribution", "Label", "LabeledSample", "MLBackend", "MLError",
    "ModelMetrics", "PredictionResult", "PredictionStatus", "TrainRequest",
    "TrainResult",
]
