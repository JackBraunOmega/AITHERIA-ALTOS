"""Tests for aitheria.forensic.runners.hg_mc_rerun.

These tests run a small-N MC to keep wall clock low. The full 100k-trial
run is exercised by `python tools/hg_mc_rerun_002.py`.
"""

import json
from pathlib import Path

import numpy as np

from aitheria.forensic.runners.hg_mc_rerun import run_hg_mc_rerun_002, DEFAULT_SEED
from aitheria.deterministic import sha256_of_file


def test_default_seed_is_au_priority_date():
    assert DEFAULT_SEED == 20260520


def test_small_run_produces_four_files(tmp_path):
    summary = run_hg_mc_rerun_002(n_trials=500, output_dir=tmp_path, run_id="TEST-RUN")
    expected = [
        "TEST-RUN_raw_per_trial.npz",
        "TEST-RUN_summary.json",
        "TEST-RUN_provenance.json",
        "TEST-RUN_hashes.json",
        "TEST-RUN_evidence_manifest.json",
    ]
    for name in expected:
        assert (tmp_path / name).exists(), f"missing {name}"


def test_run_is_deterministic_under_fixed_seed(tmp_path):
    s1 = run_hg_mc_rerun_002(n_trials=200, output_dir=tmp_path / "a", run_id="DET-1")
    s2 = run_hg_mc_rerun_002(n_trials=200, output_dir=tmp_path / "b", run_id="DET-1")
    # Same seed, same n, same model -> bit-identical raw output.
    h1 = sha256_of_file(tmp_path / "a" / "DET-1_raw_per_trial.npz")
    h2 = sha256_of_file(tmp_path / "b" / "DET-1_raw_per_trial.npz")
    assert h1 == h2
    assert s1["h2_yield_mean_pct"] == s2["h2_yield_mean_pct"]


def test_summary_reports_seed_and_n_trials(tmp_path):
    summary = run_hg_mc_rerun_002(n_trials=300, output_dir=tmp_path, run_id="META")
    assert summary["rng_seed"] == 20260520
    assert summary["n_trials"] == 300
    assert summary["validates_au_2026904845"] is False


def test_summary_numbers_are_out_of_envelope_by_design(tmp_path):
    """Parametric model is known to produce out-of-envelope figures."""
    summary = run_hg_mc_rerun_002(n_trials=2000, output_dir=tmp_path, run_id="ENV-CHECK")
    # Yield ~52%, catalyst ~13%, cost negative — all out of [60,95]/[55,92]/[0.5,5.0].
    assert summary["h2_yield_mean_pct"] < 60.0
    assert summary["catalyst_activity_mean_pct"] < 55.0
    assert summary["cost_per_kg_mean_aud"] < 0.5
