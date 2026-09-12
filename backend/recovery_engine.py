import logging
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models import Transaction, RecoveryAttempt
from backend.razorpay_client import get_razorpay_client

logger = logging.getLogger(__name__)

def execute_recovery(transaction: Transaction, strategy: str, customer_message: str, db: Session) -> RecoveryAttempt:
    """Execute recovery actions via Razorpay and record the attempt."""
    client = get_razorpay_client()
    attempt = RecoveryAttempt(
        transaction_id=transaction.id,
        recovery_type=strategy,
        customer_message=customer_message,
        escalation_level=1,
        status="PENDING"
    )
    
    try:
        if strategy == "payment_link":
            # Create a payment link
            ref_id = f"recovery_{transaction.transaction_id}_{int(time.time())}"
            expire_by = int(time.time()) + (24 * 60 * 60) # 24 hours
            notes = {"recovery_for": transaction.transaction_id}
            link_res = client.create_payment_link(
                amount=transaction.amount,
                currency=transaction.currency,
                description=customer_message[:2048] if customer_message else "Payment Recovery",
                customer_email=transaction.customer_email,
                customer_contact=transaction.customer_contact,
                reference_id=ref_id,
                expire_by=expire_by,
                callback_url=None,
                notes=notes
            )
            attempt.payment_link_id = link_res.get("id")
            attempt.payment_link_url = link_res.get("short_url")
            attempt.recovery_order_id = link_res.get("id")
            attempt.status = "PENDING"
            transaction.recovery_status = "IN_PROGRESS"
            transaction.recovery_attempt_count += 1
            
        elif strategy == "delayed_retry":
            # Create a new order for the retry, then a payment link for it
            notes = {"recovery_for": transaction.transaction_id}
            order_res = client.create_order(
                amount=transaction.amount,
                currency=transaction.currency,
                receipt=f"retry_{transaction.transaction_id[:10]}",
                notes=notes
            )
            attempt.recovery_order_id = order_res.get("id")
            
            ref_id = f"retry_{transaction.transaction_id}_{int(time.time())}"
            expire_by = int(time.time()) + (2 * 60 * 60) # 2 hours
            link_res = client.create_payment_link(
                amount=transaction.amount,
                currency=transaction.currency,
                description="Retry Payment",
                customer_email=transaction.customer_email,
                customer_contact=transaction.customer_contact,
                reference_id=ref_id,
                expire_by=expire_by,
                callback_url=None
            )
            attempt.payment_link_id = link_res.get("id")
            attempt.payment_link_url = link_res.get("short_url")
            attempt.status = "PENDING"
            transaction.recovery_status = "IN_PROGRESS"
            transaction.recovery_attempt_count += 1

        elif strategy == "alternative_payment_method":
            ref_id = f"alt_{transaction.transaction_id}_{int(time.time())}"
            expire_by = int(time.time()) + (24 * 60 * 60) # 24 hours
            desc = "Alternative Payment (UPI/Netbanking Recommended)"
            if customer_message:
                desc = customer_message[:2048]
            notes = {"recovery_for": transaction.transaction_id}
            link_res = client.create_payment_link(
                amount=transaction.amount,
                currency=transaction.currency,
                description=desc,
                customer_email=transaction.customer_email,
                customer_contact=transaction.customer_contact,
                reference_id=ref_id,
                expire_by=expire_by,
                callback_url=None,
                notes=notes
            )
            attempt.payment_link_id = link_res.get("id")
            attempt.payment_link_url = link_res.get("short_url")
            attempt.recovery_order_id = link_res.get("id")
            attempt.status = "PENDING"
            transaction.recovery_status = "IN_PROGRESS"
            transaction.recovery_attempt_count += 1
            
        elif strategy == "human_review":
            attempt.status = "PENDING"
            transaction.recovery_status = "HUMAN_REVIEW"
            transaction.recovery_attempt_count += 1
            
        elif strategy == "stop":
            attempt.status = "FAILED"
            transaction.recovery_status = "FAILED"
            
        else:
            logger.error(f"Unknown strategy: {strategy}")
            attempt.status = "FAILED"
            transaction.recovery_status = "FAILED"

        db.add(attempt)
        return attempt

    except Exception as e:
        logger.error(f"Failed to execute recovery strategy '{strategy}': {e}")
        attempt.status = "FAILED"
        db.add(attempt)
        return attempt
