from datetime import datetime

import pytest

from backend.app.models import AnnotationRecord, Message, ReviewRecord, User
from backend.app.commands import migrate_record_timestamps


@pytest.mark.parametrize("model_name", ["user", "message", "annotation", "review"])
def test_four_tables_record_creation_and_orm_update_times(db, model_name):
    user = db.get(User, 1)
    message = Message(id=100, author_id=1, content="时间记录测试")
    db.add(message)
    db.flush()
    annotation = AnnotationRecord(message_id=100, annotator_id=2, new_label="normal")
    review = ReviewRecord(
        message_id=100, reviewer_id=2, previous_status="pending", decision="approved",
    )
    db.add(annotation)
    db.add(review)
    db.commit()

    if model_name == "user":
        record = user
    elif model_name == "message":
        record = message
    elif model_name == "annotation":
        record = annotation
    else:
        record = review

    assert record.created_at is not None
    assert record.updated_at is not None
    created_at = record.created_at
    old_updated_at = datetime(2000, 1, 1)
    record.updated_at = old_updated_at
    db.commit()

    if model_name == "user":
        record.nickname = "新昵称"
    elif model_name == "message":
        record.content = "更新后的留言"
    elif model_name == "annotation":
        record.reason = "更新标注原因"
    else:
        record.comment = "更新审核说明"
    db.commit()
    db.refresh(record)
    assert record.created_at == created_at
    assert record.updated_at > old_updated_at


def test_mysql_migration_refuses_other_database_types(db, monkeypatch):
    monkeypatch.setattr(migrate_record_timestamps, "engine", db.get_bind())
    with pytest.raises(RuntimeError, match="requires MySQL"):
        migrate_record_timestamps.migrate_record_timestamps()


def test_review_record_accepts_manual_and_automatic_sources(db):
    db.add(Message(id=101, author_id=1, content="审核来源测试"))
    db.commit()
    manual = ReviewRecord(
        message_id=101, reviewer_id=2, previous_status="pending", decision="approved",
    )
    automatic = ReviewRecord(
        message_id=101, reviewer_id=None, review_source="automatic",
        previous_status="pending", decision="approved", label_snapshot="normal",
        model_name_snapshot="model_v1", spam_probability_snapshot=0.02,
        normal_threshold_snapshot=0.95,
    )
    db.add(manual)
    db.add(automatic)
    db.commit()
    assert manual.review_source == "manual"
    assert automatic.reviewer_id is None
