from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False
