import argparse
from getpass import getpass

from sqlalchemy import select

from backend.app.database import Base, engine
from backend.app.database import SessionLocal
from backend.app import models  # noqa: F401：models 包统一导入四个模型，注册到 Base.metadata


def seed_users() -> None:
    from backend.app.utils.password import hash_password

    with SessionLocal.begin() as session:
        for username, role in (("student", "student"), ("admin", "admin")):
            query = select(models.User)
            query = query.where(models.User.username == username)
            existing_user = session.scalar(query)
            if existing_user is not None:
                print(f"Skipped existing user: {username} (password and role unchanged)")
                continue
            while True:
                password = getpass(f"Set password for {username} (8-32 characters): ")
                if not 8 <= len(password) <= 32 or not password.strip():
                    print("Password must contain 8-32 characters and cannot be whitespace only.")
                    continue
                if password != getpass("Confirm password: "):
                    print("Passwords do not match. Try again.")
                    continue
                break
            session.add(models.User(username=username, nickname=username, password_hash=hash_password(password), role=role))
            session.flush()
            print(f"Prepared user: {username} ({role})")
    print("Account initialization committed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create missing tables and optionally initialize accounts.")
    parser.add_argument("--seed-users", action="store_true", help="Interactively create missing student/admin accounts")
    args = parser.parse_args()
    # 只创建缺少的表，不删除数据，也不修改已有表结构。
    Base.metadata.create_all(bind=engine)
    print("Tables ready: " + ", ".join(Base.metadata.tables))
    if args.seed_users:
        try:
            seed_users()
        except (KeyboardInterrupt, EOFError):
            parser.exit(1, "\nAccount initialization cancelled; account changes rolled back.\n")


if __name__ == "__main__":
    main()
