from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/arbitrage_db")
    
    # Redis (optional)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # JWT
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # App Store IAP
    app_store_shared_secret: str = os.getenv("APP_STORE_SHARED_SECRET", "")
    app_store_bundle_id: str = os.getenv("APP_STORE_BUNDLE_ID", "com.yourcompany.arbitragebot")
    
    # API Settings
    api_v1_prefix: str = "/api/v1"
    project_name: str = "Arbitrage Bot API"
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Cache
    cache_duration: int = 30  # seconds
    min_fetch_interval: int = 15  # seconds
    
    # Arbitrage Settings
    min_volume_threshold: float = 100000.0  # $100k minimum 24h volume
    max_profit_threshold: float = 20.0  # 20% max profit for normal users
    admin_max_profit_threshold: float = 40.0  # 40% max profit for admins
    free_user_max_profit: float = 2.0  # 2% max profit for free users
    
    # Subscription Settings
    premium_subscription_days: int = 30  # 30 days per subscription
    
    # Rate Limiting
    max_requests_per_minute: int = 60
    max_concurrent_requests: int = 10
    
    # CORS
    allowed_origins: list[str] = ["*"]  # In production, specify exact origins
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()