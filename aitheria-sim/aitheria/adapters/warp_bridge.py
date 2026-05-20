"""NVIDIA Warp bridge — graceful degradation when absent."""

from __future__ import annotations

from functools import wraps


class WarpNotAvailableError(RuntimeError):
    """Raised when Warp is required but not importable."""


def warp_is_available() -> bool:
    try:
        import warp  # noqa: F401, WPS433
        return True
    except ImportError:
        return False


def aitheria_kernel(fn):
    """Decorator that wraps wp.kernel with availability checks.

    When Warp is installed, wraps fn with wp.kernel. When it is not,
    returns a callable that raises WarpNotAvailableError on invocation.
    """
    if warp_is_available():
        import warp as wp  # type: ignore  # noqa: WPS433
        return wp.kernel(fn)

    @wraps(fn)
    def _raise(*args, **kwargs):
        raise WarpNotAvailableError(
            "Warp is not installed. Install with: pip install warp-lang>=1.3"
        )

    return _raise


def init_warp(backend: str = "cpu") -> dict:
    """Initialise Warp on the requested backend and return a provenance dict."""
    if not warp_is_available():
        raise WarpNotAvailableError(
            "Warp is not installed. Install with: pip install warp-lang>=1.3"
        )
    import warp as wp  # type: ignore  # noqa: WPS433

    wp.init()
    return {
        "warp_version": getattr(wp, "__version__", "unknown"),
        "backend_requested": backend,
        "available": True,
    }


__all__ = [
    "WarpNotAvailableError",
    "warp_is_available",
    "aitheria_kernel",
    "init_warp",
]
