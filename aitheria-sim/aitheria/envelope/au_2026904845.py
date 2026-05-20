"""aitheria.envelope.au_2026904845 — claim-envelope reconciliation.

Loads the AU 2026904845 claim ranges from YAML and provides:

* load_au_2026904845_envelope() -> dict
* is_in_envelope(summary: dict) -> bool
* assert_in_envelope(summary: dict) -> None  (raises EnvelopeViolation)

The reconciler is intentionally strict: every range named in the YAML
must be present in the summary, and every present value must fall within
[min, max] inclusive. Missing keys are themselves violations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

import yaml


class EnvelopeViolation(AssertionError):
    """Raised by assert_in_envelope when any range check fails."""


_DEFAULT_YAML = Path(__file__).parent / "claims" / "au_2026904845.yaml"


def load_au_2026904845_envelope(path: str | os.PathLike | None = None) -> dict:
    """Load the claim-envelope YAML and return its parsed content."""
    target = Path(path) if path else _DEFAULT_YAML
    with open(target, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _check(summary: Mapping, envelope: dict) -> list[str]:
    """Return a list of violation strings (empty list == in envelope)."""
    violations: list[str] = []
    for metric, spec in envelope.get("ranges", {}).items():
        if metric not in summary:
            violations.append(f"{metric}: MISSING from summary")
            continue
        value = summary[metric]
        if not isinstance(value, (int, float)):
            violations.append(f"{metric}: non-numeric value {value!r}")
            continue
        lo, hi = float(spec["min"]), float(spec["max"])
        if value < lo or value > hi:
            violations.append(f"{metric}={value} outside claimed range [{lo}, {hi}]")
    return violations


def is_in_envelope(summary: Mapping, envelope: dict | None = None) -> bool:
    """Return True iff every claim-range metric in summary is within bounds."""
    env = envelope if envelope is not None else load_au_2026904845_envelope()
    return not _check(summary, env)


def assert_in_envelope(summary: Mapping, envelope: dict | None = None) -> None:
    """Raise EnvelopeViolation if any claim-range metric is out of bounds."""
    env = envelope if envelope is not None else load_au_2026904845_envelope()
    violations = _check(summary, env)
    if violations:
        msg = "AU 2026904845 envelope violation:\n  " + "\n  ".join(violations)
        raise EnvelopeViolation(msg)


__all__ = [
    "EnvelopeViolation",
    "load_au_2026904845_envelope",
    "is_in_envelope",
    "assert_in_envelope",
]
