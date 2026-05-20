"""Tests for aitheria.deterministic — anchored seeds, NIST SHA-256, Merkle."""

import hashlib

import numpy as np
import pytest

from aitheria.deterministic import (
    anchored_seed,
    seed_all,
    sha256_of_bytes,
    sha256_of_file,
    merkle_root,
    verify_merkle_proof,
)


def test_anchored_seed_known_dates():
    assert anchored_seed("2026-05-20") == 20260520
    assert anchored_seed("2025-04-24") == 20250424


def test_seed_all_reproducibility():
    seed_all(42)
    a = np.random.rand(1000)
    seed_all(42)
    b = np.random.rand(1000)
    assert np.array_equal(a, b)


def test_sha256_of_bytes_known_vectors():
    # NIST SHA-256: empty string
    assert sha256_of_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    # NIST SHA-256: "abc"
    assert sha256_of_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_of_file(tmp_path):
    p = tmp_path / "fixture.bin"
    p.write_bytes(b"abc")
    assert sha256_of_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_merkle_root_single_leaf():
    h = sha256_of_bytes(b"hello")
    assert merkle_root([h]) == h


def test_merkle_root_two_leaves():
    h1 = sha256_of_bytes(b"a")
    h2 = sha256_of_bytes(b"b")
    expected = hashlib.sha256(bytes.fromhex(h1) + bytes.fromhex(h2)).hexdigest()
    assert merkle_root([h1, h2]) == expected


def test_merkle_root_empty():
    assert merkle_root([]) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_merkle_proof_round_trip():
    leaves = [sha256_of_bytes(str(i).encode()) for i in range(4)]
    root = merkle_root(leaves)
    # Construct a proof for leaf 0: sibling on right is leaves[1]'s hash,
    # then sibling on right is hash(leaves[2]+leaves[3]).
    sibling01 = leaves[1]
    sibling23 = hashlib.sha256(bytes.fromhex(leaves[2]) + bytes.fromhex(leaves[3])).hexdigest()
    proof = [(sibling01, "right"), (sibling23, "right")]
    assert verify_merkle_proof(leaves[0], proof, root) is True


def test_merkle_proof_bad_proof_fails():
    leaves = [sha256_of_bytes(str(i).encode()) for i in range(4)]
    root = merkle_root(leaves)
    bad_proof = [(sha256_of_bytes(b"wrong"), "right"), (sha256_of_bytes(b"wrong2"), "right")]
    assert verify_merkle_proof(leaves[0], bad_proof, root) is False
