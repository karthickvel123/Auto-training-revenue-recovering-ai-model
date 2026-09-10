from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, Any
from datetime import datetime

# LLM Output Schema
class FailureAnalysis(BaseModel):
    failure_category: Literal["temporary", "customer_action", "permanent", "security"]
    retryability: Literal["retryable", "needs_customer_action", "do_not_retry"]
    recommended_strategy: Literal["delayed_retry", "payment_link", "alternative_payment_method", "human_review", "stop"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str
    customer_message: str

# Strategy Decision
class StrategyDecision(BaseModel):
    selected_strategy: str
    reasoning: str
    data_driven: bool = False
    historical_recovery_rate: Optional[float] = None
    llm_recommendation: str
    override_reason: Optional[str] = None

# Safety Verdict  
class SafetyVerdict(BaseModel):
    allowed: bool
    reason: str
    rule_triggered: Optional[str] = None
    overridden_strategy: Optional[str] = None

# Insight Report
class InsightReport(BaseModel):
    headline: str
    pattern: str
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

# API Response Models
class TransactionResponse(BaseModel):
    id: int
    transaction_id: str
    order_id: Optional[str] = None
    amount: int
    currency: str
    status: str
    error_code: Optional[str] = None
    error_description: Optional[str] = None
    error_reason: Optional[str] = None
    payment_method: Optional[str] = None
    ai_classification: Optional[Any] = None
    selected_strategy: Optional[str] = None
    safety_decision: Optional[Any] = None
    recovery_status: str
    recovered_amount: Optional[int] = None
    recovered_at: Optional[datetime] = None
    recovery_strategy: Optional[str] = None
    recovery_attempt_count: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class CreateOrderRequest(BaseModel):
    amount: Optional[int] = 50000

class MetricsResponse(BaseModel):
    total_transactions: int
    failed_payments: int
    recovered_transactions: int
    amount_recovered: int  # paise
    recovery_rate: float
    pending_recovery: int
    total_failed_amount: int  # paise
    transactions_processed: Optional[int] = None
    amount_recovered_paise: Optional[int] = None
    recovery_rate_percent: Optional[float] = None

class StrategyStatsResponse(BaseModel):
    failure_category: str
    error_reason: str
    strategy: str
    attempts: int
    successful_recoveries: int
    recovery_rate: float
    total_amount_attempted: int
    total_amount_recovered: int
    
    model_config = ConfigDict(from_attributes=True)

class DemoOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    razorpay_key_id: str
    status: str
