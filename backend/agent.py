import logging
import json
from sqlalchemy.orm import Session
from backend.models import Transaction, AgentDecision
from backend.classifier import classify_failure
from backend.strategy_engine import select_strategy
from backend.safety_gateway import check_safety
from backend.recovery_engine import execute_recovery

logger = logging.getLogger(__name__)

def process_failed_payment(transaction_id: int, db: Session):
    """Main orchestrator for processing a failed payment webhook."""
    logger.info(f"Starting processing for transaction {transaction_id}")
    
    # 1. Load transaction
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        logger.error(f"Transaction {transaction_id} not found.")
        return

    try:
        # 2 & 3. Classify failure
        analysis = classify_failure(
            error_code=transaction.error_code,
            error_description=transaction.error_description,
            error_source=transaction.error_source,
            error_step=transaction.error_step,
            error_reason=transaction.error_reason,
            amount=transaction.amount,
            currency=transaction.currency,
            payment_method=transaction.payment_method,
            customer_email=transaction.customer_email
        )
        transaction.ai_classification = analysis.model_dump()
        
        # 4. Log Decision
        decision_cls = AgentDecision(
            transaction_id=transaction.id,
            step="classification",
            input_data={"error_reason": transaction.error_reason, "amount": transaction.amount},
            output_data=analysis.model_dump()
        )
        db.add(decision_cls)

        # 5 & 6. Select Strategy
        strategy_decision = select_strategy(transaction, analysis, db)
        transaction.selected_strategy = strategy_decision.selected_strategy
        transaction.recovery_strategy = strategy_decision.selected_strategy
        
        # 7. Log Decision
        decision_strat = AgentDecision(
            transaction_id=transaction.id,
            step="strategy",
            input_data=analysis.model_dump(),
            output_data=strategy_decision.model_dump()
        )
        db.add(decision_strat)

        # 8 & 9. Safety Gateway
        safety_verdict = check_safety(transaction, analysis, strategy_decision.selected_strategy, db)
        transaction.safety_decision = safety_verdict.model_dump()
        
        # 10. Log Decision
        decision_safe = AgentDecision(
            transaction_id=transaction.id,
            step="safety",
            input_data={"proposed_strategy": strategy_decision.selected_strategy},
            output_data=safety_verdict.model_dump()
        )
        db.add(decision_safe)

        # 11 & 12. Execute Recovery
        if safety_verdict.allowed:
            logger.info(f"Safety allowed. Executing strategy: {strategy_decision.selected_strategy}")
            execute_recovery(transaction, strategy_decision.selected_strategy, analysis.customer_message, db)
            decision_act = AgentDecision(
                transaction_id=transaction.id,
                step="action",
                input_data={"strategy": strategy_decision.selected_strategy, "message": analysis.customer_message},
                output_data={"blocked": False, "status": "executed"}
            )
            db.add(decision_act)
        else:
            logger.warning(f"Safety blocked. Overridden strategy: {safety_verdict.overridden_strategy}")
            execute_recovery(transaction, safety_verdict.overridden_strategy, "Manual review required", db)
            decision_act = AgentDecision(
                transaction_id=transaction.id,
                step="action",
                input_data={"strategy": strategy_decision.selected_strategy},
                output_data={"blocked": True, "overridden_strategy": safety_verdict.overridden_strategy, "reason": safety_verdict.reason}
            )
            db.add(decision_act)
            
        # 13. Commit all changes
        db.commit()
        logger.info(f"Successfully processed transaction {transaction_id}")

    except Exception as e:
        logger.error(f"Error processing transaction {transaction_id}: {e}", exc_info=True)
        db.rollback()
