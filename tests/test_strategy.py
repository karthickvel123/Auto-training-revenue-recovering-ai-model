"""Tests for the adaptive strategy engine — imports and tests the REAL backend.strategy_engine."""
import pytest
from backend.strategy_engine import select_strategy
from backend.schemas import FailureAnalysis, StrategyDecision
from backend.models import Transaction, StrategyStats


def _make_analysis(category="customer_action", strategy="payment_link", confidence=0.8):
    return FailureAnalysis(
        failure_category=category,
        retryability="needs_customer_action",
        recommended_strategy=strategy,
        confidence=confidence,
        reasoning_summary="Test",
        customer_message="Please retry.",
    )


class TestColdStart:
    """When there's no historical data, the LLM recommendation should be used."""

    def test_uses_llm_recommendation(self, sample_transaction, db_session):
        analysis = _make_analysis(strategy="payment_link")
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert decision.selected_strategy == "payment_link"
        assert not decision.data_driven

    def test_returns_strategy_decision_model(self, sample_transaction, db_session):
        analysis = _make_analysis()
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert isinstance(decision, StrategyDecision)
        assert decision.llm_recommendation == "payment_link"


class TestHardConstraints:
    """Hard constraints override everything — security and permanent always stop."""

    def test_security_always_stops(self, sample_transaction, db_session):
        analysis = _make_analysis(category="security", strategy="payment_link")
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert decision.selected_strategy == "stop"
        assert not decision.data_driven

    def test_permanent_always_stops(self, sample_transaction, db_session):
        analysis = _make_analysis(category="permanent", strategy="payment_link")
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert decision.selected_strategy == "stop"

    def test_delayed_retry_only_for_temporary(self, sample_transaction, db_session):
        analysis = _make_analysis(category="customer_action", strategy="delayed_retry")
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert decision.selected_strategy == "payment_link"
        assert "Constraint" in (decision.override_reason or "")


class TestDataDrivenOverride:
    """When historical data has enough samples, data-driven override activates."""

    def test_override_when_historical_is_better(self, sample_transaction, db_session):
        # Seed strategy stats: payment_link has 50% rate, delayed_retry has 5%
        stats_link = StrategyStats(
            failure_category="customer_action",
            error_reason="insufficient_funds",
            strategy="payment_link",
            attempts=20,
            successful_recoveries=10,
            recovery_rate=0.5,
            total_amount_attempted=1000000,
            total_amount_recovered=500000,
        )
        stats_retry = StrategyStats(
            failure_category="customer_action",
            error_reason="insufficient_funds",
            strategy="delayed_retry",
            attempts=20,
            successful_recoveries=1,
            recovery_rate=0.05,
            total_amount_attempted=1000000,
            total_amount_recovered=50000,
        )
        db_session.add_all([stats_link, stats_retry])
        db_session.commit()

        analysis = _make_analysis(strategy="delayed_retry")
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert decision.selected_strategy == "payment_link"
        assert decision.data_driven

    def test_no_override_with_insufficient_data(self, sample_transaction, db_session):
        # Only 5 attempts — below the 10-attempt threshold
        stats = StrategyStats(
            failure_category="customer_action",
            error_reason="insufficient_funds",
            strategy="payment_link",
            attempts=5,
            successful_recoveries=4,
            recovery_rate=0.8,
            total_amount_attempted=250000,
            total_amount_recovered=200000,
        )
        db_session.add(stats)
        db_session.commit()

        analysis = _make_analysis(strategy="delayed_retry")
        decision = select_strategy(sample_transaction, analysis, db_session)
        # Not enough data to override, so uses LLM rec (but then constraint applies)
        assert not decision.data_driven

    def test_data_driven_reset_on_hard_constraint(self, sample_transaction, db_session):
        """When data selects a strategy but hard constraint overrides it, data_driven must be False."""
        stats_link = StrategyStats(
            failure_category="security",
            error_reason="suspected_fraud",
            strategy="payment_link",
            attempts=20,
            successful_recoveries=15,
            recovery_rate=0.75,
            total_amount_attempted=1000000,
            total_amount_recovered=750000,
        )
        stats_retry = StrategyStats(
            failure_category="security",
            error_reason="suspected_fraud",
            strategy="delayed_retry",
            attempts=20,
            successful_recoveries=1,
            recovery_rate=0.05,
            total_amount_attempted=1000000,
            total_amount_recovered=50000,
        )
        db_session.add_all([stats_link, stats_retry])
        db_session.commit()

        sample_transaction.error_reason = "suspected_fraud"
        db_session.commit()

        analysis = _make_analysis(category="security", strategy="delayed_retry")
        decision = select_strategy(sample_transaction, analysis, db_session)
        assert decision.selected_strategy == "stop"
        assert not decision.data_driven  # Hard constraint overrides data-driven
