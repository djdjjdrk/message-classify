from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base, utc_now
from backend.app.models.message import Message
from backend.app.models.user import User


class AnnotationRecord(Base):
    __tablename__ = "annotation_records"
    __table_args__ = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), index=True
    )
    annotator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    previous_label: Mapped[str | None] = mapped_column(
        Enum("normal", "spam", validate_strings=True)
    )
    new_label: Mapped[str] = mapped_column(
        Enum("normal", "spam", validate_strings=True)
    )
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    message: Mapped[Message] = relationship()
    annotator: Mapped[User] = relationship()
