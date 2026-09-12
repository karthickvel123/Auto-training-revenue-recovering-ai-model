import logging
from sqlalchemy.orm import Session
from backend.models import Transaction, StrategyStats
from backend.schemas import FailureAnalysis, StrategyDecision

logger = logging.getLogger(__name__)

def select_strategy(transaction: Transaction, analysis: FailureAnalysis, db: Session) -> StrategyDecision:
    """Select the best recovery strategy based on AI analysis and historical stats."""
    recommended_strategy = analysis.recommended_strategy
    selected_strategy = recommended_strategy
    data_driven = False
    historical_recovery_rate = None
    override_reason = None

    # Query historical stats for this failure category and error reason
    stats = db.query(StrategyStats).filter(
        StrategyStats.failure_category == analysis.failure_category,
        StrategyStats.error_reason == (transaction.error_reason or "unknown")
    ).all()

    # Need at least 2 different strategies with >= 10 attempts each to make a comparison
    valid_stats = [s for s in stats if s.attempts >= 10]
    
    if len(valid_stats) >= 2:
        # Find the best performing strategy
        best_stat = max(valid_stats, key=lambda s: s.recovery_rate)
        
        # Find the LLM recommended strategy's historical performance, if any
        llm_stat = next((s for s in valid_stats if s.strategy == recommended_strategy), None)
        
        if llm_stat:
            # Override if the best historical strategy is > 1.5x better
            if best_stat.recovery_rate > 1.5 * llm_stat.recovery_rate:
                selected_strategy = best_stat.strategy
                data_driven = True
                historical_recovery_rate = best_stat.recovery_rate
                override_reason = f"Historical rate ({best_stat.recovery_rate:.2f}) > 1.5x LLM rate ({llm_stat.recovery_rate:.2f})"
        else:
            # If the LLM strategy has no history but another one does very well (>20%)
            if best_stat.recovery_rate > 0.20:
                selected_strategy = best_stat.strategy
                data_driven = True
                historical_recovery_rate = best_stat.recovery_rate
                override_reason = "Strong historical performance over unknown LLM strategy."

    # Apply hard constraints based on failure category
    if analysis.failure_category in ("security", "permanent"):
        selected_strategy = "stop"
        data_driven = False
        override_reason = "Constraint: Stop for security/permanent failures."
    elif selected_strategy == "delayed_retry" and analysis.failure_category != "temporary":
        selected_strategy = "payment_link"
        data_driven = False
        override_reason = "Constraint: Delayed retry only for temporary failures."

    logger.info(f"Strategy selected: {selected_strategy} (Data driven: {data_driven})")

    return StrategyDecision(
        selected_strategy=selected_strategy,
        reasoning=analysis.reasoning_summary,
        data_driven=data_driven,
        historical_recovery_rate=historical_recovery_rate,
        llm_recommendation=recommended_strategy,
        override_reason=override_reason
    )
