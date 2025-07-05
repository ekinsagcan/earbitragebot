from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.database.connection import get_database
from app.database.models import User, PremiumUser, ArbitrageData
from app.database.schemas import ArbitrageResponse, APIResponse, ErrorResponse
from app.core.enhanced_arbitrage import EnhancedArbitrageEngine, RiskLevel
from app.utils.security import verify_token
from app.config import settings

router = APIRouter()

# Global engine instance
arbitrage_engine = EnhancedArbitrageEngine()

async def get_current_user(
    authorization: str = Query(None, alias="Authorization"),
    db: AsyncSession = Depends(get_database)
) -> Optional[User]:
    """Get current user from JWT token"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    
    if not payload:
        return None
    
    user_id = int(payload.get("sub", 0))
    if not user_id:
        return None
    
    # Get user from database
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()

async def is_premium_user(user: User, db: AsyncSession) -> bool:
    """Check if user has premium subscription"""
    if not user:
        return False
    
    # Check premium_users table
    result = await db.execute(
        select(PremiumUser).where(PremiumUser.user_id == user.user_id)
    )
    premium_user = result.scalar_one_or_none()
    
    if premium_user and premium_user.subscription_end:
        return premium_user.subscription_end >= datetime.now().date()
    
    return user.is_premium

@router.get("/opportunities", response_model=Dict[str, Any])
async def get_arbitrage_opportunities(
    min_profit: Optional[float] = Query(None, ge=0.1, le=50, description="Minimum profit percentage"),
    max_risk: Optional[str] = Query(None, description="Maximum risk level (low, medium, high)"),
    exchanges: Optional[str] = Query(None, description="Comma-separated list of exchanges"),
    categories: Optional[str] = Query(None, description="Comma-separated list of categories"),
    min_volume: Optional[float] = Query(None, ge=1000, description="Minimum 24h volume"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Get arbitrage opportunities with advanced filtering
    
    **Free users**: Get top 10 opportunities, limited features
    **Premium users**: Get top 100 opportunities, all features
    """
    try:
        # Check user premium status
        is_premium = await is_premium_user(user, db) if user else False
        
        # Build filters
        filters = {}
        
        if min_profit is not None:
            filters['min_profit'] = min_profit
        
        if max_risk:
            risk_levels = []
            if max_risk == "low":
                risk_levels = ["low"]
            elif max_risk == "medium":
                risk_levels = ["low", "medium"]
            elif max_risk == "high":
                risk_levels = ["low", "medium", "high"]
            filters['risk_levels'] = risk_levels
        
        if exchanges:
            filters['exchanges'] = [ex.strip() for ex in exchanges.split(',')]
        
        if categories:
            filters['categories'] = [cat.strip() for cat in categories.split(',')]
        
        if min_volume is not None:
            filters['min_volume'] = min_volume
        
        # Get opportunities from engine
        result = await arbitrage_engine.get_enhanced_arbitrage_opportunities(
            is_premium=is_premium,
            filters=filters
        )
        
        # Save some opportunities to database for analytics
        if result['opportunities']:
            await _save_arbitrage_samples(result['opportunities'][:5], db)
        
        # Add user context to metadata
        result['metadata']['user_tier'] = 'premium' if is_premium else 'free'
        result['metadata']['applied_filters'] = filters
        
        return {
            "success": True,
            "data": result,
            "message": f"Found {len(result['opportunities'])} opportunities"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get opportunities: {str(e)}"
        )

@router.get("/opportunities/premium-preview")
async def get_premium_preview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """
    Show preview of premium features for free users
    """
    try:
        is_premium = await is_premium_user(user, db) if user else False
        
        if is_premium:
            return await get_arbitrage_opportunities(user=user, db=db)
        
        # Get full opportunities but mask data for preview
        result = await arbitrage_engine.get_enhanced_arbitrage_opportunities(
            is_premium=True,  # Get full data
            filters=None
        )
        
        # Mask premium features
        opportunities = result['opportunities'][:20]  # Show more for preview
        for opp in opportunities[10:]:  # Mask opportunities beyond free tier
            opp['profit_percent'] = min(opp['profit_percent'], 2.0)  # Cap at 2%
            opp['risk_data'] = {"preview_only": True}
            opp['opportunity_score'] = min(opp['opportunity_score'], 40)
        
        return {
            "success": True,
            "data": {
                "opportunities": opportunities,
                "metadata": {
                    **result['metadata'],
                    "user_tier": "free",
                    "preview_mode": True,
                    "upgrade_message": "Upgrade to Premium for unlimited opportunities and advanced features"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get premium preview: {str(e)}"
        )

@router.get("/symbol/{symbol}")
async def get_symbol_prices(
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Get prices for a specific symbol across all exchanges"""
    try:
        is_premium = await is_premium_user(user, db) if user else False
        
        symbol = symbol.upper()
        if not symbol.endswith('USDT'):
            symbol += 'USDT'
        
        # Get current cached data
        current_time = time.time()
        with arbitrage_engine.cache_lock:
            if (current_time - arbitrage_engine.cache_timestamp) < settings.cache_duration:
                all_data = arbitrage_engine.cache_data
            else:
                # Fetch fresh data if cache is old
                all_data = await arbitrage_engine._fetch_all_enhanced_data()
        
        symbol_prices = []
        for exchange, exchange_data in all_data.items():
            if symbol in exchange_data:
                price_data = exchange_data[symbol]
                symbol_prices.append({
                    'exchange': exchange,
                    'price': price_data['price'],
                    'volume_24h': price_data['volume'],
                    'change_24h': price_data.get('change_24h', 0),
                    'tier': arbitrage_engine.exchange_tiers.get(exchange, 'tier_3').value,
                    'timestamp': price_data['timestamp'].isoformat()
                })
        
        if not symbol_prices:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol {symbol} not found"
            )
        
        # Sort by price
        symbol_prices.sort(key=lambda x: x['price'])
        
        # Calculate statistics
        prices = [p['price'] for p in symbol_prices]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        spread_percent = ((max_price - min_price) / min_price) * 100 if min_price > 0 else 0
        
        # Limit data for free users
        if not is_premium and len(symbol_prices) > 5:
            symbol_prices = symbol_prices[:5]
        
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "prices": symbol_prices,
                "statistics": {
                    "min_price": min_price,
                    "max_price": max_price,
                    "avg_price": round(avg_price, 8),
                    "spread_percent": round(spread_percent, 4),
                    "exchange_count": len(symbol_prices),
                    "total_volume": sum(p['volume_24h'] for p in symbol_prices)
                },
                "metadata": {
                    "user_tier": "premium" if is_premium else "free",
                    "last_updated": datetime.now().isoformat()
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbol prices: {str(e)}"
        )

@router.get("/markets/overview")
async def get_market_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_database)
):
    """Get market overview and statistics"""
    try:
        is_premium = await is_premium_user(user, db) if user else False
        
        # Get engine statistics
        stats = arbitrage_engine.get_enhanced_stats()
        
        # Get top opportunities for overview
        result = await arbitrage_engine.get_enhanced_arbitrage_opportunities(
            is_premium=True,  # Get full data for statistics
            filters=None
        )
        
        opportunities = result['opportunities']
        
        # Calculate market statistics
        if opportunities:
            profit_percentages = [opp['profit_percent'] for opp in opportunities]
            risk_distribution = {}
            category_distribution = {}
            
            for opp in opportunities:
                risk = opp['risk_level']
                risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
                
                category = opp['category']
                category_distribution[category] = category_distribution.get(category, 0) + 1
            
            market_stats = {
                "total_opportunities": len(opportunities),
                "avg_profit": round(sum(profit_percentages) / len(profit_percentages), 2),
                "max_profit": round(max(profit_percentages), 2),
                "risk_distribution": risk_distribution,
                "category_distribution": category_distribution,
                "top_symbols": [opp['symbol'] for opp in opportunities[:10]]
            }
        else:
            market_stats = {
                "total_opportunities": 0,
                "avg_profit": 0,
                "max_profit": 0,
                "risk_distribution": {},
                "category_distribution": {},
                "top_symbols": []
            }
        
        # Limit data for free users
        if not is_premium:
            market_stats["top_symbols"] = market_stats["top_symbols"][:5]
            market_stats["message"] = "Upgrade to Premium for complete market overview"
        
        return {
            "success": True,
            "data": {
                "market_stats": market_stats,
                "system_stats": {
                    "cache_performance": {
                        "hit_rate": round((stats['cache_hits'] / max(stats['cache_hits'] + stats['cache_misses'], 1)) * 100, 1),
                        "total_requests": stats['cache_hits'] + stats['cache_misses']
                    },
                    "exchange_health": stats['exchange_health'],
                    "performance": result['metadata']['performance']
                },
                "metadata": {
                    "user_tier": "premium" if is_premium else "free",
                    "last_updated": datetime.now().isoformat()
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get market overview: {str(e)}"
        )

@router.get("/filters/options")
async def get_filter_options():
    """Get available filter options for the mobile app"""
    return {
        "success": True,
        "data": {
            "risk_levels": [
                {"value": "low", "label": "Low Risk", "description": "Conservative opportunities"},
                {"value": "medium", "label": "Medium Risk", "description": "Balanced risk/reward"},
                {"value": "high", "label": "High Risk", "description": "High potential, high risk"}
            ],
            "exchanges": [
                {"value": ex, "label": ex.title(), "tier": tier.value}
                for ex, tier in arbitrage_engine.exchange_tiers.items()
            ],
            "categories": [
                {"value": "layer1", "label": "Layer 1", "description": "Bitcoin, Ethereum, etc."},
                {"value": "layer2", "label": "Layer 2", "description": "Polygon, Arbitrum, etc."},
                {"value": "defi", "label": "DeFi", "description": "Decentralized Finance"},
                {"value": "exchange", "label": "Exchange Tokens", "description": "BNB, FTT, etc."},
                {"value": "meme", "label": "Meme Coins", "description": "DOGE, SHIB, etc."},
                {"value": "payment", "label": "Payment", "description": "XRP, LTC, etc."},
                {"value": "other", "label": "Others", "description": "Other cryptocurrencies"}
            ],
            "volume_ranges": [
                {"value": 10000, "label": "$10K+"},
                {"value": 50000, "label": "$50K+"},
                {"value": 100000, "label": "$100K+"},
                {"value": 500000, "label": "$500K+"},
                {"value": 1000000, "label": "$1M+"}
            ],
            "profit_ranges": [
                {"value": 0.5, "label": "0.5%+"},
                {"value": 1.0, "label": "1.0%+"},
                {"value": 2.0, "label": "2.0%+"},
                {"value": 5.0, "label": "5.0%+"},
                {"value": 10.0, "label": "10.0%+"}
            ]
        }
    }

async def _save_arbitrage_samples(opportunities: List[Dict], db: AsyncSession):
    """Save sample opportunities to database for analytics"""
    try:
        for opp in opportunities[:3]:  # Save top 3 for analytics
            arbitrage_record = ArbitrageData(
                symbol=opp['symbol'],
                exchange1=opp['exchange1'],
                exchange2=opp['exchange2'],
                price1=opp['price1'],
                price2=opp['price2'],
                profit_percent=opp['profit_percent'],
                volume_24h=opp['volume_24h']
            )
            db.add(arbitrage_record)
        
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to save arbitrage samples: {e}")
        await db.rollback()

# Cleanup function for the engine
async def close_arbitrage_engine():
    """Close arbitrage engine connections"""
    await arbitrage_engine.close()