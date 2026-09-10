import logging
import uuid
from sqlalchemy.orm import Session
from backend.models import Transaction, RecoveryAttempt, AgentDecision
from backend.config import get_settings
from backend.razorpay_client import get_razorpay_client

logger = logging.getLogger(__name__)

def create_demo_order(amount: int = 50000, db: Session = None) -> dict:
    """Create a dummy order for demonstration purposes."""
    settings = get_settings()
    client = get_razorpay_client()
    
    receipt_id = f"demo_{uuid.uuid4().hex[:8]}"
    
    try:
        order = client.create_order(
            amount=amount,
            currency="INR",
            receipt=receipt_id,
            notes={"is_demo": "true"}
        )
        return {
            "order_id": order["id"],
            "amount": amount,
            "key_id": settings.razorpay_key_id
        }
    except Exception as e:
        logger.error(f"Failed to create demo order: {e}")
        raise e

def get_simulation_status(order_id: str, db: Session) -> dict:
    """Retrieve full status of a transaction including recovery attempts and decisions."""
    transaction = db.query(Transaction).filter(Transaction.order_id == order_id).first()
    if not transaction:
        return {"error": "Transaction not found"}
        
    attempts = db.query(RecoveryAttempt).filter(RecoveryAttempt.transaction_id == transaction.id).order_by(RecoveryAttempt.created_at.asc()).all()
    decisions = db.query(AgentDecision).filter(AgentDecision.transaction_id == transaction.id).order_by(AgentDecision.created_at.asc()).all()
    
    return {
        "transaction": {
            "id": transaction.id,
            "transaction_id": transaction.transaction_id,
            "order_id": transaction.order_id,
            "amount": transaction.amount,
            "status": transaction.status,
            "error_reason": transaction.error_reason,
            "recovery_status": transaction.recovery_status,
            "recovery_strategy": transaction.recovery_strategy,
            "ai_classification": transaction.ai_classification
        },
        "attempts": [
            {
                "type": a.recovery_type,
                "status": a.status,
                "escalation_level": a.escalation_level,
                "created_at": a.created_at.isoformat() if a.created_at else None
            } for a in attempts
        ],
        "decisions": [
            {
                "step": d.step,
                "input": d.input_data,
                "output": d.output_data,
                "created_at": d.created_at.isoformat() if d.created_at else None
            } for d in decisions
        ]
    }
