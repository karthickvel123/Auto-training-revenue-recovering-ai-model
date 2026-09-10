import logging
from sqlalchemy.orm import Session
from backend.models import StrategyStats

logger = logging.getLogger(__name__)

def record_outcome(failure_category: str, error_reason: str, strategy: str, success: bool, amount: int, db: Session):
    """Record recovery outcome and update strategy statistics."""
    try:
        # Normalize inputs
        failure_category = failure_category or "unknown"
        error_reason = error_reason or "unknown"
        strategy = strategy or "unknown"

        stats = db.query(StrategyStats).filter(
            StrategyStats.failure_category == failure_category,
            StrategyStats.error_reason == error_reason,
            StrategyStats.strategy == strategy
        ).first()

        if not stats:
            stats = StrategyStats(
                failure_category=failure_category,
                error_reason=error_reason,
                strategy=strategy,
                attempts=0,
                successful_recoveries=0,
                recovery_rate=0.0,
                total_amount_attempted=0,
                total_amount_recovered=0
            )
            db.add(stats)

        stats.attempts += 1
        stats.total_amount_attempted += amount

        if success:
            stats.successful_recoveries += 1
            stats.total_amount_recovered += amount

        stats.recovery_rate = stats.successful_recoveries / stats.attempts

        db.commit()
        logger.info(f"Recorded outcome for {strategy}: success={success}, new rate={stats.recovery_rate:.2f}")

    except Exception as e:
        logger.error(f"Failed to record outcome: {e}")
        db.rollback()
