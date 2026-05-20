#!/usr/bin/env python3
"""tools/discovery_turn.py — run a single Inversion-Guided Discovery turn.

Usage:
    python tools/discovery_turn.py --turn 1
    python tools/discovery_turn.py --turn 5 --n-trials 100000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from aitheria.discovery import run_discovery_turn, DEFAULT_SEED  # noqa: E402
from aitheria.envelope.au_2026904845 import is_in_envelope  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Inversion-Guided Discovery turn.")
    parser.add_argument("--turn", type=int, required=True, help="Discovery turn number (1-10).")
    parser.add_argument("--n-trials", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    summary = run_discovery_turn(
        turn=args.turn,
        n_trials=args.n_trials,
        seed=args.seed,
        output_dir=args.output_dir,
        run_id=args.run_id,
    )

    # Print summary minus the manifest (the manifest is on disk)
    display = {k: v for k, v in summary.items() if k != "evidence_manifest"}
    print(json.dumps(display, indent=2, sort_keys=True, default=str))
    print(f"\nIn envelope: {is_in_envelope(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
