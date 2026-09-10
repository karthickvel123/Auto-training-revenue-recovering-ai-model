import logging
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from backend.models import RecoveryAttempt, Transaction
from backend.config import get_settings
from backend.razorpay_client import get_razorpay_client

logger = logging.getLogger(__name__)

def check_and_escalate(db: Session):
    """Scan for pending recovery attempts that need escalation."""
    settings = get_settings()
    timeout_delta = timedelta(minutes=settings.escalation_timeout_minutes)
    threshold_time = datetime.now(timezone.utc) - timeout_delta
    
    pending_attempts = db.query(RecoveryAttempt).filter(
        RecoveryAttempt.status == "PENDING",
        RecoveryAttempt.created_at < threshold_time
    ).all()
    
    client = get_razorpay_client()

    for attempt in pending_attempts:
        transaction = db.query(Transaction).filter(Transaction.id == attempt.transaction_id).first()
        if not transaction or transaction.recovery_status == "SUCCESS":
            attempt.status = "EXPIRED"
            continue

        try:
            if attempt.escalation_level == 1:
                # Escalate to Level 2: Alternative Payment Method (UPI)
                logger.info(f"Escalating transaction {transaction.id} to level 2 (Alternative Payment).")
                attempt.status = "ESCALATED"
                
                new_attempt = RecoveryAttempt(
                    transaction_id=transaction.id,
                    recovery_type="alternative_payment_method",
                    customer_message="Your previous payment attempt is pending. We recommend trying UPI for faster processing.",
                    escalation_level=2,
                    status="PENDING"
                )
                
                ref_id = f"escalation_2_{transaction.transaction_id}_{int(time.time())}"
                expire_by = int(time.time()) + (24 * 60 * 60)
                link_res = client.create_payment_link(
                    amount=transaction.amount,
                    currency=transaction.currency,
                    description=new_attempt.customer_message,
                    customer_email=transaction.customer_email,
                    customer_contact=transaction.customer_contact,
                    reference_id=ref_id,
                    expire_by=expire_by,
                    callback_url=None
                )
                new_attempt.payment_link_id = link_res.get("id")
                new_attempt.payment_link_url = link_res.get("short_url")
                
                db.add(new_attempt)
                transaction.recovery_attempt_count += 1
                
            elif attempt.escalation_level == 2:
                # Escalate to Level 3: Human Review
                logger.info(f"Escalating transaction {transaction.id} to level 3 (Human Review).")
                attempt.status = "ESCALATED"
                
                new_attempt = RecoveryAttempt(
                    transaction_id=transaction.id,
                    recovery_type="human_review",
                    customer_message="This payment requires manual review.",
                    escalation_level=3,
                    status="PENDING"
                )
                db.add(new_attempt)
                transaction.recovery_status = "HUMAN_REVIEW"
                transaction.recovery_attempt_count += 1
                
            elif attempt.escalation_level >= 3:
                # Fully escalated, leave as is or mark expired
                pass
                
        except Exception as e:
            logger.error(f"Failed to escalate attempt {attempt.id}: {e}")
            
    db.commit()

def get_escalation_chain(transaction_id: int, db: Session) -> list[RecoveryAttempt]:
    """Retrieve all recovery attempts for a transaction ordered by escalation level."""
    return db.query(RecoveryAttempt).filter(
        RecoveryAttempt.transaction_id == transaction_id
    ).order_by(RecoveryAttempt.escalation_level.asc()).all()
