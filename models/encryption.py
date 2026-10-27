"""Field-level PII encryption helpers (Fernet, key from env)."""

import os
import base64
from cryptography.fernet import Fernet, InvalidToken

KEY_ENV = "FIELD_ENCRYPTION_KEY"


def _get_key():
    raw = os.environ.get(KEY_ENV)
    if not raw:
        # Derive a deterministic dev key from SECRET_KEY (NOT for production).
        import hashlib
        secret = os.environ.get("SECRET_KEY", "dev")
        digest = hashlib.sha256(("field-enc:" + secret).encode()).digest()
        raw = base64.urlsafe_b64encode(digest).decode()
    # Accept either a Fernet key (44 chars) or arbitrary string -> derive.
    if len(raw) != 44:
        import hashlib
        digest = hashlib.sha256(raw.encode()).digest()
        raw = base64.urlsafe_b64encode(digest).decode()
    return raw.encode()


def get_fernet():
    return Fernet(_get_key())


def encrypt_field(value):
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_field(value):
    if value is None:
        return None
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Not encrypted (legacy plaintext) — return as-is.
        return value


def is_encrypted(value):
    if not value or not isinstance(value, str):
        return False
    try:
        get_fernet().decrypt(value.encode())
        return True
    except InvalidToken:
        return False
