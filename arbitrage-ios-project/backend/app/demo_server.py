"""
Simple demo server with mock arbitrage data
Run with: python demo_server.py
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import random
from datetime import datetime

app = FastAPI(title="Arbitrage Demo API")

# Enable CORS for mobile testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock arbitrage opportunities
MOCK_OPPORTUNITIES = [
    {
        "symbol": "BTCUSDT",
        "exchange1": "binance",
        "exchange2": "kucoin", 
        "price1": 43250.50,
        "price2": 43512.30,
        "profit_percent": 0.61,
        "volume_24h": 2500000,
        "buy_exchange_tier": "tier_1",
        "sell_exchange_tier": "tier_2",
        "total_exchanges": 8,
        "risk_level": "low",
        "risk_data": {
            "score": 2,
            "factors": ["premium_coin"],
            "confidence": 85
        },
        "opportunity_score": 75.5,
        "category": "layer1"
    },
    {
        "symbol": "ETHUSDT",
        "exchange1": "gate",
        "exchange2": "okx",
        "price1": 2845.20,
        "price2": 2891.75,
        "profit_percent": 1.64,
        "volume_24h": 1850000,
        "buy_exchange_tier": "tier_2",
        "sell_exchange_tier": "tier_2", 
        "total_exchanges": 12,
        "risk_level": "low",
        "risk_data": {
            "score": 1,
            "factors": ["premium_coin", "multiple_exchanges_12"],
            "confidence": 92
        },
        "opportunity_score": 88.2,
        "category": "layer1"
    },
    {
        "symbol": "SOLUSDT", 
        "exchange1": "bybit",
        "exchange2": "mexc",
        "price1": 98.45,
        "price2": 101.23,
        "profit_percent": 2.82,
        "volume_24h": 750000,
        "buy_exchange_tier": "tier_2",
        "sell_exchange_tier": "tier_3",
        "total_exchanges": 6,
        "risk_level": "medium",
        "risk_data": {
            "score": 4,
            "factors": ["medium_profit_2.8%", "mixed_tier_exchanges"],
            "confidence": 68
        },
        "opportunity_score": 62.1,
        "category": "layer1"
    },
    {
        "symbol": "DOGEUSDT",
        "exchange1": "lbank", 
        "exchange2": "bitmart",
        "price1": 0.08234,
        "price2": 0.08891,
        "profit_percent": 7.98,
        "volume_24h": 45000,
        "buy_exchange_tier": "tier_3",
        "sell_exchange_tier": "tier_3",
        "total_exchanges": 3,
        "risk_level": "high",
        "risk_data": {
            "score": 8,
            "factors": ["high_profit_8.0%", "low_volume_45k", "tier3_exchanges"],
            "confidence": 23
        },
        "opportunity_score": 28.5,
        "category": "meme"
    }
]

@app.get("/")
def root():
    return {
        "message": "🚀 Arbitrage Demo API",
        "status": "running",
        "endpoints": [
            "/health",
            "/api/v1/arbitrage/opportunities",
            "/api/v1/auth/login"
        ]
    }

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/api/v1/auth/login")
def login(data: dict = None):
    return {
        "access_token": "demo_token_123",
        "token_type": "bearer", 
        "expires_in": 3600
    }

@app.get("/api/v1/arbitrage/opportunities")
def get_opportunities():
    # Add some randomness to make it feel live
    opportunities = []
    for opp in MOCK_OPPORTUNITIES:
        # Slightly randomize profit %
        profit_variation = random.uniform(-0.1, 0.1)
        modified_opp = opp.copy()
        modified_opp["profit_percent"] = max(0.1, opp["profit_percent"] + profit_variation)
        opportunities.append(modified_opp)
    
    return {
        "success": True,
        "data": {
            "opportunities": opportunities,
            "metadata": {
                "total_found": len(opportunities),
                "is_premium": False,
                "last_updated": datetime.now().isoformat(),
                "user_tier": "free"
            }
        }
    }

@app.get("/api/v1/arbitrage/symbol/{symbol}")
def get_symbol_prices(symbol: str):
    exchanges = ["binance", "kucoin", "gate", "okx", "bybit"]
    base_price = random.uniform(100, 50000)
    
    prices = []
    for exchange in exchanges:
        price_variation = random.uniform(-0.02, 0.02)  # ±2% variation
        price = base_price * (1 + price_variation)
        
        prices.append({
            "exchange": exchange,
            "price": price,
            "volume_24h": random.uniform(50000, 2000000),
            "change_24h": random.uniform(-5, 5),
            "tier": "tier_1" if exchange in ["binance", "okx"] else "tier_2"
        })
    
    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "prices": prices,
            "statistics": {
                "min_price": min(p["price"] for p in prices),
                "max_price": max(p["price"] for p in prices),
                "avg_price": sum(p["price"] for p in prices) / len(prices),
                "spread_percent": ((max(p["price"] for p in prices) - min(p["price"] for p in prices)) / min(p["price"] for p in prices)) * 100
            }
        }
    }

if __name__ == "__main__":
    print("🚀 Starting Arbitrage Demo Server...")
    print("📱 Mobile test URL: http://localhost:8000")
    print("📖 API docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)