from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from backend.database import get_db, get_session_local
from backend.models import Transaction, WebhookEvent, RecoveryAttempt
from backend.razorpay_client import get_razorpay_client
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
router = APIRouter()

def process_webhook_event(event_id: str, event_type: str, payload: dict):
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        # Check duplicate
        existing = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
        if existing:
            logger.info(f"Duplicate webhook event: {event_id}")
            return
        
        # Save event
        db_event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            processed=True
        )
        db.add(db_event)
        
        # Route logic
        payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        transaction_id = payment_entity.get("id")
        
        if event_type == "payment.failed":
            txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
            if not txn:
                txn = Transaction(
                    transaction_id=transaction_id,
                    order_id=payment_entity.get("order_id"),
                    amount=payment_entity.get("amount", 0),
                    currency=payment_entity.get("currency", "INR"),
                    status="FAILED",
                    error_code=payment_entity.get("error_code"),
                    error_description=payment_entity.get("error_description"),
                    error_source=payment_entity.get("error_source"),
                    error_step=payment_entity.get("error_step"),
                    error_reason=payment_entity.get("error_reason"),
                    customer_contact=payment_entity.get("contact"),
                    customer_email=payment_entity.get("email"),
                    payment_method=payment_entity.get("method"),
                    raw_event=payload
                )
                db.add(txn)
            else:
                txn.status = "FAILED"
                txn.error_code = payment_entity.get("error_code")
                txn.error_description = payment_entity.get("error_description")
                txn.error_reason = payment_entity.get("error_reason")
            
            db.commit()
            
            # Call agent flow
            try:
                from backend.agent import process_failed_payment
                process_failed_payment(txn.id, db)
            except ImportError:
                logger.warning("backend.agent not found, skipping agent processing")
            except Exception as e:
                logger.error(f"Agent processing failed: {e}", exc_info=True)

        elif event_type == "payment.authorized":
            txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
            if txn:
                txn.status = "AUTHORIZED"
                db.commit()

        elif event_type == "payment.captured":
            txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
            if txn:
                txn.status = "CAPTURED"
            
            # Check for recovery matching via multiple strategies
            notes = payment_entity.get("notes", {})
            recovered_txn_id = None
            
            # 1. Notes check (primary — notes contain recovery_for)
            for k, v in notes.items():
                if k.startswith("recovery_for") and v:
                    recovered_txn_id = v
                    break
            
            # 2. Payment Link ID check — match via RecoveryAttempt records
            if not recovered_txn_id:
                payment_link_id = payment_entity.get("payment_link_id")
                if payment_link_id:
                    attempt = db.query(RecoveryAttempt).filter(
                        RecoveryAttempt.payment_link_id == payment_link_id,
                        RecoveryAttempt.status == "PENDING"
                    ).first()
                    if attempt:
                        orig_txn = db.query(Transaction).filter(Transaction.id == attempt.transaction_id).first()
                        if orig_txn:
                            recovered_txn_id = orig_txn.transaction_id

            # 3. Order ID check — match via recovery_order_id on RecoveryAttempt
            if not recovered_txn_id:
                order_id = payment_entity.get("order_id")
                if order_id:
                    attempt = db.query(RecoveryAttempt).filter(
                        RecoveryAttempt.recovery_order_id == order_id,
                        RecoveryAttempt.status == "PENDING"
                    ).first()
                    if attempt:
                        orig_txn = db.query(Transaction).filter(Transaction.id == attempt.transaction_id).first()
                        if orig_txn:
                            recovered_txn_id = orig_txn.transaction_id
                    
            if recovered_txn_id:
                orig_txn = db.query(Transaction).filter(Transaction.transaction_id == recovered_txn_id).first()
                if orig_txn:
                    orig_txn.recovery_status = "RECOVERED"
                    orig_txn.recovered_amount = payment_entity.get("amount")
                    orig_txn.recovered_at = datetime.now(timezone.utc)
                    
                    # Find attempt
                    attempt = db.query(RecoveryAttempt).filter(RecoveryAttempt.transaction_id == orig_txn.id).order_by(RecoveryAttempt.id.desc()).first()
                    if attempt:
                        attempt.status = "SUCCESS"
                        attempt.recovery_payment_id = transaction_id
                        orig_txn.recovery_strategy = attempt.recovery_type
                    
                    try:
                        from backend.learning_engine import record_outcome
                        classification = orig_txn.ai_classification or {}
                        record_outcome(
                            failure_category=classification.get("failure_category", "unknown"),
                            error_reason=orig_txn.error_reason or "unknown",
                            strategy=orig_txn.recovery_strategy or "unknown",
                            success=True,
                            amount=orig_txn.amount,
                            db=db
                        )
                    except ImportError:
                        pass
                    except Exception as e:
                        logger.error(f"Learning engine failed: {e}")
                        
            db.commit()
            
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/api/webhooks/razorpay")
async def razorpay_webhook(request: Request, background_tasks: BackgroundTasks):
    # 1. Read raw body
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")
    
    # 2. Get signature header
    signature = request.headers.get("X-Razorpay-Signature", "")
    
    # 3. Verify signature
    rz_client = get_razorpay_client()
    if not rz_client.verify_webhook_signature(body_str, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 4. Parse payload
    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    entity_id = payment_entity.get("id", "")
    event_type = payload.get("event", "")
    event_id = f"{event_type}_{entity_id}"
    
    # 5. Dedup check & Process in background
    background_tasks.add_task(process_webhook_event, event_id, event_type, payload)
    
    return {"status": "ok"}
