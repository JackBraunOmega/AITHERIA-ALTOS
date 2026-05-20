"""Tests for aitheria.forensic.evidence_bundle."""

import json
from pathlib import Path

import pytest

from aitheria.forensic.evidence_bundle import EvidenceBundle, BundleAlreadyFinalized
from aitheria.deterministic import sha256_of_bytes


def test_bundle_creates_output_dir(tmp_path):
    bundle = EvidenceBundle("TEST-001", tmp_path / "out")
    assert (tmp_path / "out").is_dir()


def test_register_artifact_bytes_returns_hash(tmp_path):
    bundle = EvidenceBundle("TEST-002", tmp_path / "out")
    digest = bundle.register_artifact_bytes("hello.txt", b"hello")
    assert digest == sha256_of_bytes(b"hello")
    assert (tmp_path / "out" / "hello.txt").read_bytes() == b"hello"


def test_finalize_writes_three_files(tmp_path):
    bundle = EvidenceBundle("TEST-003", tmp_path / "out")
    bundle.register_artifact_bytes("a.txt", b"alpha")
    manifest = bundle.finalize()

    assert (tmp_path / "out" / "TEST-003_provenance.json").exists()
    assert (tmp_path / "out" / "TEST-003_hashes.json").exists()
    assert (tmp_path / "out" / "TEST-003_evidence_manifest.json").exists()
    assert "a.txt" in manifest["artifacts"]


def test_finalize_then_mutate_raises(tmp_path):
    bundle = EvidenceBundle("TEST-004", tmp_path / "out")
    bundle.register_artifact_bytes("a.txt", b"alpha")
    bundle.finalize()
    with pytest.raises(BundleAlreadyFinalized):
        bundle.register_artifact_bytes("b.txt", b"beta")


def test_provenance_contains_required_keys(tmp_path):
    bundle = EvidenceBundle("TEST-005", tmp_path / "out")
    bundle.finalize()
    prov = json.loads((tmp_path / "out" / "TEST-005_provenance.json").read_text())
    for key in ("run_id", "started_at", "finished_at", "git", "platform", "packages", "wall_clock_seconds"):
        assert key in prov, f"missing provenance key: {key}"


def test_set_summary_writes_summary_json(tmp_path):
    bundle = EvidenceBundle("TEST-006", tmp_path / "out")
    bundle.set_summary({"h2_yield_mean_pct": 52.0, "n_trials": 1000})
    bundle.finalize()
    summary = json.loads((tmp_path / "out" / "TEST-006_summary.json").read_text())
    assert summary["h2_yield_mean_pct"] == 52.0
