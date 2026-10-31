"""为已有 MySQL 审核记录补充审核来源和模型依据，可重复执行。"""

from sqlalchemy import inspect, text

from backend.app.database import engine


def migrate_review_sources() -> None:
    if engine.dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL.")

    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("review_records") or not inspector.has_table("users"):
            raise RuntimeError("Missing review_records or users table.")

        columns = {}
        for column in inspector.get_columns("review_records"):
            columns[column["name"]] = column
        if "reviewer_id" not in columns:
            raise RuntimeError("Missing reviewer_id in review_records.")

        # 现有记录必须能确定审核来源，不能把无审核人的旧记录猜成系统审核。
        if "review_source" not in columns:
            ambiguous = connection.execute(text(
                "SELECT COUNT(*) FROM review_records WHERE reviewer_id IS NULL"
            )).scalar_one()
        else:
            ambiguous = connection.execute(text(
                "SELECT COUNT(*) FROM review_records "
                "WHERE review_source IS NULL AND reviewer_id IS NULL"
            )).scalar_one()
        if ambiguous:
            raise RuntimeError("Existing records have an unknown review source; fix them before migration.")
        orphaned = connection.execute(text(
            "SELECT COUNT(*) FROM review_records r LEFT JOIN users u ON r.reviewer_id = u.id "
            "WHERE r.reviewer_id IS NOT NULL AND u.id IS NULL"
        )).scalar_one()
        if orphaned:
            raise RuntimeError("Existing records have a missing reviewer; fix them before migration.")

        if "review_source" not in columns:
            connection.execute(text(
                "ALTER TABLE review_records ADD COLUMN review_source "
                "ENUM('manual', 'automatic') NOT NULL DEFAULT 'manual' AFTER reviewer_id"
            ))
        else:
            connection.execute(text(
                "UPDATE review_records SET review_source = 'manual' "
                "WHERE review_source IS NULL AND reviewer_id IS NOT NULL"
            ))
            if columns["review_source"]["nullable"]:
                connection.execute(text(
                    "ALTER TABLE review_records MODIFY COLUMN review_source "
                    "ENUM('manual', 'automatic') NOT NULL DEFAULT 'manual'"
                ))
        if "model_name_snapshot" not in columns:
            connection.execute(text(
                "ALTER TABLE review_records ADD COLUMN model_name_snapshot VARCHAR(128) NULL"
            ))
        if "spam_probability_snapshot" not in columns:
            connection.execute(text(
                "ALTER TABLE review_records ADD COLUMN spam_probability_snapshot FLOAT NULL"
            ))
        if "normal_threshold_snapshot" not in columns:
            connection.execute(text(
                "ALTER TABLE review_records ADD COLUMN normal_threshold_snapshot FLOAT NULL"
            ))
        if not columns["reviewer_id"]["nullable"]:
            connection.execute(text(
                "ALTER TABLE review_records MODIFY COLUMN reviewer_id BIGINT NULL"
            ))

        # 旧版本可能已创建这些约束；只移除审核表中本项目定义的检查约束。
        constraints = {}
        for constraint in inspect(connection).get_check_constraints("review_records"):
            constraints[constraint["name"]] = True
        checks = (
            "ck_review_records_rejection_reason",
            "ck_review_records_source_reviewer",
            "ck_review_records_spam_probability",
            "ck_review_records_normal_threshold",
            "ck_review_records_automatic_details",
        )
        for name in checks:
            if name in constraints:
                connection.execute(text(f"ALTER TABLE review_records DROP CHECK {name}"))

    print("Review source and model snapshot fields migrated.")


if __name__ == "__main__":
    migrate_review_sources()
