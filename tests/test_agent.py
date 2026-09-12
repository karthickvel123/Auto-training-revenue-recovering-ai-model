"""Integration test for the full agent pipeline — tests the REAL backend.agent.process_failed_payment."""
import pytest
from unittest.mock import patch, MagicMock
from backend.agent import process_failed_payment
from backend.models import Transaction, RecoveryAttempt, AgentDecision


class TestFullPipeline:
    """End-to-end test: classify → strategize → safety → recover → audit log."""

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_customer_action_recovery_pipeline(self, mock_get_client, sample_transaction, db_session):
        """insufficient_funds → customer_action → payment_link → allowed → recovery link created."""
        mock_client = MagicMock()
        mock_client.create_payment_link.return_value = {
            "id": "plink_pipeline_001",
            "short_url": "https://rzp.io/i/pipeline",
            "status": "created",
        }
        mock_get_client.return_value = mock_client

        process_failed_payment(sample_transaction.id, db_session)

        db_session.refresh(sample_transaction)

        # AI classification should be recorded
        assert sample_transaction.ai_classification is not None
        assert sample_transaction.ai_classification["failure_category"] == "customer_action"

        # Strategy should be selected
        assert sample_transaction.selected_strategy == "payment_link"

        # Safety should have passed
        assert sample_transaction.safety_decision is not None
        assert sample_transaction.safety_decision["allowed"] is True

        # Recovery should be in progress
        assert sample_transaction.recovery_status == "IN_PROGRESS"

        # Audit log should have 4 decisions
        decisions = db_session.query(AgentDecision).filter(
            AgentDecision.transaction_id == sample_transaction.id
        ).all()
        steps = [d.step for d in decisions]
        assert "classification" in steps
        assert "strategy" in steps
        assert "safety" in steps
        assert "action" in steps

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_security_failure_blocked(self, mock_get_client, security_transaction, db_session):
        """suspected_fraud → security → stop → blocked by safety gateway."""
        mock_get_client.return_value = MagicMock()

        process_failed_payment(security_transaction.id, db_session)
        db_session.refresh(security_transaction)

        assert security_transaction.ai_classification["failure_category"] == "security"
        assert security_transaction.selected_strategy == "stop"
        assert security_transaction.safety_decision["allowed"] is False
        assert security_transaction.recovery_status == "FAILED"

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_permanent_failure_stopped(self, mock_get_client, permanent_transaction, db_session):
        """invalid_card_number → permanent → stop → blocked."""
        mock_get_client.return_value = MagicMock()

        process_failed_payment(permanent_transaction.id, db_session)
        db_session.refresh(permanent_transaction)

        assert permanent_transaction.ai_classification["failure_category"] == "permanent"
        assert permanent_transaction.selected_strategy == "stop"
        assert permanent_transaction.recovery_status == "FAILED"

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_high_value_routed_to_human_review(self, mock_get_client, high_value_transaction, db_session):
        """High value + insufficient_funds → customer_action → payment_link → safety blocks → human_review."""
        mock_get_client.return_value = MagicMock()

        process_failed_payment(high_value_transaction.id, db_session)
        db_session.refresh(high_value_transaction)

        assert high_value_transaction.safety_decision["allowed"] is False
        assert high_value_transaction.safety_decision["overridden_strategy"] == "human_review"
        assert high_value_transaction.recovery_status == "HUMAN_REVIEW"

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_nonexistent_transaction_handled(self, mock_get_client, db_session):
        """Processing a non-existent transaction ID should not crash."""
        mock_get_client.return_value = MagicMock()
        process_failed_payment(99999, db_session)  # Should log error and return
