from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, BigInteger, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime, date

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    subscription_end = Column(Date, nullable=True)
    is_premium = Column(Boolean, default=False)
    added_date = Column(DateTime, default=func.now())

class ArbitrageData(Base):
    __tablename__ = "arbitrage_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    exchange1 = Column(String, nullable=False)
    exchange2 = Column(String, nullable=False)
    price1 = Column(Float, nullable=False)
    price2 = Column(Float, nullable=False)
    profit_percent = Column(Float, nullable=False)
    volume_24h = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=func.now())

class PremiumUser(Base):
    __tablename__ = "premium_users"
    
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    added_by_admin = Column(Boolean, default=True)
    added_date = Column(DateTime, default=func.now())
    subscription_end = Column(Date, nullable=True)

class LicenseKey(Base):
    __tablename__ = "license_keys"
    
    license_key = Column(String, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=True)
    username = Column(String, nullable=True)
    used_date = Column(DateTime, default=func.now())
    gumroad_sale_id = Column(String, nullable=True)