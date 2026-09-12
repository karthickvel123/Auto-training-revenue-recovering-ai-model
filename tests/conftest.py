"""Shared pytest fixtures for the Adaptive Revenue Recovery Agent test suite."""
import sys
from unittest.mock import MagicMock

# Mock razorpay module before any backend imports
mock_rzp = MagicMock()
mock_rzp.errors = MagicMock()
mock_rzp.errors.SignatureVerificationError = type("SignatureVerificationError", (Exception,), {})
sys.modules.setdefault("razorpay", mock_rzp)
sys.modules.setdefault("razorpay.errors", mock_rzp.errors)

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from backend.database import Base
from backend.models import Transaction, RecoveryAttempt, StrategyStats, WebhookEvent, AgentDecision


@pytest.fixture
def db_session() -> Session:
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def sample_transaction(db_session: Session) -> Transaction:
    """Create and return a standard failed transaction for testing."""
    txn = Transaction(
        transaction_id="pay_test_001",
        order_id="order_test_001",
        amount=50000,
        currency="INR",
        status="FAILED",
        error_code="BAD_REQUEST_ERROR",
        error_description="Payment failed due to insufficient funds",
        error_source="customer",
        error_step="payment_authorization",
        error_reason="insufficient_funds",
        customer_contact="+919999999999",
        customer_email="test@example.com",
        payment_method="card",
        recovery_attempt_count=0,
        recovery_status="PENDING",
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


@pytest.fixture
def high_value_transaction(db_session: Session) -> Transaction:
    """Create a high-value transaction (>= 10,000 INR = 1,000,000 paise)."""
    txn = Transaction(
        transaction_id="pay_highval_001",
        order_id="order_highval_001",
        amount=2000000,  # 20,000 INR
        currency="INR",
        status="FAILED",
        error_code="BAD_REQUEST_ERROR",
        error_reason="insufficient_funds",
        error_source="customer",
        error_step="payment_authorization",
        customer_email="highval@example.com",
        payment_method="card",
        recovery_attempt_count=0,
        recovery_status="PENDING",
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


@pytest.fixture
def security_transaction(db_session: Session) -> Transaction:
    """Create a security/fraud-flagged transaction."""
    txn = Transaction(
        transaction_id="pay_fraud_001",
        order_id="order_fraud_001",
        amount=50000,
        currency="INR",
        status="FAILED",
        error_code="BAD_REQUEST_ERROR",
        error_reason="suspected_fraud",
        error_source="bank",
        error_step="payment_authorization",
        customer_email="fraud@example.com",
        payment_method="card",
        recovery_attempt_count=0,
        recovery_status="PENDING",
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


@pytest.fixture
def permanent_transaction(db_session: Session) -> Transaction:
    """Create a permanent failure transaction."""
    txn = Transaction(
        transaction_id="pay_perm_001",
        order_id="order_perm_001",
        amount=50000,
        currency="INR",
        status="FAILED",
        error_code="BAD_REQUEST_ERROR",
        error_reason="invalid_card_number",
        error_source="bank",
        error_step="payment_authorization",
        customer_email="invalid@example.com",
        payment_method="card",
        recovery_attempt_count=0,
        recovery_status="PENDING",
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


@pytest.fixture
def mock_razorpay_client():
    """Return a mock Razorpay client for testing without live API calls."""
    client = MagicMock()
    client.create_order.return_value = {
        "id": "order_mock_001",
        "amount": 50000,
        "currency": "INR",
        "status": "created",
    }
    client.create_payment_link.return_value = {
        "id": "plink_mock_001",
        "amount": 50000,
        "short_url": "https://rzp.io/i/mock_link",
        "status": "created",
    }
    client.verify_webhook_signature.return_value = True
    return client
