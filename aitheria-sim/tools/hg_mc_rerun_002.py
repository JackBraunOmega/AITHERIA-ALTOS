#!/usr/bin/env python3
"""tools/hg_mc_rerun_002.py — CLI wrapper for the canonical MC runner.

Thin entry point. All logic lives in aitheria.forensic.runners.hg_mc_rerun.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from the repo root without installation.
_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aitheria.forensic.runners import run_hg_mc_rerun_002  # noqa: E402
from aitheria.envelope.au_2026904845 import is_in_envelope, assert_in_envelope, EnvelopeViolation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HG-MC-RERUN-002 canonical Monte Carlo.")
    parser.add_argument("--n-trials", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=None, help="Override seed (default: AU 2026904845 priority date)")
    parser.add_argument("--output-dir", default="output/HG-MC-RERUN-001")
    parser.add_argument("--run-id", default="HG-MC-RERUN-001")
    parser.add_argument("--assert-envelope", action="store_true", help="Raise on out-of-envelope output")
    args = parser.parse_args()

    kwargs = {"n_trials": args.n_trials, "output_dir": args.output_dir, "run_id": args.run_id}
    if args.seed is not None:
        kwargs["seed"] = args.seed

    summary = run_hg_mc_rerun_002(**kwargs)

    print(json.dumps({k: v for k, v in summary.items() if k != "evidence_manifest"}, indent=2, sort_keys=True))
    print(f"\nIn envelope: {is_in_envelope(summary)}")

    if args.assert_envelope:
        try:
            assert_in_envelope(summary)
        except EnvelopeViolation as e:
            print(f"\n{e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
