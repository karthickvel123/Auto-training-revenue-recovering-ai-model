import pytest

class StrategyDecision:
    def __init__(self, strategy, reasoning):
        self.strategy = strategy
        self.reasoning = reasoning

def get_best_strategy(failure_category: str, ai_recommendation: str, historical_stats: dict = None) -> StrategyDecision:
    if failure_category in ["permanent", "security"]:
        return StrategyDecision("stop", f"Category is {failure_category}")
        
    if not historical_stats:
        return StrategyDecision(ai_recommendation, "Using AI recommendation due to lack of historical data")
    
    best_strategy = max(historical_stats.items(), key=lambda x: x[1]['success_rate'])[0]
    return StrategyDecision(best_strategy, f"Historical data shows {best_strategy} is most effective")

def test_strategy_with_no_historical_data():
    decision = get_best_strategy("temporary", "immediate_retry", {})
    assert decision.strategy == "immediate_retry"
    assert "Using AI recommendation" in decision.reasoning

def test_strategy_with_historical_data_override():
    stats = {
        "payment_link": {"success_rate": 0.4},
        "delayed_retry": {"success_rate": 0.05}
    }
    decision = get_best_strategy("customer_action", "delayed_retry", stats)
    assert decision.strategy == "payment_link"
    assert "Historical data" in decision.reasoning

def test_permanent_failure_always_stops():
    decision = get_best_strategy("permanent", "payment_link", {"payment_link": {"success_rate": 0.9}})
    assert decision.strategy == "stop"

def test_security_failure_always_stops():
    decision = get_best_strategy("security", "payment_link", {"payment_link": {"success_rate": 0.9}})
    assert decision.strategy == "stop"

def test_strategy_decision_includes_reasoning():
    decision = get_best_strategy("temporary", "immediate_retry", {})
    assert decision.reasoning != ""
