"""aitheria.deterministic — canonical deterministic primitives.

Single audited surface for every hash, seed, and Merkle operation in the
AITHERIA-SIM platform. All downstream modules call into here so that the
cryptographic surface area is small, auditable, and trivially testable
against NIST SHA-256 vectors.
"""

from __future__ import annotations

import hashlib
import os
import random
from datetime import date, datetime
from typing import Iterable


def anchored_seed(date_str: str) -> int:
    """Derive a deterministic integer seed from an ISO date string.

    The convention is YYYYMMDD as a decimal integer. This is used to
    anchor Monte Carlo runs to patent priority dates.

    >>> anchored_seed("2026-05-20")
    20260520
    >>> anchored_seed("2025-04-24")
    20250424
    """
    parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    return parsed.year * 10000 + parsed.month * 100 + parsed.day


def seed_all(seed: int) -> dict:
    """Single-call seed propagator across all RNGs we touch.

    Returns a dict recording which RNGs were actually seeded, suitable
    for embedding directly into an EvidenceBundle provenance record.
    """
    seeded: dict = {"python_random": False, "numpy": False, "pytorch": False}

    random.seed(seed)
    seeded["python_random"] = True

    try:
        import numpy as np  # noqa: WPS433  (deliberate runtime import)

        np.random.seed(seed)
        seeded["numpy"] = True
    except ImportError:
        pass

    try:
        import torch  # type: ignore  # noqa: WPS433

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        seeded["pytorch"] = True
    except ImportError:
        pass

    seeded["seed_value"] = seed
    return seeded


def sha256_of_bytes(data: bytes) -> str:
    """Canonical SHA-256 of a bytes object. Returns 64-char hex string."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError(f"sha256_of_bytes requires bytes-like, got {type(data).__name__}")
    return hashlib.sha256(bytes(data)).hexdigest()


def sha256_of_file(path: str | os.PathLike) -> str:
    """Canonical SHA-256 of a file's contents. Returns 64-char hex string.

    Reads the file in 1 MiB chunks so it works for large evidence bundles
    (raw_per_trial.npz can be ~10 MiB for 100k trials).
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def merkle_root(hashes: Iterable[str]) -> str:
    """Compute a SHA-256 binary Merkle root over a list of hex hashes.

    Ordering is preserved (no lexicographic re-sort). For an empty list
    returns the hash of an empty byte string, which is a well-defined
    convention compatible with most Merkle audit tools.
    """
    layer = [bytes.fromhex(h) for h in hashes]
    if not layer:
        return hashlib.sha256(b"").hexdigest()
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])  # duplicate last on odd levels
        layer = [hashlib.sha256(layer[i] + layer[i + 1]).digest() for i in range(0, len(layer), 2)]
    return layer[0].hex()


def verify_merkle_proof(leaf: str, proof: list[tuple[str, str]], root: str) -> bool:
    """Verify a Merkle proof.

    `proof` is a list of `(sibling_hash_hex, side)` where `side` is
    `"left"` or `"right"` indicating which side the sibling sits on.
    Returns True iff folding the proof from the leaf reproduces `root`.
    """
    current = bytes.fromhex(leaf)
    for sibling_hex, side in proof:
        sibling = bytes.fromhex(sibling_hex)
        if side == "left":
            current = hashlib.sha256(sibling + current).digest()
        elif side == "right":
            current = hashlib.sha256(current + sibling).digest()
        else:
            raise ValueError(f"proof side must be 'left' or 'right', got {side!r}")
    return current.hex() == root


__all__ = [
    "anchored_seed",
    "seed_all",
    "sha256_of_bytes",
    "sha256_of_file",
    "merkle_root",
    "verify_merkle_proof",
]
