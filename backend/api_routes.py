from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import hmac
import hashlib
import json
import logging
from backend.database import get_db
from backend.models import Transaction, RecoveryAttempt, AgentDecision, StrategyStats
from backend.schemas import (
    TransactionResponse, MetricsResponse, StrategyStatsResponse, DemoOrderResponse, 
    InsightReport, CreateOrderRequest
)
from backend.razorpay_client import get_razorpay_client
from backend.config import get_settings
from backend.webhook import process_webhook_event
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/transactions", response_model=List[TransactionResponse])
def list_transactions(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Transaction)
    if status:
        query = query.filter(Transaction.status == status)
    transactions = query.order_by(Transaction.created_at.desc()).all()
    return transactions

@router.get("/api/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    # Match by transaction_id or string id
    txn = db.query(Transaction).filter(
        (Transaction.transaction_id == transaction_id) | (Transaction.id == int(transaction_id) if transaction_id.isdigit() else False)
    ).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn

@router.get("/api/metrics", response_model=MetricsResponse)
def get_metrics(db: Session = Depends(get_db)):
    total_txns = db.query(func.count(Transaction.id)).scalar() or 0
    failed_txns = db.query(func.count(Transaction.id)).filter(
        func.upper(Transaction.status).in_(["FAILED", "RECOVERED"])
    ).scalar() or 0
    recovered_txns = db.query(func.count(Transaction.id)).filter(
        Transaction.recovery_status == "RECOVERED"
    ).scalar() or 0
    
    amount_recovered = db.query(func.sum(Transaction.recovered_amount)).filter(
        Transaction.recovery_status == "RECOVERED"
    ).scalar() or 0
    
    total_failed_amount = db.query(func.sum(Transaction.amount)).filter(
        func.upper(Transaction.status).in_(["FAILED", "RECOVERED"])
    ).scalar() or 0
    
    pending_recovery = db.query(func.count(Transaction.id)).filter(
        Transaction.recovery_status.in_(["PENDING", "IN_PROGRESS"])
    ).scalar() or 0
    
    recovery_rate = (recovered_txns / failed_txns * 100) if failed_txns > 0 else 0.0
    
    return MetricsResponse(
        total_transactions=total_txns,
        transactions_processed=total_txns,
        failed_payments=failed_txns,
        recovered_transactions=recovered_txns,
        amount_recovered=amount_recovered,
        amount_recovered_paise=amount_recovered,
        recovery_rate=round(recovery_rate, 2),
        recovery_rate_percent=round(recovery_rate, 2),
        pending_recovery=pending_recovery,
        total_failed_amount=total_failed_amount
    )

@router.get("/api/strategy-stats", response_model=List[StrategyStatsResponse])
def get_strategy_stats(db: Session = Depends(get_db)):
    stats = db.query(StrategyStats).all()
    return stats

@router.get("/api/agent-decisions")
def get_agent_decisions(db: Session = Depends(get_db)):
    decisions = db.query(AgentDecision).order_by(AgentDecision.created_at.desc()).all()
    return [
        {
            "id": d.id, 
            "transaction_id": d.transaction.transaction_id if d.transaction else None, 
            "step": d.step, 
            "input_data": d.input_data, 
            "output_data": d.output_data, 
            "created_at": d.created_at
        } 
        for d in decisions
    ]

@router.post("/api/create-test-order", response_model=DemoOrderResponse)
def create_test_order(body: Optional[CreateOrderRequest] = None, amount: Optional[int] = Query(None)):
    final_amount = (body.amount if body and body.amount else None) or amount or 50000
    client = get_razorpay_client()
    settings = get_settings()
    receipt = f"demo_{uuid.uuid4().hex[:8]}"
    order = client.create_order(amount=final_amount, receipt=receipt, notes={"is_demo": "true"})
    return DemoOrderResponse(
        order_id=order["id"],
        amount=order["amount"],
        currency=order["currency"],
        razorpay_key_id=settings.razorpay_key_id,
        status=order["status"]
    )

@router.get("/api/simulation-status/{order_id}")
def get_simulation_status(order_id: str, db: Session = Depends(get_db)):
    txn = db.query(Transaction).filter(Transaction.order_id == order_id).first()
    if not txn:
        return {
            "status": "not_found",
            "webhook_received": False,
            "recovered": False
        }
    
    attempts = db.query(RecoveryAttempt).filter(RecoveryAttempt.transaction_id == txn.id).order_by(RecoveryAttempt.created_at.asc()).all()
    latest_attempt = attempts[-1] if attempts else None
    
    ai_cls = txn.ai_classification or {}
    category = ai_cls.get("failure_category") or "analyzing..."
    
    # Check if safety decision is a dict or string
    safety_str = txn.safety_decision
    if isinstance(safety_str, dict):
        safety_str = "Allowed" if safety_str.get("allowed") else f"Blocked: {safety_str.get('reason')}"
    
    return {
        "webhook_received": True,
        "transaction_id": txn.transaction_id,
        "order_id": txn.order_id,
        "status": txn.status,
        "recovery_status": txn.recovery_status,
        "strategy": txn.selected_strategy,
        "safety": safety_str,
        "ai_classification": {
            "category": category,
            **ai_cls
        },
        "recovery_link": latest_attempt.payment_link_url if latest_attempt else None,
        "recovered": txn.recovery_status == "RECOVERED",
        "attempts_count": len(attempts)
    }

@router.get("/api/insights")
def get_insights(db: Session = Depends(get_db)):
    try:
        from backend.insights_engine import generate_heatmap_data, generate_trend_data, generate_ai_insight
        heatmap = generate_heatmap_data(db)
        trends = generate_trend_data(db)
        ai_insight = generate_ai_insight(db)
        
        failure_reasons = db.query(
            Transaction.error_reason, 
            func.count(Transaction.id).label("count")
        ).filter(func.upper(Transaction.status).in_(["FAILED", "RECOVERED"])).group_by(Transaction.error_reason).all()
        
        return {
            "heatmap": heatmap,
            "trends": trends,
            "ai_insight": ai_insight.model_dump() if hasattr(ai_insight, "model_dump") else ai_insight,
            "failure_reasons": [{"reason": r[0] or "unknown", "count": r[1]} for r in failure_reasons]
        }
    except Exception as e:
        logger.error(f"Error in get_insights: {e}")
        return {
            "heatmap": [],
            "trends": [],
            "failure_reasons": [],
            "error": str(e)
        }

@router.post("/api/trigger-test-failure")
def trigger_test_failure(
    order_id: str = Query(...), 
    error_reason: str = Query("insufficient_funds"),
    amount: Optional[int] = Query(None),
    customer_email: Optional[str] = Query("customer@example.com"),
    customer_contact: Optional[str] = Query("+919876543210"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Simulates receiving a real Razorpay test mode payment.failed event for an order."""
    payment_id = f"pay_test_{uuid.uuid4().hex[:10]}"
    event_id = f"payment.failed_{payment_id}"
    final_amount = amount or 50000
    
    payload = {
        "entity": "event",
        "account_id": "acc_test",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": final_amount,
                    "currency": "INR",
                    "status": "failed",
                    "order_id": order_id,
                    "invoice_id": None,
                    "international": False,
                    "method": "card",
                    "amount_refunded": 0,
                    "refund_status": None,
                    "captured": False,
                    "description": f"Test payment for {order_id}",
                    "card_id": "card_test",
                    "bank": None,
                    "wallet": None,
                    "vpa": None,
                    "email": customer_email,
                    "contact": customer_contact,
                    "notes": {"is_demo": "true"},
                    "fee": None,
                    "tax": None,
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": f"Payment failed due to {error_reason}",
                    "error_source": "customer",
                    "error_step": "payment_authorization",
                    "error_reason": error_reason
                }
            }
        },
        "created_at": int(datetime.now(timezone.utc).timestamp())
    }
    
    # Process event
    process_webhook_event(event_id, "payment.failed", payload)
    
    return {
        "status": "triggered",
        "payment_id": payment_id,
        "order_id": order_id,
        "amount": final_amount,
        "error_reason": error_reason
    }

@router.post("/api/trigger-recovery-success")
def trigger_recovery_success(order_id: str = Query(...), db: Session = Depends(get_db)):
    """Simulates/records a successful recovery payment for an order and updates the learning engine."""
    txn = db.query(Transaction).filter(Transaction.order_id == order_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found for this order_id")
    
    txn.recovery_status = "RECOVERED"
    txn.recovered_amount = txn.amount
    txn.recovered_at = datetime.now(timezone.utc)
    
    # Mark latest attempt as SUCCESS
    attempt = db.query(RecoveryAttempt).filter(RecoveryAttempt.transaction_id == txn.id).order_by(RecoveryAttempt.id.desc()).first()
    if attempt:
        attempt.status = "SUCCESS"
        attempt.recovery_payment_id = f"pay_rec_{uuid.uuid4().hex[:10]}"
        txn.recovery_strategy = attempt.recovery_type
        
    try:
        from backend.learning_engine import record_outcome
        classification = txn.ai_classification or {}
        record_outcome(
            failure_category=classification.get("failure_category", "unknown"),
            error_reason=txn.error_reason or "unknown",
            strategy=txn.selected_strategy or txn.recovery_strategy or "unknown",
            success=True,
            amount=txn.amount,
            db=db
        )
    except Exception as e:
        logger.error(f"Learning engine record outcome error: {e}")
        
    db.commit()
    return {
        "status": "success",
        "order_id": order_id,
        "recovery_status": "RECOVERED",
        "recovered_amount": txn.recovered_amount
    }

from pydantic import BaseModel
class ConfigUpdateRequest(BaseModel):
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None
    openai_api_key: Optional[str] = None

@router.get("/api/config-status")
def get_config_status():
    settings = get_settings()
    has_rzp = bool(settings.razorpay_key_id and "xxxx" not in settings.razorpay_key_id and settings.razorpay_key_id != "rzp_test_placeholder")
    has_openai = bool(settings.openai_api_key and "xxxx" not in settings.openai_api_key and settings.openai_api_key.startswith("sk-"))
    return {
        "has_razorpay_keys": has_rzp,
        "razorpay_key_id": settings.razorpay_key_id[:12] + "..." if has_rzp else "Not Configured",
        "has_openai_key": has_openai,
    }

@router.post("/api/save-config")
def save_config(config: ConfigUpdateRequest):
    import os
    env_path = ".env"
    env_dict = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env_dict[k.strip()] = v.strip()
            
    if config.razorpay_key_id:
        env_dict["RAZORPAY_KEY_ID"] = config.razorpay_key_id.strip()
    if config.razorpay_key_secret:
        env_dict["RAZORPAY_KEY_SECRET"] = config.razorpay_key_secret.strip()
    if config.razorpay_webhook_secret:
        env_dict["RAZORPAY_WEBHOOK_SECRET"] = config.razorpay_webhook_secret.strip()
    if config.openai_api_key:
        env_dict["OPENAI_API_KEY"] = config.openai_api_key.strip()
        
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in env_dict.items():
            f.write(f"{k}={v}\n")
            
    get_settings.cache_clear()
    return {"status": "saved"}
