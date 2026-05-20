"""Tests for tools/check_layer_imports.py — clean-room layer-fence guard."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
TOOL = REPO / "tools" / "check_layer_imports.py"


def test_layer_fence_passes_on_clean_codebase():
    result = subprocess.run(
        [sys.executable, str(TOOL)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_layer_fence_catches_synthetic_violation(tmp_path):
    # Create a synthetic violation: a cleanroom layer importing another.
    cleanroom = REPO / "aitheria" / "cleanroom"
    bad_layer = cleanroom / "_synthetic_bad"
    bad_layer.mkdir(parents=True, exist_ok=True)
    bad_file = bad_layer / "bad.py"
    bad_file.write_text("from aitheria.cleanroom.galvanoxide import mechanisms\n")
    try:
        result = subprocess.run(
            [sys.executable, str(TOOL)], capture_output=True, text=True
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "_synthetic_bad" in result.stdout
    finally:
        bad_file.unlink()
        bad_layer.rmdir()
