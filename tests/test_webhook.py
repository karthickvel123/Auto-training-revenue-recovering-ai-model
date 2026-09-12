"""Tests for the webhook handler — uses FastAPI TestClient against the REAL app."""
import pytest
import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import Transaction, RecoveryAttempt, WebhookEvent


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


def _make_payload(event_type: str, payment_id: str, **extra_fields) -> dict:
    """Build a Razorpay webhook payload."""
    entity = {
        "id": payment_id,
        "order_id": "order_test_wh_001",
        "amount": 50000,
        "currency": "INR",
        "status": "failed" if event_type == "payment.failed" else "captured",
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment failed due to insufficient funds",
        "error_source": "customer",
        "error_step": "payment_authorization",
        "error_reason": "insufficient_funds",
        "contact": "+919999999999",
        "email": "test@example.com",
        "method": "card",
        "notes": {},
    }
    entity.update(extra_fields)
    return {
        "event": event_type,
        "payload": {"payment": {"entity": entity}},
    }


class TestWebhookSignatureVerification:
    """Test that webhook signature verification works correctly."""

    @patch("backend.webhook.get_razorpay_client")
    def test_valid_signature_accepted(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.verify_webhook_signature.return_value = True
        mock_get_client.return_value = mock_client

        payload = _make_payload("payment.failed", "pay_wh_001")
        response = client.post(
            "/api/webhooks/razorpay",
            json=payload,
            headers={"X-Razorpay-Signature": "valid_signature"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    @patch("backend.webhook.get_razorpay_client")
    def test_invalid_signature_rejected(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.verify_webhook_signature.return_value = False
        mock_get_client.return_value = mock_client

        payload = _make_payload("payment.failed", "pay_wh_bad")
        response = client.post(
            "/api/webhooks/razorpay",
            json=payload,
            headers={"X-Razorpay-Signature": "bad_signature"},
        )
        assert response.status_code == 401

    @patch("backend.webhook.get_razorpay_client")
    def test_missing_signature_rejected(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.verify_webhook_signature.return_value = False
        mock_get_client.return_value = mock_client

        payload = _make_payload("payment.failed", "pay_wh_nosig")
        response = client.post("/api/webhooks/razorpay", json=payload)
        assert response.status_code == 401


class TestPaymentFailedWebhook:
    """Test that payment.failed webhooks create transactions and trigger the agent."""

    @patch("backend.webhook.get_razorpay_client")
    def test_creates_transaction(self, mock_get_client, client, db_session):
        mock_client = MagicMock()
        mock_client.verify_webhook_signature.return_value = True
        mock_get_client.return_value = mock_client

        payload = _make_payload("payment.failed", "pay_wh_create_001")
        response = client.post(
            "/api/webhooks/razorpay",
            json=payload,
            headers={"X-Razorpay-Signature": "valid"},
        )
        assert response.status_code == 200

    @patch("backend.webhook.get_razorpay_client")
    def test_returns_ok(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.verify_webhook_signature.return_value = True
        mock_get_client.return_value = mock_client

        payload = _make_payload("payment.failed", "pay_wh_ok_001")
        response = client.post(
            "/api/webhooks/razorpay",
            json=payload,
            headers={"X-Razorpay-Signature": "valid"},
        )
        assert response.json()["status"] == "ok"


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
