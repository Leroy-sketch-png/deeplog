"""Salted hashing helpers for pseudonymizing identifier columns in samples.

The salt is generated once per process run using ``os.urandom`` and is kept
only in memory. It is intentionally never written to any artifact file, so
hashed values in saved samples cannot be reversed or joined against other
runs of this script.
"""

from __future__ import annotations

import hashlib
import os


def generate_run_salt() -> bytes:
    """Generate a fresh random salt for this run. Never persisted to disk."""
    return os.urandom(32)


def salted_hash(value: str, salt: bytes) -> str:
    """Return a short, stable (within this run) salted hash of ``value``."""
    if value is None:
        value = ""
    digest = hashlib.sha256(salt + str(value).encode("utf-8", errors="replace")).hexdigest()
    return f"h_{digest[:16]}"
