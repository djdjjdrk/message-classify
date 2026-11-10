"""为已有 MySQL 标注和审核记录补充更新时间，可重复执行。"""

from sqlalchemy import inspect, text

from backend.app.database import engine


def migrate_record_timestamps() -> None:
    if engine.dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL.")

    table_names = ("annotation_records", "review_records")
    with engine.begin() as connection:
        inspector = inspect(connection)
        table_columns = {}
        # 在修改前检查两张表，避免因为缺表或缺失创建时间而只完成一部分。
        for table_name in table_names:
            if not inspector.has_table(table_name):
                raise RuntimeError(f"Missing table: {table_name}.")
            columns = {}
            for column in inspector.get_columns(table_name):
                columns[column["name"]] = column
            if "created_at" not in columns:
                raise RuntimeError(f"Missing created_at in {table_name}.")
            missing_created_at = connection.execute(text(
                f"SELECT COUNT(*) FROM {table_name} WHERE created_at IS NULL"
            )).scalar_one()
            if missing_created_at:
                raise RuntimeError(f"Null created_at in {table_name}; cannot backfill updated_at.")
            table_columns[table_name] = columns

        for table_name in table_names:
            columns = table_columns[table_name]
            if "updated_at" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN updated_at DATETIME NULL AFTER created_at"
                ))
            connection.execute(text(
                f"UPDATE {table_name} SET updated_at = created_at WHERE updated_at IS NULL"
            ))
            if "updated_at" not in columns or columns["updated_at"]["nullable"]:
                connection.execute(text(
                    f"ALTER TABLE {table_name} MODIFY COLUMN updated_at DATETIME NOT NULL"
                ))

    print("Record timestamps migrated: annotation_records, review_records.")


if __name__ == "__main__":
    migrate_record_timestamps()
