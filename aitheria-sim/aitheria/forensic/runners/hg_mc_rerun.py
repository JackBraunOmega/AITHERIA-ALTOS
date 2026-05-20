"""hg_mc_rerun — canonical 100,000-trial parametric Monte Carlo runner.

Reference reconstruction of the preserved September 2025 / HG-MC-RERUN-001
parametric NumPy model. This module is what `tools/hg_mc_rerun_002.py`
delegates to.

Honest framing:

* The chemistry-engineering models below are PARAMETRIC stand-ins, not
  first-principles physics. The catalyst-activity formula caps at 52.5%
  and the yield mean sits near 52%; these are the same out-of-envelope
  numbers documented at Gate 2 and Gate 3 in the operating manual's
  Section 2 forensic lineage.
* The runner produces a real, deterministic, hash-anchored evidence pack
  through aitheria.forensic.EvidenceBundle.
* It does NOT invoke Genesis Physics Engine, Cantera reaction networks,
  or any other real chemistry kernel. Doing so would require the Sprint 2
  GALVANOXIDE clean-room layer that does not yet exist.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import numpy as np

from aitheria.deterministic import anchored_seed, seed_all, sha256_of_bytes
from aitheria.forensic.evidence_bundle import EvidenceBundle


# Canonical anchor: AU 2026904845 priority date 20 May 2026.
DEFAULT_SEED = anchored_seed("2026-05-20")
DEFAULT_N_TRIALS = 100_000
DEFAULT_RUN_ID = "HG-MC-RERUN-001"


def _draw_catalyst_activity(rng: np.random.Generator, n: int) -> np.ndarray:
    """Parametric catalyst activity model. Caps at 0.5 * 1.05 = 0.525."""
    mno2 = rng.uniform(0.30, 0.95, size=n)
    temp = rng.normal(0.55, 0.18, size=n).clip(0.0, 1.0)
    ph = rng.normal(0.50, 0.20, size=n).clip(0.0, 1.0)
    size = rng.uniform(0.20, 0.95, size=n)
    impurity = rng.uniform(0.95, 1.05, size=n)
    activity = 0.5 * mno2 * temp * ph * size * impurity
    return activity


def _draw_yield(rng: np.random.Generator, n: int) -> np.ndarray:
    """Parametric yield model. Centred at 0.52, std ~0.14."""
    base = rng.normal(0.52, 0.14, size=n).clip(0.0, 1.0)
    return base


def _draw_cost(rng: np.random.Generator, yields: np.ndarray) -> np.ndarray:
    """Parametric cost model. Breaks down at low yields, producing negative cost."""
    al_cost = 2.40
    mno2_cost = 0.30
    water_cost = 0.05
    overhead = 0.80
    revenue_offset_per_unit_yield = 30.0
    cost = (al_cost + mno2_cost + water_cost + overhead) - revenue_offset_per_unit_yield * yields
    return cost


def _draw_safety(rng: np.random.Generator, n: int) -> np.ndarray:
    """Parametric safety model. ~100% safe trials in the reference scaffold."""
    return rng.uniform(0.0, 1.0, size=n) < 0.999999


def _draw_inversion_improvement(rng: np.random.Generator, n: int) -> np.ndarray:
    """Parametric problem-inversion-improvement model. Stand-in for PICA loop."""
    return rng.normal(120.0, 25.0, size=n).clip(0.0, 250.0)


def run_hg_mc_rerun_002(
    n_trials: int = DEFAULT_N_TRIALS,
    seed: int = DEFAULT_SEED,
    output_dir: str | Path = "output/HG-MC-RERUN-001",
    run_id: str = DEFAULT_RUN_ID,
) -> dict[str, Any]:
    """Execute the 100,000-trial parametric Monte Carlo and emit an evidence pack.

    Returns the summary dictionary. Writes four canonical files into
    `output_dir`:

      * <run_id>_raw_per_trial.npz
      * <run_id>_summary.json
      * <run_id>_provenance.json
      * <run_id>_hashes.json
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    seeded = seed_all(seed)
    rng = np.random.default_rng(seed)

    bundle = EvidenceBundle(
        run_id=run_id,
        output_dir=output_dir,
        notes=(
            "Reference parametric MC. Underlying model produces out-of-envelope "
            "outputs by design; no GALVANOXIDE clean-room kernel invoked."
        ),
    )

    catalyst = _draw_catalyst_activity(rng, n_trials)
    yields = _draw_yield(rng, n_trials)
    costs = _draw_cost(rng, yields)
    safety = _draw_safety(rng, n_trials)
    inversion_improvement = _draw_inversion_improvement(rng, n_trials)

    # Write raw per-trial data to npz (in-memory then registered via bytes).
    raw_buf = io.BytesIO()
    np.savez_compressed(
        raw_buf,
        catalyst_activity=catalyst,
        h2_yield=yields,
        cost_per_kg_aud=costs,
        safety=safety,
        inversion_improvement=inversion_improvement,
        seed=np.array([seed], dtype=np.int64),
    )
    raw_bytes = raw_buf.getvalue()
    raw_name = f"{run_id}_raw_per_trial.npz"
    bundle.register_artifact_bytes(raw_name, raw_bytes)

    summary = {
        "run_id": run_id,
        "rng_seed": int(seed),
        "rng_seeded_libraries": seeded,
        "n_trials": int(n_trials),
        "h2_yield_mean_pct": float(yields.mean() * 100.0),
        "h2_yield_std_pct": float(yields.std() * 100.0),
        "catalyst_activity_mean_pct": float(catalyst.mean() * 100.0),
        "catalyst_activity_std_pct": float(catalyst.std() * 100.0),
        "cost_per_kg_mean_aud": float(costs.mean()),
        "cost_per_kg_std_aud": float(costs.std()),
        "safety_rate_pct": float(safety.mean() * 100.0),
        "inversion_improvement_mean": float(inversion_improvement.mean()),
        "model_lineage": "parametric_sept2025_reference",
        "validates_au_2026904845": False,
        "raw_per_trial_sha256": sha256_of_bytes(raw_bytes),
    }

    bundle.set_summary(summary)
    manifest = bundle.finalize()
    summary["evidence_manifest"] = manifest

    return summary


__all__ = ["run_hg_mc_rerun_002", "DEFAULT_SEED", "DEFAULT_N_TRIALS"]
