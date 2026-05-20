"""aitheria.theme.matplotlib — apply Navy/Gold palette to matplotlib rcParams.

Imported lazily so that `import aitheria.theme` does not pull matplotlib.
"""

from __future__ import annotations

from aitheria.theme import NAVY_GOLD


def apply_navy_gold() -> None:
    """Set matplotlib rcParams to the HydroGien Navy/Gold palette."""
    import matplotlib  # noqa: WPS433 (deliberate runtime import)

    matplotlib.rcParams.update(
        {
            "figure.facecolor": NAVY_GOLD.paper,
            "axes.facecolor": NAVY_GOLD.paper,
            "axes.edgecolor": NAVY_GOLD.primary,
            "axes.labelcolor": NAVY_GOLD.primary,
            "axes.titlecolor": NAVY_GOLD.primary,
            "xtick.color": NAVY_GOLD.primary,
            "ytick.color": NAVY_GOLD.primary,
            "grid.color": NAVY_GOLD.muted,
            "grid.alpha": 0.25,
            "axes.prop_cycle": matplotlib.cycler(
                "color", [NAVY_GOLD.primary, NAVY_GOLD.accent, NAVY_GOLD.muted, NAVY_GOLD.success]
            ),
            "font.family": "DejaVu Serif",
        }
    )


__all__ = ["apply_navy_gold"]
