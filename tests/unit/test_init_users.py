from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.utils.password import verify_password
from backend.app.models import User
from scripts import init_db


def test_seed_keeps_existing_passwords_and_roles(db, monkeypatch):
    original = []
    users = db.scalars(select(User).order_by(User.id))
    for user in users:
        original.append((user.id, user.password_hash, user.role))
    db.commit()
    monkeypatch.setattr(init_db, "SessionLocal", sessionmaker(bind=db.get_bind()))

    def unexpected_password_prompt(prompt):
        raise AssertionError("Must not ask for existing passwords")

    monkeypatch.setattr(init_db, "getpass", unexpected_password_prompt)
    init_db.seed_users()
    current = []
    users = db.scalars(select(User).order_by(User.id))
    for user in users:
        current.append((user.id, user.password_hash, user.role))
    assert current == original


def test_seed_creates_missing_users_with_hashed_passwords(db, monkeypatch):
    db.query(User).delete()
    db.commit()
    answers = iter(["short", "p" * 33, "new-password-123", "mismatch", "new-password-123", "new-password-123", "admin-password-123", "admin-password-123"])
    monkeypatch.setattr(init_db, "SessionLocal", sessionmaker(bind=db.get_bind()))

    def read_password_answer(prompt):
        return next(answers)

    monkeypatch.setattr(init_db, "getpass", read_password_answer)
    init_db.seed_users()
    users = {}
    for user in db.scalars(select(User)):
        users[user.username] = user
    assert users["student"].role == "student"
    assert users["admin"].role == "admin"
    assert users["student"].nickname == "student"
    assert users["admin"].nickname == "admin"
    assert verify_password("new-password-123", users["student"].password_hash)
    assert verify_password("admin-password-123", users["admin"].password_hash)
