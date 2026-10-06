"""Key and credential generators (UUID, x25519, base64, tokens)."""
from __future__ import annotations

import base64
import secrets
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey


def b64u(raw: bytes) -> str:
    """URL-safe base64 without padding (Reality/WireGuard raw-key format)."""
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def new_uuid() -> str:
    return str(uuid.uuid4())


def x25519_keypair() -> tuple[str, str]:
    """Return (private_b64, public_b64) raw x25519 keys (base64url, no padding)."""
    private = X25519PrivateKey.generate()
    raw_private = private.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    raw_public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return b64u(raw_private), b64u(raw_public)


def random_b64(nbytes: int) -> str:
    """Standard base64 of random bytes (used for Shadowsocks-2022 keys)."""
    return base64.b64encode(secrets.token_bytes(nbytes)).decode()


def short_ids(count: int = 2) -> list[str]:
    return [secrets.token_hex(8) for _ in range(count)]


def random_password(length: int = 24) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def new_sub_token() -> str:
    return secrets.token_urlsafe(24)
