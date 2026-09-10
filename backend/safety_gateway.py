import logging
from backend.schemas import FailureAnalysis, SafetyVerdict
from backend.config import get_settings
from backend.models import Transaction, RecoveryAttempt
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

def check_safety(transaction: Transaction, analysis: FailureAnalysis, 
                 proposed_strategy: str, db: Session) -> SafetyVerdict:
    """Apply deterministic safety rules. Returns SafetyVerdict."""
    settings = get_settings()
    
    # Rule 1: NEVER retry security/fraud failures
    if analysis.failure_category == "security":
        logger.warning(f"Safety Rule 1 triggered: Security failure category blocked.")
        return SafetyVerdict(allowed=False, reason="Security and fraud failures cannot be retried.", rule_triggered="Rule 1: Security Block", overridden_strategy="stop")
    
    # Rule 2: NEVER retry permanently invalid payments  
    if analysis.failure_category == "permanent" and proposed_strategy in ("delayed_retry", "payment_link"):
        logger.warning(f"Safety Rule 2 triggered: Permanent failure category blocked for strategy {proposed_strategy}.")
        return SafetyVerdict(allowed=False, reason="Permanent failures cannot be retried automatically.", rule_triggered="Rule 2: Permanent Block", overridden_strategy="stop")
    
    # Rule 3: Max retry count exceeded
    if transaction.recovery_attempt_count >= settings.max_retry_count:
        logger.warning(f"Safety Rule 3 triggered: Max retry count ({settings.max_retry_count}) exceeded.")
        return SafetyVerdict(allowed=False, reason="Maximum automatic recovery attempts exceeded.", rule_triggered="Rule 3: Max Retries", overridden_strategy="human_review")
    
    # Rule 4: High-value transaction requires human review
    if transaction.amount >= settings.high_value_threshold and proposed_strategy != "human_review":
        logger.warning(f"Safety Rule 4 triggered: High-value transaction requires human review.")
        return SafetyVerdict(allowed=False, reason="Transaction amount exceeds automatic processing threshold.", rule_triggered="Rule 4: High Value", overridden_strategy="human_review")
    
    # Rule 5: Low AI confidence
    if analysis.confidence < settings.min_ai_confidence and proposed_strategy not in ("human_review", "stop"):
        logger.warning(f"Safety Rule 5 triggered: Low AI confidence ({analysis.confidence} < {settings.min_ai_confidence}).")
        return SafetyVerdict(allowed=False, reason="AI classification confidence is too low for automatic action.", rule_triggered="Rule 5: Low Confidence", overridden_strategy="human_review")
    
    # Rule 6: Duplicate nudge prevention - check if active payment link exists
    active_links = db.query(RecoveryAttempt).filter(
        RecoveryAttempt.transaction_id == transaction.id,
        RecoveryAttempt.status == "PENDING"
    ).count()
    if active_links > 0 and proposed_strategy == "payment_link":
        logger.warning(f"Safety Rule 6 triggered: Active payment link already exists.")
        return SafetyVerdict(allowed=False, reason="An active payment link already exists for this transaction.", rule_triggered="Rule 6: Duplicate Nudge", overridden_strategy="stop")
    
    # Rule 7: Fraud signal keywords
    fraud_keywords = {"fraud", "risk", "suspicious", "blocked", "blacklist"}
    error_text = f"{transaction.error_reason or ''} {transaction.error_description or ''}".lower()
    if any(kw in error_text for kw in fraud_keywords):
        logger.warning(f"Safety Rule 7 triggered: Fraud signal keywords detected in error text.")
        return SafetyVerdict(allowed=False, reason="Fraud signal keywords detected in error text.", rule_triggered="Rule 7: Fraud Keywords", overridden_strategy="human_review")
    
    # All checks passed
    return SafetyVerdict(allowed=True, reason="All safety checks passed")
