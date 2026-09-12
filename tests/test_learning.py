"""Tests for the learning engine — imports and tests the REAL backend.learning_engine."""
import pytest
from backend.learning_engine import record_outcome
from backend.models import StrategyStats


class TestRecordOutcome:
    """Test the strategy statistics recording and learning loop."""

    def test_record_successful_outcome(self, db_session):
        record_outcome("customer_action", "insufficient_funds", "payment_link", True, 50000, db_session)
        stats = db_session.query(StrategyStats).first()
        assert stats is not None
        assert stats.attempts == 1
        assert stats.successful_recoveries == 1
        assert stats.recovery_rate == 1.0
        assert stats.total_amount_recovered == 50000

    def test_record_failed_outcome(self, db_session):
        record_outcome("customer_action", "insufficient_funds", "payment_link", False, 50000, db_session)
        stats = db_session.query(StrategyStats).first()
        assert stats.attempts == 1
        assert stats.successful_recoveries == 0
        assert stats.recovery_rate == 0.0
        assert stats.total_amount_recovered == 0

    def test_recovery_rate_calculation(self, db_session):
        record_outcome("temporary", "network_error", "delayed_retry", True, 50000, db_session)
        record_outcome("temporary", "network_error", "delayed_retry", False, 50000, db_session)
        record_outcome("temporary", "network_error", "delayed_retry", True, 50000, db_session)
        stats = db_session.query(StrategyStats).first()
        assert stats.attempts == 3
        assert stats.successful_recoveries == 2
        assert abs(stats.recovery_rate - 2 / 3) < 0.001

    def test_creates_new_stats_row_per_combination(self, db_session):
        record_outcome("customer_action", "insufficient_funds", "payment_link", True, 50000, db_session)
        record_outcome("customer_action", "insufficient_funds", "delayed_retry", True, 50000, db_session)
        record_outcome("temporary", "network_error", "delayed_retry", True, 50000, db_session)
        all_stats = db_session.query(StrategyStats).all()
        assert len(all_stats) == 3

    def test_upserts_existing_row(self, db_session):
        record_outcome("customer_action", "insufficient_funds", "payment_link", True, 50000, db_session)
        record_outcome("customer_action", "insufficient_funds", "payment_link", False, 30000, db_session)
        all_stats = db_session.query(StrategyStats).all()
        assert len(all_stats) == 1
        stats = all_stats[0]
        assert stats.attempts == 2
        assert stats.total_amount_attempted == 80000

    def test_handles_none_inputs(self, db_session):
        record_outcome(None, None, None, True, 50000, db_session)
        stats = db_session.query(StrategyStats).first()
        assert stats.failure_category == "unknown"
        assert stats.error_reason == "unknown"
        assert stats.strategy == "unknown"

    def test_amount_tracking(self, db_session):
        record_outcome("customer_action", "wrong_otp", "payment_link", True, 100000, db_session)
        record_outcome("customer_action", "wrong_otp", "payment_link", False, 200000, db_session)
        stats = db_session.query(StrategyStats).first()
        assert stats.total_amount_attempted == 300000
        assert stats.total_amount_recovered == 100000
