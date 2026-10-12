import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from ..config import settings

_BCRYPT_SHA256_PREFIX = "bcrypt-sha256$"


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    prefix = ""
    if len(encoded) > 72:
        encoded = hashlib.sha256(encoded).hexdigest().encode("ascii")
        prefix = _BCRYPT_SHA256_PREFIX
    password_hash = bcrypt.hashpw(encoded, bcrypt.gensalt())
    return prefix + password_hash.decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if password_hash.startswith(_BCRYPT_SHA256_PREFIX):
        encoded = hashlib.sha256(encoded).hexdigest().encode("ascii")
        password_hash = password_hash.removeprefix(_BCRYPT_SHA256_PREFIX)
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
    except ValueError:
        return False


def create_access_token(user_id: UUID) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    data = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    sub = data.get("sub")
    if sub is None:
        raise JWTError("Token subject is missing")
    return UUID(sub)
