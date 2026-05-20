#!/usr/bin/env python3
"""Run all 10 discovery turns, verify each, emit a per-turn markdown report.

This script intentionally does NOT commit — committing is done from the
shell so that the verbose commit-message template can carry the real hashes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aitheria.deterministic import sha256_of_file
from aitheria.discovery import run_discovery_turn, DEFAULT_SEED
from aitheria.envelope.au_2026904845 import is_in_envelope, load_au_2026904845_envelope


CANONICAL_FILES = (
    "{run_id}_raw_per_trial.npz",
    "{run_id}_summary.json",
    "{run_id}_provenance.json",
    "{run_id}_hashes.json",
)


def run_one_turn(turn: int, n_trials: int = 100_000) -> dict:
    run_id = f"HG-MC-RERUN-T{turn:02d}"
    output_dir = Path("output") / run_id
    summary = run_discovery_turn(turn=turn, n_trials=n_trials, output_dir=output_dir, run_id=run_id)

    # Verify all four canonical files exist on disk
    file_hashes = {}
    for tpl in CANONICAL_FILES:
        fname = tpl.format(run_id=run_id)
        fpath = output_dir / fname
        if not fpath.exists():
            raise RuntimeError(f"Canonical file missing on disk after run: {fpath}")
        file_hashes[fname] = sha256_of_file(fpath)

    return {
        "summary": summary,
        "file_hashes": file_hashes,
        "in_envelope": is_in_envelope(summary),
        "output_dir": str(output_dir),
    }


def write_turn_report(turn: int, result: dict, prior_summary: dict | None) -> Path:
    """Write a markdown report for this turn into docs/discovery/."""
    run_id = f"HG-MC-RERUN-T{turn:02d}"
    docs_dir = Path("docs") / "discovery"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_path = docs_dir / f"turn-{turn:02d}-report.md"

    s = result["summary"]
    fh = result["file_hashes"]

    pattern_lookup = {
        1: ("Pattern 2", "catalyst: stochastic-rare -> continuous-engineered"),
        2: ("Pattern 5", "cost: downstream derivation -> primary constraint with byproduct credit"),
        3: ("Pattern 1", "yield: stochastic N(0.52,0.14) -> engineered design-space exploration"),
        4: ("Pattern 3", "skin: static barrier -> engineered participant (2 design parameters)"),
        5: ("Pattern 6", "trial: open-loop sampling -> PICA inner loop with 3 refinement iterations"),
        6: ("Pattern 4", "yield: sampled -> first-principles modified Arrhenius (dG/RT)"),
        7: ("Pattern 7", "skin: 2 params -> 5 engineered design dimensions"),
        8: ("Pattern 8", "trials report at all mission tiers T1-T5 (graceful degradation)"),
        9: ("Pattern 10", "per-trial closed-loop envelope assertion"),
        10: ("Pattern 9", "final consolidation: kernel invokes no upstream physics-engine dependency"),
    }
    pattern, pattern_desc = pattern_lookup[turn]

    inflection = ""
    if prior_summary is not None:
        prior_y = prior_summary["h2_yield_mean_pct"]
        prior_c = prior_summary["catalyst_activity_mean_pct"]
        prior_cost = prior_summary["cost_per_kg_mean_aud"]
        envelope = load_au_2026904845_envelope()["ranges"]
        out = []
        if prior_y < envelope["h2_yield_mean_pct"]["min"]:
            out.append(f"yield={prior_y:.2f}% below {envelope['h2_yield_mean_pct']['min']}%")
        if prior_c < envelope["catalyst_activity_mean_pct"]["min"]:
            out.append(f"catalyst={prior_c:.2f}% below {envelope['catalyst_activity_mean_pct']['min']}%")
        if prior_cost < envelope["cost_per_kg_mean_aud"]["min"] or prior_cost > envelope["cost_per_kg_mean_aud"]["max"]:
            out.append(f"cost=${prior_cost:.2f}/kg outside [{envelope['cost_per_kg_mean_aud']['min']}, {envelope['cost_per_kg_mean_aud']['max']}]")
        inflection = ("Out-of-envelope at prior turn: " + "; ".join(out)) if out else "Prior turn was in envelope; this turn is a structural refinement."

    body_lines = [
        f"# Discovery Turn {turn:02d} — {run_id}",
        "",
        f"**Inversion pattern applied:** {pattern} ({pattern_desc})",
        "",
        f"**Inflection point at prior turn:** {inflection or 'baseline'}",
        "",
        "## Real evidence pack on disk",
        "",
        f"Output directory: `{result['output_dir']}`",
        "",
        "| File | SHA-256 |",
        "|---|---|",
    ]
    for fname, h in fh.items():
        body_lines.append(f"| `{fname}` | `{h}` |")

    body_lines.extend([
        "",
        "## Summary values from disk",
        "",
        f"- `discovery_turn`: {s['discovery_turn']}",
        f"- `rng_seed`: {s['rng_seed']}",
        f"- `n_trials`: {s['n_trials']}",
        f"- `h2_yield_mean_pct`: {s['h2_yield_mean_pct']:.4f}",
        f"- `h2_yield_std_pct`: {s['h2_yield_std_pct']:.4f}",
        f"- `catalyst_activity_mean_pct`: {s['catalyst_activity_mean_pct']:.4f}",
        f"- `catalyst_activity_std_pct`: {s['catalyst_activity_std_pct']:.4f}",
        f"- `cost_per_kg_mean_aud`: {s['cost_per_kg_mean_aud']:.4f}",
        f"- `cost_per_kg_std_aud`: {s['cost_per_kg_std_aud']:.4f}",
        f"- `safety_rate_pct`: {s['safety_rate_pct']:.4f}",
        f"- `patterns_applied`: {s.get('patterns_applied', [])}",
        f"- `raw_per_trial_sha256`: `{s['raw_per_trial_sha256']}`",
        "",
        f"## In envelope: **{result['in_envelope']}**",
        "",
    ])

    # Add extras if present
    extras = {k: v for k, v in s.items() if k not in {
        "run_id", "discovery_turn", "rng_seed", "rng_seeded_libraries",
        "n_trials", "h2_yield_mean_pct", "h2_yield_std_pct",
        "catalyst_activity_mean_pct", "catalyst_activity_std_pct",
        "cost_per_kg_mean_aud", "cost_per_kg_std_aud", "safety_rate_pct",
        "inversion_improvement_mean", "raw_per_trial_sha256",
        "model_lineage", "validates_au_2026904845",
        "patterns_applied", "evidence_manifest",
    }}
    if extras:
        body_lines.append("## Turn-specific extras")
        body_lines.append("")
        for k, v in extras.items():
            body_lines.append(f"- `{k}`: {v}")
        body_lines.append("")

    report_path.write_text("\n".join(body_lines), encoding="utf-8")
    return report_path


def main() -> int:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
    prior_summary = None
    output_log = []
    for turn in range(1, 11):
        result = run_one_turn(turn, n_trials=n_trials)
        report = write_turn_report(turn, result, prior_summary)
        s = result["summary"]
        print(
            f"Turn {turn:02d}: yield={s['h2_yield_mean_pct']:6.2f}% "
            f"cat={s['catalyst_activity_mean_pct']:6.2f}% "
            f"cost=${s['cost_per_kg_mean_aud']:7.2f}/kg "
            f"in_env={result['in_envelope']} "
            f"raw_sha={s['raw_per_trial_sha256'][:16]}... "
            f"report={report}"
        )
        output_log.append({
            "turn": turn,
            "summary": s,
            "file_hashes": result["file_hashes"],
            "in_envelope": result["in_envelope"],
            "report_path": str(report),
        })
        prior_summary = s

    # Write a single index report
    idx_path = Path("docs") / "discovery" / "index.md"
    idx_lines = ["# Inversion-Guided Discovery — Ten-Turn Run Index", ""]
    idx_lines.append("| Turn | Pattern | Yield % | Catalyst % | Cost AUD/kg | In env | Raw npz SHA-256 (first 16) |")
    idx_lines.append("|---|---|---|---|---|---|---|")
    pattern_short = {1: "P2", 2: "P5", 3: "P1", 4: "P3", 5: "P6", 6: "P4", 7: "P7", 8: "P8", 9: "P10", 10: "P9"}
    for row in output_log:
        s = row["summary"]
        idx_lines.append(
            f"| {row['turn']:02d} | {pattern_short[row['turn']]} | "
            f"{s['h2_yield_mean_pct']:.2f} | {s['catalyst_activity_mean_pct']:.2f} | "
            f"{s['cost_per_kg_mean_aud']:.2f} | {row['in_envelope']} | "
            f"`{s['raw_per_trial_sha256'][:16]}...` |"
        )
    idx_path.write_text("\n".join(idx_lines), encoding="utf-8")

    # Also write a machine-readable JSON manifest of the entire chain
    manifest_path = Path("docs") / "discovery" / "chain-manifest.json"
    manifest_path.write_text(json.dumps(output_log, indent=2, sort_keys=True, default=str), encoding="utf-8")

    print(f"\nIndex: {idx_path}")
    print(f"Chain manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
