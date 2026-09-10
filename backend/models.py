from typing import Optional, Any
from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, JSON, Float, Boolean, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from backend.database import Base

class Transaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    status: Mapped[str] = mapped_column(String(50))
    error_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_contact: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_classification: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    selected_strategy: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    safety_decision: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    recovery_status: Mapped[str] = mapped_column(String(50), default="PENDING")
    recovered_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    recovery_strategy: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recovery_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_event: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    recovery_attempts: Mapped[list["RecoveryAttempt"]] = relationship("RecoveryAttempt", back_populates="transaction")
    agent_decisions: Mapped[list["AgentDecision"]] = relationship("AgentDecision", back_populates="transaction")

class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"))
    recovery_type: Mapped[str] = mapped_column(String(50))
    recovery_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_link_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_link_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recovery_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    customer_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="recovery_attempts")

class StrategyStats(Base):
    __tablename__ = "strategy_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    failure_category: Mapped[str] = mapped_column(String(100))
    error_reason: Mapped[str] = mapped_column(String(255))
    strategy: Mapped[str] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    successful_recoveries: Mapped[int] = mapped_column(Integer, default=0)
    recovery_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount_attempted: Mapped[int] = mapped_column(Integer, default=0)
    total_amount_recovered: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (UniqueConstraint('failure_category', 'error_reason', 'strategy'),)

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[Any] = mapped_column(JSON)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class AgentDecision(Base):
    __tablename__ = "agent_decisions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[int] = mapped_column(Integer, ForeignKey("transactions.id"))
    step: Mapped[str] = mapped_column(String(100))
    input_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="agent_decisions")
