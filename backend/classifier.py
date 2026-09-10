import openai
import json
import logging
from backend.config import get_settings
from backend.schemas import FailureAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a payment failure analysis expert for Indian payment systems (Razorpay).
Analyze the payment failure and return a structured classification.

Categories:
- temporary: Transient issues (network timeout, bank server down, rate limiting). Usually resolve on retry.
- customer_action: Customer needs to act (insufficient funds, expired card, wrong OTP). Needs a new payment attempt.
- permanent: Cannot be retried (invalid card number, account closed, unsupported card). No point retrying.
- security: Fraud or risk flags. NEVER retry automatically.

Strategies:
- delayed_retry: Wait and create a new payment opportunity. Only for temporary failures.
- payment_link: Send a payment link to the customer. Best for customer_action failures.
- alternative_payment_method: Suggest a different payment method (UPI instead of card).
- human_review: Escalate to manual review. For ambiguous or high-risk cases.
- stop: Do not attempt recovery. For permanent or security failures.

Be conservative with confidence scores. If unsure, recommend human_review.
Generate a helpful, professional customer message (no technical jargon).
"""

def classify_failure(error_code: str, error_description: str, error_source: str,
                     error_step: str, error_reason: str, amount: int,
                     currency: str, payment_method: str,
                     customer_email: str = None) -> FailureAnalysis:
    """Send failure info to LLM and get structured classification."""
    settings = get_settings()
    
    # Build context
    failure_context = {
        "error_code": error_code or "unknown",
        "error_description": error_description or "No description",
        "error_source": error_source or "unknown",
        "error_step": error_step or "unknown",
        "error_reason": error_reason or "unknown",
        "amount_paise": amount,
        "amount_rupees": amount / 100,
        "currency": currency or "INR",
        "payment_method": payment_method or "unknown",
    }
    
    user_message = f"Analyze this Razorpay payment failure:\n{json.dumps(failure_context, indent=2)}"
    
    if not settings.openai_api_key or "xxxx" in settings.openai_api_key:
        logger.info("OpenAI API key is empty or placeholder. Using deterministic fallback classification.")
        return _fallback_classification(error_code, error_reason, amount, payment_method)
    
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            response_format=FailureAnalysis,
        )
        result = response.choices[0].message.parsed
        logger.info(f"Classification: {result.failure_category} / {result.recommended_strategy} (confidence: {result.confidence})")
        return result
    except Exception as e:
        logger.error(f"LLM classification failed: {e}. Using fallback.")
        return _fallback_classification(error_code, error_reason, amount, payment_method)

def _fallback_classification(error_code, error_reason, amount, payment_method) -> FailureAnalysis:
    """Deterministic fallback when LLM is unavailable."""
    # Map common Razorpay errors
    security_reasons = {"fraud", "risk_check_failed", "international_transaction_not_allowed"}
    permanent_reasons = {"invalid_card_number", "card_not_supported", "account_closed"}
    temporary_reasons = {"network_error", "gateway_error", "server_error", "timeout"}
    customer_reasons = {"insufficient_funds", "expired_card", "wrong_otp", "authentication_failed", "card_declined"}
    
    reason = (error_reason or "").lower()
    
    if any(r in reason for r in security_reasons):
        return FailureAnalysis(
            failure_category="security", retryability="do_not_retry",
            recommended_strategy="stop", confidence=0.9,
            reasoning_summary=f"Security-related failure: {error_reason}",
            customer_message="Your payment could not be processed. Please contact your bank."
        )
    elif any(r in reason for r in permanent_reasons):
        return FailureAnalysis(
            failure_category="permanent", retryability="do_not_retry",
            recommended_strategy="stop", confidence=0.85,
            reasoning_summary=f"Permanent failure: {error_reason}",
            customer_message="This payment method cannot be used. Please try a different one."
        )
    elif any(r in reason for r in temporary_reasons):
        return FailureAnalysis(
            failure_category="temporary", retryability="retryable",
            recommended_strategy="delayed_retry", confidence=0.7,
            reasoning_summary=f"Temporary failure: {error_reason}",
            customer_message="We encountered a temporary issue. Please try again shortly."
        )
    elif any(r in reason for r in customer_reasons):
        return FailureAnalysis(
            failure_category="customer_action", retryability="needs_customer_action",
            recommended_strategy="payment_link", confidence=0.75,
            reasoning_summary=f"Customer action needed: {error_reason}",
            customer_message=f"Your payment of ₹{amount/100:,.2f} could not be completed. Please try again with sufficient funds or a different payment method."
        )
    else:
        return FailureAnalysis(
            failure_category="temporary", retryability="needs_customer_action",
            recommended_strategy="payment_link", confidence=0.5,
            reasoning_summary=f"Unknown failure pattern: {error_code} / {error_reason}",
            customer_message=f"Your payment of ₹{amount/100:,.2f} could not be completed. Please try again."
        )
