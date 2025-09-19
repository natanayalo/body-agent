from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet  # type: ignore[import-not-found]

from app.config import settings


def _keys_dir() -> Path:
    d = Path(settings.data_dir) / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key_path(user_id: str) -> Path:
    # Keep filename simple; user_id is already a stable key partition for ES
    return _keys_dir() / f"{user_id}.key"


def ensure_user_key(user_id: str) -> bytes:
    kp = _key_path(user_id)
    if not kp.exists():
        key = Fernet.generate_key()
        # Best-effort to restrict permissions; platform dependent
        with open(kp, "wb") as f:
            f.write(key)
        try:
            os.chmod(kp, 0o600)
        except Exception:
            pass
        return key
    return kp.read_bytes()


def get_user_cipher(user_id: str) -> Fernet:
    key = ensure_user_key(user_id)
    return Fernet(key)


def encrypt_for_user(user_id: str, text: Optional[str]) -> str:
    if not text:
        return ""
    c = get_user_cipher(user_id)
    token = c.encrypt(text.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_for_user(user_id: str, token: Optional[str]) -> str:
    if not token:
        return ""
    c = get_user_cipher(user_id)
    plain = c.decrypt(token.encode("utf-8"))
    return plain.decode("utf-8")


__all__ = [
    "ensure_user_key",
    "get_user_cipher",
    "encrypt_for_user",
    "decrypt_for_user",
]
