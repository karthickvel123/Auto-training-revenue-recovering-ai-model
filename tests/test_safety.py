"""Tests for the safety gateway — imports and tests the REAL backend.safety_gateway.check_safety."""
import pytest
from unittest.mock import patch
from backend.safety_gateway import check_safety
from backend.schemas import FailureAnalysis, SafetyVerdict
from backend.models import Transaction, RecoveryAttempt


def _make_analysis(category="customer_action", strategy="payment_link", confidence=0.9):
    """Helper to build a FailureAnalysis with defaults."""
    return FailureAnalysis(
        failure_category=category,
        retryability="needs_customer_action",
        recommended_strategy=strategy,
        confidence=confidence,
        reasoning_summary="Test analysis",
        customer_message="Please retry your payment.",
    )


# --- Rule 1: Security failures always blocked ---
def test_security_failure_blocked(security_transaction, db_session):
    analysis = _make_analysis(category="security", strategy="stop", confidence=0.9)
    verdict = check_safety(security_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert verdict.overridden_strategy == "stop"
    assert "Rule 1" in verdict.rule_triggered


# --- Rule 2: Permanent failures blocked for retry/link ---
def test_permanent_failure_blocked(permanent_transaction, db_session):
    analysis = _make_analysis(category="permanent", strategy="stop")
    verdict = check_safety(permanent_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert verdict.overridden_strategy == "stop"
    assert "Rule 2" in verdict.rule_triggered


def test_permanent_failure_allows_stop(permanent_transaction, db_session):
    analysis = _make_analysis(category="permanent", strategy="stop")
    verdict = check_safety(permanent_transaction, analysis, "stop", db_session)
    # stop strategy is not in ("delayed_retry", "payment_link"), so Rule 2 doesn't apply
    assert verdict.allowed


# --- Rule 3: Max retries exceeded ---
def test_max_retries_blocked(sample_transaction, db_session):
    sample_transaction.recovery_attempt_count = 3
    db_session.commit()
    analysis = _make_analysis()
    verdict = check_safety(sample_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert "Rule 3" in verdict.rule_triggered


# --- Rule 4: High-value transaction requires human review ---
def test_high_value_requires_review(high_value_transaction, db_session):
    analysis = _make_analysis()
    verdict = check_safety(high_value_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert verdict.overridden_strategy == "human_review"
    assert "Rule 4" in verdict.rule_triggered


def test_high_value_allows_human_review(high_value_transaction, db_session):
    analysis = _make_analysis()
    verdict = check_safety(high_value_transaction, analysis, "human_review", db_session)
    # human_review is already the strategy, Rule 4 doesn't trigger
    assert verdict.allowed


# --- Rule 5: Low AI confidence ---
def test_low_confidence_blocked(sample_transaction, db_session):
    analysis = _make_analysis(confidence=0.4)
    verdict = check_safety(sample_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert "Rule 5" in verdict.rule_triggered


def test_low_confidence_allows_human_review(sample_transaction, db_session):
    analysis = _make_analysis(confidence=0.4)
    verdict = check_safety(sample_transaction, analysis, "human_review", db_session)
    assert verdict.allowed


# --- Rule 6: Duplicate nudge prevention ---
def test_duplicate_nudge_blocked(sample_transaction, db_session):
    # Add an active pending recovery attempt
    attempt = RecoveryAttempt(
        transaction_id=sample_transaction.id,
        recovery_type="payment_link",
        status="PENDING",
    )
    db_session.add(attempt)
    db_session.commit()

    analysis = _make_analysis()
    verdict = check_safety(sample_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert "Rule 6" in verdict.rule_triggered


# --- Rule 7: Fraud keywords in error text ---
def test_fraud_keywords_blocked(sample_transaction, db_session):
    sample_transaction.error_reason = "suspected_fraud"
    sample_transaction.error_description = "Transaction flagged as suspicious"
    db_session.commit()

    analysis = _make_analysis()
    verdict = check_safety(sample_transaction, analysis, "payment_link", db_session)
    assert not verdict.allowed
    assert "Rule 7" in verdict.rule_triggered


# --- Happy path: all rules pass ---
def test_safe_payment_allowed(sample_transaction, db_session):
    analysis = _make_analysis()
    verdict = check_safety(sample_transaction, analysis, "payment_link", db_session)
    assert verdict.allowed
    assert verdict.reason == "All safety checks passed"
