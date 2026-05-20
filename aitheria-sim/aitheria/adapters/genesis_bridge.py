"""Genesis Physics Engine bridge — graceful degradation when absent.

The bridge does NOT silently substitute parametric output for real Genesis
output. If Genesis is not installed, GenesisScene construction raises
GenesisNotAvailableError with a clear remediation message.
"""

from __future__ import annotations


class GenesisNotAvailableError(RuntimeError):
    """Raised when Genesis is required but not importable."""


def genesis_is_available() -> bool:
    try:
        import genesis  # noqa: F401, WPS433
        return True
    except ImportError:
        return False


class GenesisScene:
    """Thin wrapper around `gs.Scene` with AITHERIA-flavoured helpers.

    Construction fails fast with GenesisNotAvailableError if Genesis
    is not installed. This is deliberate: silent fallback would let the
    runner produce output that claims Genesis provenance while actually
    running parametric NumPy.
    """

    def __init__(self, *args, **kwargs) -> None:
        if not genesis_is_available():
            raise GenesisNotAvailableError(
                "Genesis Physics Engine is not installed. Install with: pip install genesis-world"
            )
        import genesis as gs  # type: ignore  # noqa: WPS433
        self._gs = gs
        self._scene = gs.Scene(*args, **kwargs)
        self._evidence_bundle = None

    def attach_evidence_bundle(self, bundle) -> None:
        self._evidence_bundle = bundle

    def add_entity(self, morph_spec):
        return self._scene.add_entity(morph_spec)

    def step(self):
        return self._scene.step()

    def run(self, steps: int, log_every: int | None = None) -> dict:
        results = {"steps_run": 0}
        for i in range(steps):
            self._scene.step()
            results["steps_run"] = i + 1
            if log_every and (i + 1) % log_every == 0:
                pass  # would log via aitheria.theme-themed reporter
        return results


__all__ = ["GenesisNotAvailableError", "genesis_is_available", "GenesisScene"]
