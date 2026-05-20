"""aitheria.forensic — evidence-bundle sealing, provenance, hash anchoring.

Every claim-supporting Monte Carlo output in AITHERIA-SIM must pass
through an EvidenceBundle. The bundle captures git state, platform,
package versions, operator identity, and timestamps, then writes a
hash-anchored manifest. Bundles are immutable after finalize().
"""

from aitheria.forensic.evidence_bundle import EvidenceBundle, BundleAlreadyFinalized

__all__ = ["EvidenceBundle", "BundleAlreadyFinalized"]
