"""为已有 MySQL users 表补充昵称和更新时间，可重复执行，不清空数据。"""

from sqlalchemy import inspect, text

from backend.app.database import engine


def main() -> None:
    if engine.dialect.name != "mysql":
        raise RuntimeError("This migration requires MySQL.")

    with engine.begin() as connection:
        columns = {}
        database_columns = inspect(connection).get_columns("users")
        for column in database_columns:
            column_name = column["name"]
            columns[column_name] = column
        # 缩短字段前检查数据，防止 MySQL 隐式截断已有用户名。
        invalid = connection.execute(text(
            "SELECT COUNT(*) FROM users WHERE CHAR_LENGTH(username) NOT BETWEEN 3 AND 20"
        )).scalar_one()
        if invalid:
            raise RuntimeError("Existing usernames must be 3-20 characters; no changes were made.")
        if "nickname" in columns:
            too_long = connection.execute(text(
                "SELECT COUNT(*) FROM users WHERE CHAR_LENGTH(nickname) > 20"
            )).scalar_one()
            if too_long:
                raise RuntimeError("Existing nicknames exceed 20 characters; no changes were made.")

        if "nickname" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(20) NULL AFTER username"))
        connection.execute(text(
            "UPDATE users SET nickname = username WHERE nickname IS NULL OR TRIM(nickname) = ''"
        ))
        if (
            "nickname" not in columns
            or columns["nickname"]["nullable"]
            or getattr(columns["nickname"]["type"], "length", None) != 20
        ):
            connection.execute(text("ALTER TABLE users MODIFY COLUMN nickname VARCHAR(20) NOT NULL"))

        if "updated_at" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME NULL AFTER created_at"))
        connection.execute(text("UPDATE users SET updated_at = created_at WHERE updated_at IS NULL"))
        if "updated_at" not in columns or columns["updated_at"]["nullable"]:
            connection.execute(text("ALTER TABLE users MODIFY COLUMN updated_at DATETIME NOT NULL"))

        if getattr(columns["username"]["type"], "length", None) != 20:
            connection.execute(text("ALTER TABLE users MODIFY COLUMN username VARCHAR(20) NOT NULL"))

    print("Users migrated: username VARCHAR(20), nickname VARCHAR(20), updated_at DATETIME.")


if __name__ == "__main__":
    main()
