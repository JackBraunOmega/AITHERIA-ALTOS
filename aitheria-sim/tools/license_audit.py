#!/usr/bin/env python3
"""tools/license_audit.py — reject GPL/AGPL/SSPL in the dependency tree.

LGPL is permitted via subprocess quarantine (it must not be linked in-process)
and is surfaced to the operator for confirmation rather than auto-failed.

Exit code:
  0 — clean (or only allowed copyleft surface-flagged)
  1 — forbidden licence detected
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

DEFAULT_FORBIDDEN = ("GPL", "AGPL", "SSPL")
# Surfaced but not failed:
SURFACED = ("LGPL",)


def _is_forbidden(licence: str, forbidden: tuple[str, ...]) -> bool:
    if not licence:
        return False
    up = licence.upper()
    # LGPL contains 'GPL' as a substring, so exclude it explicitly here.
    if any(s in up for s in SURFACED):
        return False
    return any(f in up for f in forbidden)


def _is_surfaced(licence: str) -> bool:
    if not licence:
        return False
    up = licence.upper()
    return any(s in up for s in SURFACED)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit installed package licences.")
    parser.add_argument(
        "--fail-on",
        default=",".join(DEFAULT_FORBIDDEN),
        help="Comma-separated forbidden licence substrings (default: GPL,AGPL,SSPL).",
    )
    args = parser.parse_args()
    forbidden = tuple(s.strip().upper() for s in args.fail_on.split(",") if s.strip())

    try:
        out = subprocess.run(
            ["pip-licenses", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("license_audit: pip-licenses not installed. Install with: pip install pip-licenses", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as e:
        print(f"license_audit: pip-licenses failed: {e.stderr}", file=sys.stderr)
        return 1

    pkgs = json.loads(out.stdout)
    violations = []
    surfaced = []
    for pkg in pkgs:
        lic = pkg.get("License", "")
        if _is_forbidden(lic, forbidden):
            violations.append((pkg.get("Name"), pkg.get("Version"), lic))
        elif _is_surfaced(lic):
            surfaced.append((pkg.get("Name"), pkg.get("Version"), lic))

    if surfaced:
        print("license_audit: LGPL packages detected (allowed via subprocess quarantine only):")
        for name, ver, lic in surfaced:
            print(f"  - {name} {ver} :: {lic}")

    if violations:
        print("license_audit: FORBIDDEN licences detected:")
        for name, ver, lic in violations:
            print(f"  - {name} {ver} :: {lic}")
        return 1

    print("license_audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
