"""API key encryption at rest.

Uses Fernet (symmetric, from the cryptography package). The encryption key is
derived from settings.API_KEY_ENCRYPTION_KEY (env var), falling back to a
machine-local generated key file. Old plaintext records are handled gracefully
(decrypt-or-return-as-is on read, encrypted on next write).
"""

from __future__ import annotations

import base64
import hashlib
import os

from app.core.config import settings


def _fernet():
    from cryptography.fernet import Fernet
    secret = getattr(settings, "API_KEY_ENCRYPTION_KEY", "") or os.environ.get("API_KEY_ENCRYPTION_KEY", "")
    if not secret:
        # machine-local fallback key (persisted per install)
        key_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".enc_key")
        if not os.path.isfile(key_file):
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(Fernet.generate_key().decode())
        with open(key_file, "r", encoding="utf-8") as f:
            secret = f.read().strip()
    # normalize to 32-byte urlsafe key
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    try:
        return _fernet().encrypt(plain.encode("utf-8")).decode()
    except Exception:  # noqa: BLE001
        return plain


def decrypt_secret(stored: str) -> str:
    if not stored:
        return ""
    try:
        return _fernet().decrypt(stored.encode("utf-8")).decode("utf-8")
    except Exception:
        # legacy plaintext record — return as-is (will be re-encrypted on update)
        return stored
