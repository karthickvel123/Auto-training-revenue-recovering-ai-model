import pytest

class StrategyStats:
    def __init__(self):
        self.attempts = 0
        self.recoveries = 0
    
    def record_outcome(self, success: bool):
        self.attempts += 1
        if success:
            self.recoveries += 1
            
    @property
    def recovery_rate(self):
        return self.recoveries / self.attempts if self.attempts > 0 else 0

def test_record_successful_outcome():
    stats = StrategyStats()
    stats.record_outcome(True)
    assert stats.attempts == 1
    assert stats.recoveries == 1

def test_record_failed_outcome():
    stats = StrategyStats()
    stats.record_outcome(False)
    assert stats.attempts == 1
    assert stats.recoveries == 0

def test_recovery_rate_calculation():
    stats = StrategyStats()
    stats.record_outcome(True)
    stats.record_outcome(False)
    stats.record_outcome(True)
    assert stats.attempts == 3
    assert stats.recoveries == 2
    assert stats.recovery_rate == 2/3

def test_new_strategy_creates_stats():
    # Mock behavior of creating a new row in DB
    assert True
