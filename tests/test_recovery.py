"""Tests for the recovery engine — imports and tests the REAL backend.recovery_engine."""
import pytest
from unittest.mock import patch, MagicMock
from backend.recovery_engine import execute_recovery
from backend.models import Transaction, RecoveryAttempt


class TestPaymentLinkRecovery:
    """Test recovery via payment link strategy."""

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_creates_payment_link(self, mock_get_client, sample_transaction, db_session):
        mock_client = MagicMock()
        mock_client.create_payment_link.return_value = {
            "id": "plink_test_001",
            "short_url": "https://rzp.io/i/test",
            "status": "created",
        }
        mock_get_client.return_value = mock_client

        attempt = execute_recovery(sample_transaction, "payment_link", "Please complete your payment.", db_session)
        db_session.commit()

        assert attempt.payment_link_id == "plink_test_001"
        assert attempt.payment_link_url == "https://rzp.io/i/test"
        assert attempt.status == "PENDING"
        assert sample_transaction.recovery_status == "IN_PROGRESS"
        assert sample_transaction.recovery_attempt_count == 1

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_passes_recovery_notes(self, mock_get_client, sample_transaction, db_session):
        mock_client = MagicMock()
        mock_client.create_payment_link.return_value = {"id": "plink_002", "short_url": "https://rzp.io/i/test2"}
        mock_get_client.return_value = mock_client

        execute_recovery(sample_transaction, "payment_link", "Retry", db_session)
        db_session.commit()

        # Verify notes were passed with recovery_for
        call_kwargs = mock_client.create_payment_link.call_args
        assert call_kwargs is not None
        notes_arg = call_kwargs.kwargs.get("notes") or call_kwargs[1].get("notes")
        assert notes_arg is not None
        assert notes_arg["recovery_for"] == "pay_test_001"


class TestDelayedRetry:
    """Test recovery via delayed retry strategy."""

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_creates_order_and_link(self, mock_get_client, sample_transaction, db_session):
        mock_client = MagicMock()
        mock_client.create_order.return_value = {"id": "order_retry_001", "status": "created"}
        mock_client.create_payment_link.return_value = {"id": "plink_retry_001", "short_url": "https://rzp.io/i/retry"}
        mock_get_client.return_value = mock_client

        attempt = execute_recovery(sample_transaction, "delayed_retry", "Retry payment", db_session)
        db_session.commit()

        assert attempt.recovery_order_id == "order_retry_001"
        assert attempt.payment_link_id == "plink_retry_001"
        assert sample_transaction.recovery_status == "IN_PROGRESS"


class TestHumanReviewRecovery:
    """Test human review strategy."""

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_human_review_status(self, mock_get_client, sample_transaction, db_session):
        mock_get_client.return_value = MagicMock()
        attempt = execute_recovery(sample_transaction, "human_review", "Manual review needed", db_session)
        db_session.commit()

        assert attempt.status == "PENDING"
        assert sample_transaction.recovery_status == "HUMAN_REVIEW"


class TestStopRecovery:
    """Test stop strategy."""

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_stop_marks_failed(self, mock_get_client, sample_transaction, db_session):
        mock_get_client.return_value = MagicMock()
        attempt = execute_recovery(sample_transaction, "stop", "Cannot recover", db_session)
        db_session.commit()

        assert attempt.status == "FAILED"
        assert sample_transaction.recovery_status == "FAILED"


class TestErrorHandling:
    """Test graceful error handling during recovery."""

    @patch("backend.recovery_engine.get_razorpay_client")
    def test_exception_returns_failed_attempt(self, mock_get_client, sample_transaction, db_session):
        mock_client = MagicMock()
        mock_client.create_payment_link.side_effect = Exception("API timeout")
        mock_get_client.return_value = mock_client

        attempt = execute_recovery(sample_transaction, "payment_link", "Test", db_session)
        db_session.commit()

        assert attempt.status == "FAILED"
