from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base, utc_now
from backend.app.models.message import Message
from backend.app.models.user import User


class ReviewRecord(Base):
    __tablename__ = "review_records"
    __table_args__ = (
        CheckConstraint(
            "decision != 'rejected' OR "
            "(comment IS NOT NULL AND CHAR_LENGTH(TRIM(comment)) > 0)",
            name="ck_review_records_rejection_reason",
        ),
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    previous_status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", validate_strings=True)
    )
    decision: Mapped[str] = mapped_column(
        Enum("approved", "rejected", validate_strings=True)
    )
    label_snapshot: Mapped[str | None] = mapped_column(
        Enum("normal", "spam", validate_strings=True)
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    message: Mapped[Message] = relationship()
    reviewer: Mapped[User] = relationship()
