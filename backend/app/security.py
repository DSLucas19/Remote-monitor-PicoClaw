import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import Settings


def generate_api_key() -> str:
    return f"rmk_{secrets.token_urlsafe(32)}"


def key_prefix(api_key: str) -> str:
    return api_key[:12]


def hash_api_key(api_key: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", api_key.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def verify_api_key(api_key: str, salt_hex: str, hash_hex: str) -> bool:
    _, computed = hash_api_key(api_key, salt_hex=salt_hex)
    return secrets.compare_digest(computed, hash_hex)


def create_session_token(settings: Settings, key_id: int) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(key_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int((expire - now).total_seconds())


def decode_session_token(settings: Settings, token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

