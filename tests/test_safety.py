import pytest

class Transaction:
    def __init__(self, amount, error_reason, failure_category, confidence, strategy, recovery_attempt_count=0, existing_pending=False):
        self.amount = amount
        self.error_reason = error_reason
        self.failure_category = failure_category
        self.confidence = confidence
        self.strategy = strategy
        self.recovery_attempt_count = recovery_attempt_count
        self.existing_pending = existing_pending

def evaluate_safety(tx: Transaction) -> str:
    if tx.failure_category == "security" or "fraud" in tx.error_reason.lower():
        return "blocked"
    if tx.failure_category == "permanent" and tx.strategy == "payment_link":
        return "blocked"
    if tx.recovery_attempt_count >= 3:
        return "blocked"
    if tx.amount >= 1000000: # 10,000 INR
        return "human_review"
    if tx.confidence < 0.6:
        return "blocked"
    if tx.existing_pending:
        return "blocked"
    return "allowed"

def test_security_failure_blocked():
    tx = Transaction(50000, "unknown", "security", 0.9, "retry")
    assert evaluate_safety(tx) == "blocked"

def test_permanent_failure_blocked():
    tx = Transaction(50000, "invalid_card", "permanent", 0.9, "payment_link")
    assert evaluate_safety(tx) == "blocked"

def test_max_retries_exceeded():
    tx = Transaction(50000, "network_error", "temporary", 0.9, "retry", recovery_attempt_count=3)
    assert evaluate_safety(tx) == "blocked"

def test_high_value_requires_review():
    tx = Transaction(2000000, "insufficient_funds", "customer_action", 0.9, "payment_link")
    assert evaluate_safety(tx) == "human_review"

def test_low_confidence_blocked():
    tx = Transaction(50000, "unknown", "unknown", 0.4, "retry")
    assert evaluate_safety(tx) == "blocked"

def test_duplicate_nudge_prevented():
    tx = Transaction(50000, "insufficient_funds", "customer_action", 0.9, "payment_link", existing_pending=True)
    assert evaluate_safety(tx) == "blocked"

def test_fraud_keywords_blocked():
    tx = Transaction(50000, "suspected_fraud", "unknown", 0.9, "retry")
    assert evaluate_safety(tx) == "blocked"

def test_safe_payment_allowed():
    tx = Transaction(50000, "insufficient_funds", "customer_action", 0.9, "payment_link")
    assert evaluate_safety(tx) == "allowed"
