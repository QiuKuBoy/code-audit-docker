"""API key encryption at rest.

Uses Fernet (symmetric, from the cryptography package). The encryption key is
derived from settings.API_KEY_ENCRYPTION_KEY (env var), falling back to a
generated key file persisted on the data volume (so container rebuilds keep
old ciphertexts decryptable). Old plaintext records are handled gracefully
(decrypt-or-return-as-is on read, encrypted on next write).
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import stat

from app.core.config import settings

logger = logging.getLogger(__name__)


def _key_dir() -> str:
    """Directory for the fallback key file.

    Prefer the Docker data volume (/data) so the key survives container
    rebuilds; fall back to the backend directory for local dev.
    """
    if os.path.isdir("/data") and os.access("/data", os.W_OK):
        return "/data"
    # backend/app/core/crypto.py -> backend
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fernet():
    from cryptography.fernet import Fernet
    secret = getattr(settings, "API_KEY_ENCRYPTION_KEY", "") or os.environ.get("API_KEY_ENCRYPTION_KEY", "")
    if not secret:
        # machine-local fallback key (persisted on the data volume)
        key_file = os.path.join(_key_dir(), ".enc_key")
        if not os.path.isfile(key_file):
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(Fernet.generate_key().decode())
            try:
                os.chmod(key_file, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
            except OSError:
                pass  # Windows: chmod is a no-op
            logger.warning(
                "API_KEY_ENCRYPTION_KEY not set; generated a fallback key at %s. "
                "Set the env var for stable encryption across environments.", key_file,
            )
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
    except Exception as e:  # noqa: BLE001
        # Never silently store plaintext — log loudly and re-raise
        logger.error("encrypt_secret failed: %s", e)
        raise


def decrypt_secret(stored: str) -> str:
    if not stored:
        return ""
    try:
        return _fernet().decrypt(stored.encode("utf-8")).decode("utf-8")
    except Exception:
        # Legacy plaintext record — return as-is (will be re-encrypted on update)
        return stored
