"""Hashing for the shared admin login secret.

The admin credential is stored only as a salted, memory-hard scrypt hash
(ADMIN_PASSWORD_HASH) — never as recoverable plaintext. A leak of the
environment, logs, or a crash dump then reveals a one-way hash, not a password
the operator may reuse elsewhere. scrypt ships in the standard library, so this
adds no dependency.

Encoded format (self-describing so params can evolve):
    scrypt$<n>$<r>$<p>$<salt_b64>$<hash_b64>
"""
from __future__ import annotations

import base64
import hmac
import os
from hashlib import scrypt

# OWASP-suggested scrypt work factors (n=2**15). Working set is ~128*n*r bytes
# (~32 MiB here); maxmem is set above that so OpenSSL doesn't reject it.
_N = 2**15
_R = 8
_P = 1
_DKLEN = 32


def _maxmem(n: int, r: int) -> int:
    return 128 * n * r * 2


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(plaintext: str) -> str:
    salt = os.urandom(16)
    digest = scrypt(
        plaintext.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN, maxmem=_maxmem(_N, _R)
    )
    return f"scrypt${_N}${_R}${_P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(plaintext: str, encoded: str) -> bool:
    """Constant-time check of `plaintext` against an encoded scrypt hash."""
    try:
        scheme, n_s, r_s, p_s, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        n, r, p = int(n_s), int(r_s), int(p_s)
        salt = _b64d(salt_b64)
        expected = _b64d(hash_b64)
        actual = scrypt(
            plaintext.encode(), salt=salt, n=n, r=r, p=p, dklen=len(expected), maxmem=_maxmem(n, r)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
