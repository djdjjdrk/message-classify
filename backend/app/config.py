from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根目录


class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    JWT_EXPIRE_HOURS: int = Field(default=2, ge=1, le=24)

    MODEL_PATH: str = "artifacts/models/baseline/pipeline.joblib"
    AUTO_APPROVE_SPAM_THRESHOLD: float = Field(default=0.25, ge=0, le=0.5)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore
