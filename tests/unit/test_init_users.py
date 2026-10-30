from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.utils.password import verify_password
from backend.app.models import User
from scripts import init_db


def test_seed_keeps_existing_passwords_and_roles(db, monkeypatch):
    original = [(u.id, u.password_hash, u.role) for u in db.scalars(select(User).order_by(User.id))]
    db.commit()
    monkeypatch.setattr(init_db, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(init_db, "getpass", lambda _: (_ for _ in ()).throw(AssertionError("Must not ask for existing passwords")))
    init_db.seed_users()
    assert [(u.id, u.password_hash, u.role) for u in db.scalars(select(User).order_by(User.id))] == original


def test_seed_creates_missing_users_with_hashed_passwords(db, monkeypatch):
    db.query(User).delete()
    db.commit()
    answers = iter(["short", "new-password-123", "mismatch", "new-password-123", "new-password-123", "admin-password-123", "admin-password-123"])
    monkeypatch.setattr(init_db, "SessionLocal", sessionmaker(bind=db.get_bind()))
    monkeypatch.setattr(init_db, "getpass", lambda _: next(answers))
    init_db.seed_users()
    users = {u.username: u for u in db.scalars(select(User))}
    assert users["student"].role == "student"
    assert users["admin"].role == "admin"
    assert verify_password("new-password-123", users["student"].password_hash)
    assert verify_password("admin-password-123", users["admin"].password_hash)
