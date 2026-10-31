import os

# 测试只使用内存数据库和测试密钥，不连接本地 MySQL。
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-at-least-32-characters"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Integer, MetaData, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.api.annotation import router as annotation_router
from backend.app.api.auth import router
from backend.app.api.classification import router as classification_router
from backend.app.api.messages import router as messages_router
from backend.app.api.review import router as review_router
from backend.app.dependencies import AdminUser
from backend.app.utils.password import hash_password
from backend.app.database import get_db
from backend.app.models import AnnotationRecord, Message, ReviewRecord, User
from backend.app.main import app
from backend.app.common.response import Response


@pytest.fixture(scope="session")
def password_hash():
    return hash_password("test-password-123")


@pytest.fixture
def db(password_hash):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _):
        connection.create_function("CHAR_LENGTH", 1, len)
        connection.execute("PRAGMA foreign_keys=ON")

    # SQLite 自增主键要求 INTEGER；只调整测试表的副本。
    metadata = MetaData()
    for model in (User, Message, AnnotationRecord, ReviewRecord):
        table = model.__table__.to_metadata(metadata)
        table.c.id.type = Integer()
    metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            User(id=1, username="student", nickname="学生", password_hash=password_hash, role="student"),
            User(id=2, username="admin", nickname="管理员", password_hash=password_hash, role="admin"),
        ])
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def client(db):
    test_app = FastAPI(exception_handlers=app.exception_handlers)
    test_app.include_router(router, prefix="/api/v1")
    test_app.include_router(messages_router, prefix="/api/v1")
    test_app.include_router(classification_router, prefix="/api/v1")
    test_app.include_router(annotation_router, prefix="/api/v1")
    test_app.include_router(review_router, prefix="/api/v1")

    @test_app.get("/admin-only")
    def admin_only(user: AdminUser):
        return Response.success(data={"id": user.id})

    test_app.dependency_overrides[get_db] = lambda: db
    with TestClient(test_app) as client:
        yield client
