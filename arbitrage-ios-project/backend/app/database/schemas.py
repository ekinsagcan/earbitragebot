from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

# User Schemas
class UserBase(BaseModel):
    username: Optional[str] = None

class UserCreate(UserBase):
    user_id: int
    username: Optional[str] = None

class UserResponse(UserBase):
    user_id: int
    is_premium: bool
    subscription_end: Optional[date] = None
    added_date: datetime

    class Config:
        from_attributes = True

# Arbitrage Schemas
class ArbitrageOpportunity(BaseModel):
    symbol: str
    exchange1: str
    exchange2: str
    price1: float
    price2: float
    profit_percent: float
    volume_24h: float
    timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True

class ArbitrageResponse(BaseModel):
    opportunities: List[ArbitrageOpportunity]
    total_count: int
    is_premium: bool
    last_updated: datetime

# Price Data Schema
class PriceData(BaseModel):
    exchange: str
    price: float
    volume_24h: Optional[float] = None

class SymbolPricesResponse(BaseModel):
    symbol: str
    prices: List[PriceData]
    last_updated: datetime

# Authentication Schemas
class UserLogin(BaseModel):
    user_id: int
    username: Optional[str] = None

class UserRegister(BaseModel):
    user_id: int
    username: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class TokenData(BaseModel):
    user_id: Optional[int] = None

# License Schemas
class LicenseActivation(BaseModel):
    license_key: str = Field(..., min_length=10, max_length=100)

class LicenseResponse(BaseModel):
    success: bool
    message: str
    subscription_end: Optional[date] = None

# Premium User Schemas
class PremiumUserCreate(BaseModel):
    user_id: int
    username: Optional[str] = None
    days: int = 30

class PremiumUserResponse(BaseModel):
    user_id: int
    username: Optional[str] = None
    subscription_end: Optional[date] = None
    added_date: datetime

    class Config:
        from_attributes = True

# Admin Schemas
class AdminStats(BaseModel):
    total_users: int
    premium_users: int
    total_opportunities: int
    cache_hits: int
    cache_misses: int
    api_requests: int

# API Response Wrapper
class APIResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None

# Error Response
class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None