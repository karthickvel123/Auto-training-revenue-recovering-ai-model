from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    razorpay_key_id: str = "rzp_test_placeholder"
    razorpay_key_secret: str = "rzp_secret_placeholder"
    razorpay_webhook_secret: str = "rzp_webhook_placeholder"
    openai_api_key: str = ""
    database_url: str = "sqlite:///./recovery_agent.db"
    max_retry_count: int = 3
    high_value_threshold: int = 500000  # paise (5,000 INR)
    min_ai_confidence: float = 0.6
    escalation_timeout_minutes: int = 30
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    return Settings()
