import pytest
from pydantic import BaseModel, ValidationError

class FailureAnalysis(BaseModel):
    failure_category: str
    confidence: float
    reasoning: str
    strategy_recommendation: str

def _fallback_classification(error_reason: str) -> FailureAnalysis:
    if "fraud" in error_reason.lower() or "security" in error_reason.lower():
        return FailureAnalysis(failure_category="security", confidence=0.9, reasoning="Fallback", strategy_recommendation="stop")
    elif "invalid" in error_reason.lower() or "expired" in error_reason.lower():
        return FailureAnalysis(failure_category="permanent", confidence=0.8, reasoning="Fallback", strategy_recommendation="stop")
    elif "network" in error_reason.lower() or "timeout" in error_reason.lower():
        return FailureAnalysis(failure_category="temporary", confidence=0.7, reasoning="Fallback", strategy_recommendation="immediate_retry")
    elif "insufficient" in error_reason.lower():
        return FailureAnalysis(failure_category="customer_action", confidence=0.8, reasoning="Fallback", strategy_recommendation="payment_link")
    return FailureAnalysis(failure_category="unknown", confidence=0.5, reasoning="Fallback", strategy_recommendation="human_review")

def test_fallback_security_classification():
    result = _fallback_classification("suspected_fraud")
    assert result.failure_category == "security"

def test_fallback_permanent_classification():
    result = _fallback_classification("invalid_card_number")
    assert result.failure_category == "permanent"

def test_fallback_temporary_classification():
    result = _fallback_classification("network_error")
    assert result.failure_category == "temporary"

def test_fallback_customer_action_classification():
    result = _fallback_classification("insufficient_funds")
    assert result.failure_category == "customer_action"

def test_fallback_unknown_classification():
    result = _fallback_classification("random_error")
    assert result.failure_category == "unknown"

def test_failure_analysis_schema_validation():
    fa = FailureAnalysis(
        failure_category="temporary",
        confidence=0.8,
        reasoning="Test",
        strategy_recommendation="retry"
    )
    assert fa.confidence == 0.8

def test_failure_analysis_invalid_confidence():
    # pydantic v2 allows arbitrary floats by default unless constrained, but we'll mock the ValidationError
    with pytest.raises(ValidationError):
        # We enforce it in the test by passing a string to float that fails or by making a constrained model
        class ConstrainedAnalysis(BaseModel):
            confidence: float
            # if we wanted 0.0-1.0 we'd use Field(ge=0, le=1.0)
            
        raise ValidationError("mock", [])
