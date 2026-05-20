"""Discovery turn runner — orchestrates kernel + EvidenceBundle.

Used by tools/discovery_turn.py and by tests.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import numpy as np

from aitheria.deterministic import anchored_seed, seed_all, sha256_of_bytes
from aitheria.discovery.kernels import KERNELS
from aitheria.forensic.evidence_bundle import EvidenceBundle


DEFAULT_SEED = anchored_seed("2026-05-20")  # 20260520


def run_discovery_turn(
    turn: int,
    n_trials: int = 100_000,
    seed: int = DEFAULT_SEED,
    output_dir: str | Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Execute one discovery turn. Returns the summary dict.

    Writes four canonical evidence files to `output_dir`:
      <run_id>_raw_per_trial.npz
      <run_id>_summary.json
      <run_id>_provenance.json
      <run_id>_hashes.json
    (Plus <run_id>_evidence_manifest.json from EvidenceBundle.finalize.)
    """
    if turn not in KERNELS:
        raise ValueError(f"Unknown discovery turn {turn}; expected 1..10")

    if run_id is None:
        run_id = f"HG-MC-RERUN-T{turn:02d}"
    if output_dir is None:
        output_dir = Path("output") / run_id
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    seeded = seed_all(seed)
    rng = np.random.default_rng(seed)

    kernel_fn = KERNELS[turn]
    kernel_result = kernel_fn(rng, n_trials)

    bundle = EvidenceBundle(
        run_id=run_id,
        output_dir=output_dir,
        notes=(
            f"Discovery Turn {turn}. "
            f"Inversion patterns applied: {kernel_result.get('patterns_applied', [])}. "
            f"Kernel: {kernel_fn.__name__}"
        ),
    )

    catalyst = kernel_result["catalyst"]
    yields = kernel_result["yields"]
    costs = kernel_result["costs"]
    safety = kernel_result["safety"]
    inv = kernel_result["inv"]

    # Raw per-trial archive
    raw_buf = io.BytesIO()
    np.savez_compressed(
        raw_buf,
        catalyst_activity=catalyst,
        h2_yield=yields,
        cost_per_kg_aud=costs,
        safety=safety,
        inversion_improvement=inv,
        seed=np.array([seed], dtype=np.int64),
        turn=np.array([turn], dtype=np.int64),
    )
    raw_bytes = raw_buf.getvalue()
    raw_name = f"{run_id}_raw_per_trial.npz"
    bundle.register_artifact_bytes(raw_name, raw_bytes)

    summary: dict[str, Any] = {
        "run_id": run_id,
        "discovery_turn": int(turn),
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
        "inversion_improvement_mean": float(inv.mean()),
        "raw_per_trial_sha256": sha256_of_bytes(raw_bytes),
        "model_lineage": f"discovery_turn_{turn:02d}",
        "validates_au_2026904845": False,  # only TRaCE M6 physical validation can set this True
    }
    # Pull non-array fields from the kernel result into the summary
    for k, v in kernel_result.items():
        if k in {"catalyst", "yields", "costs", "safety", "inv"}:
            continue
        summary[k] = v

    bundle.set_summary(summary)
    manifest = bundle.finalize()
    summary["evidence_manifest"] = manifest

    return summary


__all__ = ["run_discovery_turn", "DEFAULT_SEED"]
