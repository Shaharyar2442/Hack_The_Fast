"""
Flag encryption/decryption utilities.

Uses Fernet (AES-128) symmetric encryption with a key derived from FLAG_MASTER_KEY.
Flags are encrypted in the database and decrypted at runtime for display.
Flag submissions are hashed and compared against stored hashes.
"""
import base64
import hashlib
import os
from cryptography.fernet import Fernet, InvalidToken

# Derive encryption key from environment variable or default seed
_SEED = os.getenv("FLAG_MASTER_KEY", "black-sunrise-zero-day")
_KEY = base64.urlsafe_b64encode(hashlib.sha256(_SEED.encode()).digest())
_CIPHER = Fernet(_KEY)


def encrypt_flag(value: str) -> str:
    """Encrypt a plaintext flag value for storage in the database."""
    if not value:
        return ""
    token = _CIPHER.encrypt(value.encode())
    return token.decode()


def decrypt_flag(token: str) -> str:
    """Decrypt an encrypted flag token back to plaintext."""
    if not token:
        return ""
    try:
        return _CIPHER.decrypt(token.encode()).decode()
    except InvalidToken:
        return "[corrupted-flag]"


def hash_flag(value: str) -> str:
    """Generate SHA-256 hash of a flag for submission validation."""
    return hashlib.sha256(value.encode()).hexdigest()

