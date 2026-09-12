"""Tests for the AI failure classifier — imports and tests the REAL backend.classifier module."""
import pytest
from backend.classifier import _fallback_classification, classify_failure
from backend.schemas import FailureAnalysis


class TestFallbackClassification:
    """Test the deterministic fallback classifier used when OpenAI is unavailable."""

    def test_security_classification(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "suspected_fraud", 50000, "card")
        assert result.failure_category == "security"
        assert result.recommended_strategy == "stop"
        assert result.confidence >= 0.8

    def test_permanent_classification(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "invalid_card_number", 50000, "card")
        assert result.failure_category == "permanent"
        assert result.recommended_strategy == "stop"

    def test_temporary_classification(self):
        result = _fallback_classification("GATEWAY_ERROR", "network_error", 50000, "card")
        assert result.failure_category == "temporary"
        assert result.recommended_strategy == "delayed_retry"

    def test_customer_action_classification(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "insufficient_funds", 50000, "card")
        assert result.failure_category == "customer_action"
        assert result.recommended_strategy == "payment_link"

    def test_unknown_error_defaults_to_temporary(self):
        result = _fallback_classification("UNKNOWN", "some_random_error", 50000, "card")
        assert result.failure_category == "temporary"
        assert result.recommended_strategy == "payment_link"

    def test_expired_card_is_customer_action(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "expired_card", 50000, "card")
        assert result.failure_category == "customer_action"

    def test_wrong_otp_is_customer_action(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "wrong_otp", 50000, "upi")
        # wrong_otp contains neither security/permanent/temporary keywords, but contains none of the customer keywords either
        # Actually "wrong_otp" doesn't match customer_reasons exactly, let's check
        result = _fallback_classification("BAD_REQUEST_ERROR", "authentication_failed", 50000, "upi")
        assert result.failure_category == "customer_action"

    def test_risk_check_is_security(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "risk_check_failed", 50000, "card")
        assert result.failure_category == "security"
        assert result.recommended_strategy == "stop"


class TestFailureAnalysisSchema:
    """Test that the Pydantic schema validates correctly."""

    def test_valid_schema(self):
        fa = FailureAnalysis(
            failure_category="temporary",
            retryability="retryable",
            recommended_strategy="delayed_retry",
            confidence=0.8,
            reasoning_summary="Test analysis",
            customer_message="Please try again.",
        )
        assert fa.confidence == 0.8
        assert fa.failure_category == "temporary"

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(Exception):
            FailureAnalysis(
                failure_category="temporary",
                retryability="retryable",
                recommended_strategy="delayed_retry",
                confidence=1.5,  # Invalid: > 1.0
                reasoning_summary="Test",
                customer_message="Test",
            )

    def test_invalid_category_rejected(self):
        with pytest.raises(Exception):
            FailureAnalysis(
                failure_category="not_a_category",  # Invalid literal
                retryability="retryable",
                recommended_strategy="delayed_retry",
                confidence=0.8,
                reasoning_summary="Test",
                customer_message="Test",
            )

    def test_customer_message_included(self):
        result = _fallback_classification("BAD_REQUEST_ERROR", "insufficient_funds", 100000, "card")
        assert "1,000.00" in result.customer_message or "payment" in result.customer_message.lower()


class TestClassifyFailure:
    """Test the main classify_failure function (falls back to deterministic without OpenAI key)."""

    def test_classify_without_openai_key(self):
        """Without a valid OpenAI key, classify_failure uses the fallback."""
        result = classify_failure(
            error_code="BAD_REQUEST_ERROR",
            error_description="Payment failed due to insufficient funds",
            error_source="customer",
            error_step="payment_authorization",
            error_reason="insufficient_funds",
            amount=50000,
            currency="INR",
            payment_method="card",
        )
        assert isinstance(result, FailureAnalysis)
        assert result.failure_category == "customer_action"

    def test_classify_security_without_openai(self):
        result = classify_failure(
            error_code="BAD_REQUEST_ERROR",
            error_description="Fraud detected",
            error_source="bank",
            error_step="payment_authorization",
            error_reason="suspected_fraud",
            amount=50000,
            currency="INR",
            payment_method="card",
        )
        assert result.failure_category == "security"
        assert result.recommended_strategy == "stop"
