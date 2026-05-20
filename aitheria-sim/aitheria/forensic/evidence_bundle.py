"""EvidenceBundle — cryptographic sealing for claim-supporting outputs.

Usage:

    bundle = EvidenceBundle(run_id="HG-MC-RERUN-001", output_dir="output/HG-MC-RERUN-001")
    bundle.register_artifact("output/HG-MC-RERUN-001/raw_per_trial.npz")
    bundle.register_artifact_bytes("summary.json", summary_json_bytes)
    bundle.finalize()  # writes provenance.json, hashes.json, manifest.json

After finalize(), any attempt to mutate the bundle raises
BundleAlreadyFinalized. The three written files plus every registered
artefact together form the canonical evidence pack.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from aitheria.deterministic import sha256_of_bytes, sha256_of_file


class BundleAlreadyFinalized(RuntimeError):
    """Raised on any mutation of a finalized EvidenceBundle."""


def _git(*args: str, cwd: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _capture_git_state() -> dict:
    """Capture commit SHA, branch, dirty flag, remote."""
    head = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    remote = _git("config", "--get", "remote.origin.url")
    return {
        "commit": head,
        "branch": branch,
        "dirty": dirty,
        "remote_origin": remote,
    }


def _capture_platform() -> dict:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "hostname": socket.gethostname(),
    }


def _capture_package_versions() -> dict:
    versions: dict = {}
    try:
        import numpy
        versions["numpy"] = numpy.__version__
    except ImportError:
        versions["numpy"] = None
    try:
        import torch  # type: ignore
        versions["pytorch"] = torch.__version__
        versions["pytorch_cuda_available"] = bool(torch.cuda.is_available())
        if hasattr(torch.backends, "mps"):
            versions["pytorch_mps_available"] = bool(torch.backends.mps.is_available())
    except ImportError:
        versions["pytorch"] = None
    return versions


class EvidenceBundle:
    """A sealed forensic evidence pack for a single Monte Carlo run."""

    def __init__(
        self,
        run_id: str,
        output_dir: str | os.PathLike,
        notes: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._finalized = False
        self._artifacts: dict[str, str] = {}  # name -> sha256
        self._artifact_paths: dict[str, str] = {}  # name -> on-disk path

        # Captured at construction time so they reflect the moment the run started.
        self._provenance: dict[str, Any] = {
            "run_id": run_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "started_wall_clock": time.time(),
            "operator": getpass.getuser() if os.environ.get("USER") or os.environ.get("USERNAME") else "unknown",
            "git": _capture_git_state(),
            "platform": _capture_platform(),
            "packages": _capture_package_versions(),
            "argv": list(sys.argv),
            "cwd": os.getcwd(),
            "notes": notes or "",
        }

    def _guard(self) -> None:
        if self._finalized:
            raise BundleAlreadyFinalized(
                f"EvidenceBundle for {self.run_id} is finalized; no further mutation permitted."
            )

    def register_artifact(self, path: str | os.PathLike) -> str:
        """Register a file on disk. Returns its SHA-256."""
        self._guard()
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Artifact not found: {p}")
        digest = sha256_of_file(p)
        self._artifacts[p.name] = digest
        self._artifact_paths[p.name] = str(p)
        return digest

    def register_artifact_bytes(self, name: str, data: bytes) -> str:
        """Write `data` into the output directory as `name`, register, return hash."""
        self._guard()
        target = self.output_dir / name
        with open(target, "wb") as fh:
            fh.write(data)
        digest = sha256_of_bytes(data)
        self._artifacts[name] = digest
        self._artifact_paths[name] = str(target)
        return digest

    def set_summary(self, summary: dict) -> None:
        """Convenience: write summary.json under the run_id-prefixed name."""
        self._guard()
        name = f"{self.run_id}_summary.json"
        self.register_artifact_bytes(name, json.dumps(summary, indent=2, sort_keys=True).encode("utf-8"))

    def finalize(self) -> dict:
        """Write provenance, hashes, manifest. Seal the bundle. Return the manifest."""
        self._guard()
        self._provenance["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._provenance["finished_wall_clock"] = time.time()
        self._provenance["wall_clock_seconds"] = (
            self._provenance["finished_wall_clock"] - self._provenance["started_wall_clock"]
        )

        provenance_name = f"{self.run_id}_provenance.json"
        hashes_name = f"{self.run_id}_hashes.json"
        manifest_name = f"{self.run_id}_evidence_manifest.json"

        prov_bytes = json.dumps(self._provenance, indent=2, sort_keys=True).encode("utf-8")
        (self.output_dir / provenance_name).write_bytes(prov_bytes)
        self._artifacts[provenance_name] = sha256_of_bytes(prov_bytes)

        hashes_payload = {"sha256": dict(self._artifacts)}
        hashes_bytes = json.dumps(hashes_payload, indent=2, sort_keys=True).encode("utf-8")
        (self.output_dir / hashes_name).write_bytes(hashes_bytes)
        # Don't include hashes.json's own hash in the table — that's circular.

        manifest = {
            "run_id": self.run_id,
            "output_dir": str(self.output_dir),
            "artifacts": dict(self._artifacts),
            "artifact_paths": dict(self._artifact_paths),
            "provenance_file": provenance_name,
            "hashes_file": hashes_name,
        }
        (self.output_dir / manifest_name).write_bytes(
            json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
        )

        self._finalized = True
        return manifest

    @property
    def finalized(self) -> bool:
        return self._finalized

    @property
    def artifacts(self) -> dict[str, str]:
        return dict(self._artifacts)
