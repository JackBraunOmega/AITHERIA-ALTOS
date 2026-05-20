"""Tests for aitheria.envelope.au_2026904845 — claim-envelope reconciliation."""

import pytest

from aitheria.envelope.au_2026904845 import (
    EnvelopeViolation,
    load_au_2026904845_envelope,
    is_in_envelope,
    assert_in_envelope,
)


def test_load_envelope_has_three_ranges():
    env = load_au_2026904845_envelope()
    assert "ranges" in env
    assert {"h2_yield_mean_pct", "catalyst_activity_mean_pct", "cost_per_kg_mean_aud"} <= set(env["ranges"])


def test_is_in_envelope_when_all_in_range():
    summary = {
        "h2_yield_mean_pct": 75.0,
        "catalyst_activity_mean_pct": 70.0,
        "cost_per_kg_mean_aud": 2.5,
    }
    assert is_in_envelope(summary) is True


def test_is_in_envelope_when_out_of_range():
    summary = {
        "h2_yield_mean_pct": 52.0,  # below 60
        "catalyst_activity_mean_pct": 18.4,  # below 55
        "cost_per_kg_mean_aud": -12.5,  # below 0.5
    }
    assert is_in_envelope(summary) is False


def test_is_in_envelope_when_missing_key():
    summary = {"h2_yield_mean_pct": 75.0}
    assert is_in_envelope(summary) is False


def test_assert_in_envelope_raises_with_messages():
    summary = {
        "h2_yield_mean_pct": 52.0,
        "catalyst_activity_mean_pct": 18.4,
        "cost_per_kg_mean_aud": -12.5,
    }
    with pytest.raises(EnvelopeViolation) as exc_info:
        assert_in_envelope(summary)
    msg = str(exc_info.value)
    assert "h2_yield_mean_pct" in msg
    assert "catalyst_activity_mean_pct" in msg
    assert "cost_per_kg_mean_aud" in msg


def test_boundary_inclusive():
    summary = {
        "h2_yield_mean_pct": 60.0,  # lower bound exactly
        "catalyst_activity_mean_pct": 92.0,  # upper bound exactly
        "cost_per_kg_mean_aud": 0.5,
    }
    assert is_in_envelope(summary) is True
