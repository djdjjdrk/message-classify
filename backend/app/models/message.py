from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base, utc_now
from backend.app.models.user import User


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(content) BETWEEN 1 AND 2000", name="ck_messages_content_length"
        ),
        CheckConstraint(
            "predicted_probability BETWEEN 0 AND 1", name="ck_messages_probability"
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    predicted_label: Mapped[str | None] = mapped_column(
        Enum("normal", "spam", validate_strings=True)
    )
    prediction_status: Mapped[str] = mapped_column(
        Enum("pending", "success", "no_features", "no_model", "error", validate_strings=True),
        default="pending",
        server_default="pending",
    )
    predicted_probability: Mapped[float | None] = mapped_column(Float)
    prediction_explanation: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON(none_as_null=True)
    )
    model_name: Mapped[str | None] = mapped_column(String(128))
    manual_label: Mapped[str | None] = mapped_column(
        Enum("normal", "spam", validate_strings=True)
    )
    review_status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", validate_strings=True),
        default="pending",
        server_default="pending",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)

    author: Mapped[User] = relationship()
