"""Tests for the escalation engine — imports and tests the REAL backend.escalation_engine."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from backend.escalation_engine import check_and_escalate, get_escalation_chain
from backend.models import Transaction, RecoveryAttempt


class TestCheckAndEscalate:
    """Test the escalation engine's automatic level promotion."""

    @patch("backend.escalation_engine.get_razorpay_client")
    def test_level1_to_level2_escalation(self, mock_get_client, sample_transaction, db_session):
        mock_client = MagicMock()
        mock_client.create_payment_link.return_value = {
            "id": "plink_esc_001",
            "short_url": "https://rzp.io/i/esc",
        }
        mock_get_client.return_value = mock_client

        # Create a stale Level 1 attempt (older than escalation timeout)
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        attempt = RecoveryAttempt(
            transaction_id=sample_transaction.id,
            recovery_type="payment_link",
            status="PENDING",
            escalation_level=1,
            created_at=old_time,
        )
        db_session.add(attempt)
        db_session.commit()

        check_and_escalate(db_session)

        # Old attempt should be marked ESCALATED
        db_session.refresh(attempt)
        assert attempt.status == "ESCALATED"

        # New Level 2 attempt should exist
        new_attempt = db_session.query(RecoveryAttempt).filter(
            RecoveryAttempt.transaction_id == sample_transaction.id,
            RecoveryAttempt.escalation_level == 2,
        ).first()
        assert new_attempt is not None
        assert new_attempt.recovery_type == "alternative_payment_method"
        assert new_attempt.status == "PENDING"

    @patch("backend.escalation_engine.get_razorpay_client")
    def test_level2_to_level3_escalation(self, mock_get_client, sample_transaction, db_session):
        mock_get_client.return_value = MagicMock()

        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        attempt = RecoveryAttempt(
            transaction_id=sample_transaction.id,
            recovery_type="alternative_payment_method",
            status="PENDING",
            escalation_level=2,
            created_at=old_time,
        )
        db_session.add(attempt)
        db_session.commit()

        check_and_escalate(db_session)

        new_attempt = db_session.query(RecoveryAttempt).filter(
            RecoveryAttempt.transaction_id == sample_transaction.id,
            RecoveryAttempt.escalation_level == 3,
        ).first()
        assert new_attempt is not None
        assert new_attempt.recovery_type == "human_review"
        assert sample_transaction.recovery_status == "HUMAN_REVIEW"

    @patch("backend.escalation_engine.get_razorpay_client")
    def test_no_escalation_before_timeout(self, mock_get_client, sample_transaction, db_session):
        mock_get_client.return_value = MagicMock()

        # Recent attempt — should NOT escalate
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        attempt = RecoveryAttempt(
            transaction_id=sample_transaction.id,
            recovery_type="payment_link",
            status="PENDING",
            escalation_level=1,
            created_at=recent_time,
        )
        db_session.add(attempt)
        db_session.commit()

        check_and_escalate(db_session)

        db_session.refresh(attempt)
        assert attempt.status == "PENDING"  # Unchanged

    @patch("backend.escalation_engine.get_razorpay_client")
    def test_skips_recovered_transactions(self, mock_get_client, sample_transaction, db_session):
        mock_get_client.return_value = MagicMock()
        sample_transaction.recovery_status = "SUCCESS"
        db_session.commit()

        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        attempt = RecoveryAttempt(
            transaction_id=sample_transaction.id,
            recovery_type="payment_link",
            status="PENDING",
            escalation_level=1,
            created_at=old_time,
        )
        db_session.add(attempt)
        db_session.commit()

        check_and_escalate(db_session)
        db_session.refresh(attempt)
        assert attempt.status == "EXPIRED"


class TestGetEscalationChain:
    """Test retrieval of escalation history."""

    def test_returns_ordered_chain(self, sample_transaction, db_session):
        for level in [1, 2, 3]:
            attempt = RecoveryAttempt(
                transaction_id=sample_transaction.id,
                recovery_type="payment_link",
                status="PENDING",
                escalation_level=level,
            )
            db_session.add(attempt)
        db_session.commit()

        chain = get_escalation_chain(sample_transaction.id, db_session)
        assert len(chain) == 3
        assert [a.escalation_level for a in chain] == [1, 2, 3]
