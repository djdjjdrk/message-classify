"""浏览器联调用的隔离后端；内存数据库不读取或写入本地 MySQL。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "frontend-e2e-only-secret-at-least-32-characters"

import uvicorn
from sqlalchemy import Integer, MetaData, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models import AnnotationRecord, Message, ReviewRecord, User
from backend.app.utils.password import hash_password

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def configure_sqlite(connection, _):
    connection.create_function("CHAR_LENGTH", 1, len)
    connection.execute("PRAGMA foreign_keys=ON")


metadata = MetaData()
for model in (User, Message, AnnotationRecord, ReviewRecord):
    table = model.__table__.to_metadata(metadata)
    table.c.id.type = Integer()
metadata.create_all(engine)
with Session(engine) as db:
    for user_id, username, nickname in [(1, "student", "测试同学"), (2, "admin", "测试管理员")]:
        db.add(User(id=user_id, username=username, nickname=nickname,
                    password_hash=hash_password("test-password-123"), role=username))
    db.commit()


def test_database():
    with Session(engine) as db:
        yield db


app.dependency_overrides[get_db] = test_database

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
