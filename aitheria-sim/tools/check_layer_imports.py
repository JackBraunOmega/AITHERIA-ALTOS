#!/usr/bin/env python3
"""tools/check_layer_imports.py — clean-room layer-fence guard.

Enforces the rule from the operating manual: no clean-room layer under
`aitheria/cleanroom/` may import another clean-room layer directly. They
may only communicate through `aitheria/couplers/`.

Allow-list for cleanroom imports:
  * stdlib (any)
  * numpy, scipy, pyyaml, torch, warp, cantera, mitsuba, drjit
  * aitheria.deterministic, aitheria.forensic, aitheria.envelope, aitheria.theme
  * aitheria.couplers (mediation path)

Exit code:
  0 — clean
  1 — violations detected (file:line listed)
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ALLOWED_PREFIXES = {
    "aitheria.deterministic",
    "aitheria.forensic",
    "aitheria.envelope",
    "aitheria.theme",
    "aitheria.adapters",
    "aitheria.couplers",
}

ALLOWED_THIRDPARTY = {
    "numpy", "scipy", "torch", "warp", "cantera", "mitsuba", "drjit",
    "yaml", "pyyaml", "pennylane", "qiskit", "cirq",
}


def _stdlib_modules() -> set[str]:
    # Conservative subset; sys.stdlib_module_names exists from Python 3.10.
    return set(getattr(sys, "stdlib_module_names", set()))


def _is_allowed(module_name: str) -> bool:
    if not module_name:
        return True
    root = module_name.split(".")[0]
    if root in _stdlib_modules():
        return True
    if root in ALLOWED_THIRDPARTY:
        return True
    for prefix in ALLOWED_PREFIXES:
        if module_name == prefix or module_name.startswith(prefix + "."):
            return True
    # Same cleanroom layer is OK; different cleanroom layer is the violation.
    return False


def _module_layer(file_path: Path) -> str | None:
    parts = file_path.parts
    if "cleanroom" not in parts:
        return None
    idx = parts.index("cleanroom")
    if idx + 1 < len(parts):
        return parts[idx + 1]
    return None


def _check_file(file_path: Path) -> list[str]:
    violations: list[str] = []
    layer = _module_layer(file_path)
    if layer is None:
        return violations
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return [f"{file_path}:{e.lineno}: SyntaxError: {e.msg}"]

    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names = [node.module]
        for name in names:
            # Same-layer import is fine; different cleanroom layer is the violation.
            if name.startswith("aitheria.cleanroom."):
                other_layer = name.split(".")[2] if name.count(".") >= 2 else ""
                if other_layer and other_layer != layer:
                    violations.append(
                        f"{file_path}:{node.lineno}: cleanroom layer '{layer}' imports cleanroom layer '{other_layer}'"
                    )
                continue
            if not _is_allowed(name):
                violations.append(
                    f"{file_path}:{node.lineno}: layer '{layer}' imports disallowed module '{name}'"
                )
    return violations


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    cleanroom = repo / "aitheria" / "cleanroom"
    if not cleanroom.exists():
        print("layer-check: OK (no cleanroom directory yet)")
        return 0

    all_violations: list[str] = []
    for py in cleanroom.rglob("*.py"):
        all_violations.extend(_check_file(py))

    if all_violations:
        print("Layer-fence violations:")
        for v in all_violations:
            print(f"  {v}")
        return 1

    print("layer-check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
