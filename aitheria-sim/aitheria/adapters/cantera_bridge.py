"""Cantera bridge — graceful degradation when absent."""

from __future__ import annotations

import os
from pathlib import Path


class CanteraNotAvailableError(RuntimeError):
    """Raised when Cantera is required but not importable."""


def cantera_is_available() -> bool:
    try:
        import cantera  # noqa: F401, WPS433
        return True
    except ImportError:
        return False


def load_mechanism(yaml_path: str | os.PathLike):
    """Load a Cantera Solution from a mechanism YAML.

    Raises CanteraNotAvailableError if Cantera is not installed. Raises
    FileNotFoundError if the mechanism file does not exist.
    """
    if not cantera_is_available():
        raise CanteraNotAvailableError(
            "Cantera is not installed. Install with: pip install cantera>=3.0"
        )
    target = Path(yaml_path)
    if not target.exists():
        raise FileNotFoundError(f"Cantera mechanism file not found: {target}")
    import cantera as ct  # type: ignore  # noqa: WPS433
    return ct.Solution(str(target))


__all__ = ["CanteraNotAvailableError", "cantera_is_available", "load_mechanism"]
