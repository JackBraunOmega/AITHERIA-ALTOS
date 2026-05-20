"""aitheria.discovery — Inversion-Guided Discovery loop infrastructure.

Implements the methodology from
docs/Claude-Code-Operating-Manual-AITHERIA-SIM-v2.0.md, Sections 3-10.

Each turn applies one of the ten inversion patterns to the parametric
Monte Carlo model. The cumulative effect — turn-by-turn — moves the
envelope dimensions (yield, catalyst, cost) toward the AU 2026904845
claim ranges. The first three turns are the load-bearing ones because
each addresses a primary out-of-envelope dimension; turns 4-10 refine
structure.

Turn → Pattern mapping:
  Turn 1  → Pattern 2  (catalyst: stochastic-rare → continuous-engineered)
  Turn 2  → Pattern 5  (cost: downstream → primary constraint)
  Turn 3  → Pattern 1  (yield: stochastic → engineered design space)
  Turn 4  → Pattern 3  (skin: static barrier → engineered participant)
  Turn 5  → Pattern 6  (open-loop trial → PICA loop inside trial)
  Turn 6  → Pattern 4  (sampled yield → first-principles Arrhenius)
  Turn 7  → Pattern 7  (single-param skin → high-dimensional skin)
  Turn 8  → Pattern 8  (tier-blind → all-tier T1-T5 reporting)
  Turn 9  → Pattern 10 (open-loop → closed-loop forensic per trial)
  Turn 10 → Pattern 9  (final dead-dependency cleanup, honest invocation)
"""

from aitheria.discovery.runner import run_discovery_turn, DEFAULT_SEED

__all__ = ["run_discovery_turn", "DEFAULT_SEED"]
