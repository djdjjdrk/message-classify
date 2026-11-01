from pydantic import BaseModel, Field


class ClassificationCounts(BaseModel):
    normal: int = Field(ge=0)
    spam: int = Field(ge=0)
    unclassified: int = Field(ge=0)


class ReviewCounts(BaseModel):
    pending: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)


class StatisticsResponse(BaseModel):
    total: int = Field(ge=0)
    classification: ClassificationCounts
    review: ReviewCounts
