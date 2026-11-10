# -*- coding: utf-8 -*-
"""在独立的演示库中建表并创建演示账号，供界面截图使用。"""
import os
import sys
from urllib.parse import quote_plus

database_password = os.environ["DEMO_DB_PASSWORD"]
os.environ["DATABASE_URL"] = (
    f"mysql+pymysql://root:{quote_plus(database_password)}"
    "@127.0.0.1:3306/message-classify-demo?charset=utf8mb4"
)

import pymysql  # noqa: E402

conn = pymysql.connect(host="127.0.0.1", port=3306, user="root",
                       password=database_password, charset="utf8mb4")
with conn.cursor() as cur:
    cur.execute("CREATE DATABASE IF NOT EXISTS `message-classify-demo` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
conn.commit()
conn.close()

from sqlalchemy import select  # noqa: E402

from backend.app.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.models import User  # noqa: E402
from backend.app.utils.password import hash_password  # noqa: E402

Base.metadata.create_all(bind=engine)
with SessionLocal.begin() as session:
    for username, nickname, role in (
        ("student", "李同学", "student"),
        ("admin", "管理员", "admin"),
    ):
        existing = session.scalar(select(User).where(User.username == username))
        if existing is None:
            session.add(User(username=username, nickname=nickname,
                             password_hash=hash_password("demo12345"), role=role))
            print("created", username)
        else:
            print("exists", username)
print("demo db ready")
