"""
Ogak Crypto Utilities
Encryption, hashing, and security utilities for sensitive data.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from base64 import b64decode, b64encode

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_encryption_key() -> bytes:
    """Get the application encryption key from environment."""
    key = os.environ.get("APP_ENCRYPTION_KEY", "")
    if not key:
        raise ValueError("APP_ENCRYPTION_KEY environment variable is required")
    # Ensure key is 32 bytes for AES-256
    return hashlib.sha256(key.encode()).digest()


def encrypt_sensitive(plaintext: str) -> str:
    """
    Encrypt sensitive data (BVN, API keys) using AES-256-GCM.
    Returns base64-encoded ciphertext with prepended nonce.
    """
    key = get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Prepend nonce to ciphertext
    return b64encode(nonce + ciphertext).decode("utf-8")


def decrypt_sensitive(encrypted: str) -> str:
    """Decrypt AES-256-GCM encrypted data."""
    key = get_encryption_key()
    raw = b64decode(encrypted.encode("utf-8"))
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def hash_pin(pin: str, salt: str | None = None) -> tuple[str, str]:
    """
    Hash a USSD PIN using PBKDF2-HMAC-SHA256.
    Returns (hashed_pin, salt) tuple.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    )
    return b64encode(hashed).decode("utf-8"), salt


def verify_pin(pin: str, hashed_pin: str, salt: str) -> bool:
    """Verify a PIN against its hash."""
    computed_hash, _ = hash_pin(pin, salt)
    return hmac.compare_digest(computed_hash, hashed_pin)


def generate_ilp_condition() -> tuple[bytes, bytes]:
    """
    Generate an ILP condition and fulfillment pair.
    Fulfillment is a random 32-byte preimage.
    Condition is SHA-256(fulfillment).
    """
    fulfillment = os.urandom(32)
    condition = hashlib.sha256(fulfillment).digest()
    return condition, fulfillment


def verify_ilp_fulfillment(condition: bytes, fulfillment: bytes) -> bool:
    """Verify that a fulfillment satisfies a condition."""
    computed = hashlib.sha256(fulfillment).digest()
    return hmac.compare_digest(computed, condition)


def generate_transaction_reference(prefix: str = "OGK") -> str:
    """Generate a unique transaction reference. E.g., OGK-20260608-a3f7b2c1"""
    from datetime import datetime, timezone

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(4)
    return f"{prefix}-{date_part}-{random_part}"


def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP."""
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def generate_fernet_key() -> str:
    """Generate a Fernet encryption key (for session tokens)."""
    return Fernet.generate_key().decode("utf-8")


def hmac_sha512(secret: str, payload: str) -> str:
    """Generate HMAC-SHA512 signature (for Paystack webhook verification)."""
    return hmac.HMAC(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()


def sanitize_phone(phone: str) -> str:
    """Normalize Nigerian phone number to E.164 format (+234...)."""
    # Remove spaces, dashes, parentheses
    phone = "".join(c for c in phone if c.isdigit() or c == "+")

    if phone.startswith("+234"):
        return phone
    elif phone.startswith("234"):
        return "+" + phone
    elif phone.startswith("0"):
        return "+234" + phone[1:]
    else:
        return "+234" + phone


def mask_phone(phone: str) -> str:
    """Mask a phone number for display. E.g., +2348012345678 → +234801****678"""
    if len(phone) < 8:
        return phone
    return phone[:7] + "****" + phone[-3:]


def mask_account_number(account: str) -> str:
    """Mask an account number for display. E.g., 0123456789 → ****6789"""
    if len(account) < 4:
        return account
    return "****" + account[-4:]


def mask_bvn(bvn: str) -> str:
    """Mask a BVN for display. E.g., 12345678901 → *******8901"""
    if len(bvn) < 4:
        return bvn
    return "*" * (len(bvn) - 4) + bvn[-4:]
