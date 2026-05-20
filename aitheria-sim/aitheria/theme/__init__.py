"""aitheria.theme — HydroGien Navy/Gold brand discipline for visual outputs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class _Palette:
    primary: str
    accent: str
    paper: str
    ink: str
    muted: str
    success: str
    warn: str
    error: str


NAVY_GOLD = _Palette(
    primary="#0A1628",
    accent="#D4A843",
    paper="#FFFFFF",
    ink="#0A1628",
    muted="#6B7280",
    success="#0F766E",
    warn="#B45309",
    error="#991B1B",
)


def luminance_ramp(hex_colour: str, n: int = 9) -> list[str]:
    """Return an n-step luminance ramp from the input toward white."""
    if not hex_colour.startswith("#") or len(hex_colour) != 7:
        raise ValueError(f"expected #RRGGBB, got {hex_colour!r}")
    r0 = int(hex_colour[1:3], 16)
    g0 = int(hex_colour[3:5], 16)
    b0 = int(hex_colour[5:7], 16)
    out: list[str] = []
    for i in range(n):
        t = i / max(1, n - 1)
        r = int(r0 + (255 - r0) * t)
        g = int(g0 + (255 - g0) * t)
        b = int(b0 + (255 - b0) * t)
        out.append(f"#{r:02X}{g:02X}{b:02X}")
    return out


__all__ = ["NAVY_GOLD", "luminance_ramp"]
