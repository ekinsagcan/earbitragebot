import asyncio
import aiohttp
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional
from threading import Lock
from aiohttp import TCPConnector
from enum import Enum
import statistics
import json

from app.config import settings

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    UNKNOWN = "unknown"

class ExchangeTier(Enum):
    TIER_1 = "tier_1"  # Binance, Coinbase, Kraken
    TIER_2 = "tier_2"  # KuCoin, Gate.io, OKX
    TIER_3 = "tier_3"  # Smaller exchanges

class EnhancedArbitrageEngine:
    def __init__(self):
        # Major exchanges categorized by tier
        self.tier_1_exchanges = {
            'binance': 'https://api.binance.com/api/v3/ticker/24hr',
            'coinbase': 'https://api.exchange.coinbase.com/products',
            'kraken': 'https://api.kraken.com/0/public/Ticker',
        }
        
        self.tier_2_exchanges = {
            'kucoin': 'https://api.kucoin.com/api/v1/market/allTickers',
            'gate': 'https://api.gateio.ws/api/v4/spot/tickers',
            'okx': 'https://www.okx.com/api/v5/market/tickers?instType=SPOT',
            'bybit': 'https://api.bybit.com/v5/market/tickers?category=spot',
            'bitget': 'https://api.bitget.com/api/spot/v1/market/tickers',
        }
        
        self.tier_3_exchanges = {
            'mexc': 'https://api.mexc.com/api/v3/ticker/24hr',
            'huobi': 'https://api.huobi.pro/market/tickers',
            'bitfinex': 'https://api-pub.bitfinex.com/v2/tickers?symbols=ALL',
            'bingx': 'https://open-api.bingx.com/openApi/spot/v1/ticker/24hr',
            'lbank': 'https://api.lbkex.com/v2/ticker/24hr.do',
        }
        
        # Combine all exchanges
        self.all_exchanges = {**self.tier_1_exchanges, **self.tier_2_exchanges, **self.tier_3_exchanges}
        
        # Exchange tier mapping
        self.exchange_tiers = {}
        for ex in self.tier_1_exchanges:
            self.exchange_tiers[ex] = ExchangeTier.TIER_1
        for ex in self.tier_2_exchanges:
            self.exchange_tiers[ex] = ExchangeTier.TIER_2
        for ex in self.tier_3_exchanges:
            self.exchange_tiers[ex] = ExchangeTier.TIER_3
        
        # Premium cryptocurrencies with enhanced metadata
        self.premium_coins = {
            'BTCUSDT': {'category': 'layer1', 'market_cap_rank': 1},
            'ETHUSDT': {'category': 'layer1', 'market_cap_rank': 2},
            'BNBUSDT': {'category': 'exchange', 'market_cap_rank': 4},
            'SOLUSDT': {'category': 'layer1', 'market_cap_rank': 5},
            'XRPUSDT': {'category': 'payment', 'market_cap_rank': 6},
            'ADAUSDT': {'category': 'layer1', 'market_cap_rank': 8},
            'AVAXUSDT': {'category': 'layer1', 'market_cap_rank': 10},
            'DOGEUSDT': {'category': 'meme', 'market_cap_rank': 11},
            'DOTUSDT': {'category': 'layer0', 'market_cap_rank': 12},
            'MATICUSDT': {'category': 'layer2', 'market_cap_rank': 13},
        }
        
        # Trusted coins (expanded from bot)
        self.trusted_symbols = set(self.premium_coins.keys()) | {
            'LINKUSDT', 'LTCUSDT', 'BCHUSDT', 'UNIUSDT', 'ATOMUSDT',
            'VETUSDT', 'FILUSDT', 'TRXUSDT', 'ETCUSDT', 'XLMUSDT',
            'ALGOUSDT', 'ICPUSDT', 'THETAUSDT', 'AXSUSDT', 'SANDUSDT',
            'MANAUSDT', 'CHZUSDT', 'ENJUSDT', 'GALAUSDT', 'APTUSDT',
            'NEARUSDT', 'FLOWUSDT', 'AAVEUSDT', 'COMPUSDT', 'SUSHIUSDT',
        }
        
        # Risk factors
        self.risk_factors = {
            'high_profit_threshold': 10.0,  # >10% is risky
            'low_volume_threshold': 50000,   # <50k is risky  
            'new_listing_days': 30,          # <30 days is risky
            'tier_3_only': True,             # Only tier 3 exchanges is risky
        }
        
        # Cache system with enhanced metadata
        self.cache_data = {}
        self.cache_metadata = {}
        self.cache_timestamp = 0
        self.cache_lock = Lock()
        
        # Performance tracking
        self.performance_metrics = {
            'api_response_times': {},
            'success_rates': {},
            'error_counts': {},
        }
        
        # Connection management
        self.connector = TCPConnector(
            limit=100,
            limit_per_host=10,
            ttl_dns_cache=600,
            use_dns_cache=True,
        )
        self.session = None
        self.request_semaphore = asyncio.Semaphore(20)
        
        # Enhanced stats
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_requests': 0,
            'opportunities_found': 0,
            'risk_filtered': 0,
            'volume_filtered': 0,
            'concurrent_users': 0,
            'avg_response_time': 0,
        }

    async def get_session(self):
        """Get or create optimized aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=15, connect=8)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'CryptoArbitragePro/1.0',
                    'Accept': 'application/json',
                    'Accept-Encoding': 'gzip, deflate'
                }
            )
        return self.session

    def calculate_risk_score(self, opportunity: Dict) -> Tuple[RiskLevel, Dict]:
        """Enhanced risk scoring algorithm"""
        risk_factors = []
        score = 0
        
        # Profit risk (higher profit = higher risk)
        profit = opportunity['profit_percent']
        if profit > self.risk_factors['high_profit_threshold']:
            score += 3
            risk_factors.append(f"high_profit_{profit:.1f}%")
        elif profit > 5.0:
            score += 2
            risk_factors.append(f"medium_profit_{profit:.1f}%")
        elif profit > 2.0:
            score += 1
            risk_factors.append(f"low_profit_{profit:.1f}%")
        
        # Volume risk
        volume = opportunity['volume_24h']
        if volume < self.risk_factors['low_volume_threshold']:
            score += 3
            risk_factors.append(f"low_volume_{volume/1000:.0f}k")
        elif volume < settings.min_volume_threshold:
            score += 2
            risk_factors.append(f"medium_volume_{volume/1000:.0f}k")
        
        # Exchange tier risk
        ex1_tier = self.exchange_tiers.get(opportunity['exchange1'], ExchangeTier.TIER_3)
        ex2_tier = self.exchange_tiers.get(opportunity['exchange2'], ExchangeTier.TIER_3)
        
        if ex1_tier == ExchangeTier.TIER_3 and ex2_tier == ExchangeTier.TIER_3:
            score += 3
            risk_factors.append("tier3_exchanges")
        elif ex1_tier == ExchangeTier.TIER_3 or ex2_tier == ExchangeTier.TIER_3:
            score += 1
            risk_factors.append("mixed_tier_exchanges")
        
        # Symbol trust risk
        symbol = opportunity['symbol']
        if symbol not in self.trusted_symbols:
            score += 2
            risk_factors.append("untrusted_symbol")
        elif symbol in self.premium_coins:
            score -= 1  # Bonus for premium coins
            risk_factors.append("premium_coin")
        
        # Determine risk level
        if score >= 6:
            risk_level = RiskLevel.HIGH
        elif score >= 3:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        return risk_level, {
            'score': score,
            'factors': risk_factors,
            'confidence': min(100, max(20, 100 - (score * 10)))
        }

    def calculate_opportunity_score(self, opportunity: Dict, risk_data: Dict) -> float:
        """AI-inspired opportunity scoring (0-100)"""
        base_score = opportunity['profit_percent'] * 10  # Base on profit
        
        # Volume bonus
        volume_score = min(20, opportunity['volume_24h'] / 10000)
        
        # Exchange tier bonus
        ex1_tier = self.exchange_tiers.get(opportunity['exchange1'], ExchangeTier.TIER_3)
        ex2_tier = self.exchange_tiers.get(opportunity['exchange2'], ExchangeTier.TIER_3)
        
        tier_bonus = 0
        if ex1_tier == ExchangeTier.TIER_1 or ex2_tier == ExchangeTier.TIER_1:
            tier_bonus = 15
        elif ex1_tier == ExchangeTier.TIER_2 or ex2_tier == ExchangeTier.TIER_2:
            tier_bonus = 10
        
        # Premium coin bonus
        premium_bonus = 10 if opportunity['symbol'] in self.premium_coins else 0
        
        # Risk penalty
        risk_penalty = risk_data['score'] * 5
        
        # Calculate final score
        final_score = base_score + volume_score + tier_bonus + premium_bonus - risk_penalty
        return max(0, min(100, final_score))

    async def fetch_enhanced_prices(self, exchange: str) -> Dict[str, Dict]:
        """Enhanced price fetching with performance tracking"""
        start_time = time.time()
        
        async with self.request_semaphore:
            try:
                session = await self.get_session()
                url = self.all_exchanges[exchange]
                
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    self.performance_metrics['api_response_times'][exchange] = response_time
                    
                    if response.status != 200:
                        self.performance_metrics['error_counts'][exchange] = \
                            self.performance_metrics['error_counts'].get(exchange, 0) + 1
                        logger.warning(f"{exchange} returned status {response.status}")
                        return {}
                    
                    data = await response.json()
                    self.stats['api_requests'] += 1
                    
                    # Update success rate
                    self.performance_metrics['success_rates'][exchange] = \
                        self.performance_metrics['success_rates'].get(exchange, 0.95) * 0.9 + 0.1
                    
                    return self.parse_exchange_data(exchange, data)
                    
            except Exception as e:
                response_time = time.time() - start_time
                self.performance_metrics['api_response_times'][exchange] = response_time
                self.performance_metrics['error_counts'][exchange] = \
                    self.performance_metrics['error_counts'].get(exchange, 0) + 1
                
                logger.error(f"{exchange} error: {str(e)}")
                return {}

    def parse_exchange_data(self, exchange: str, data) -> Dict[str, Dict]:
        """Enhanced exchange data parsing with metadata"""
        try:
            parsed_data = {}
            
            if exchange == 'binance':
                for item in data:
                    volume = float(item.get('quoteVolume', 0))
                    if volume > 10000:  # Lower threshold for more data
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['lastPrice']),
                            'volume': volume,
                            'change_24h': float(item.get('priceChangePercent', 0)),
                            'count': int(item.get('count', 0)),
                            'timestamp': datetime.now()
                        }
                        
            elif exchange == 'kucoin':
                ticker_data = data.get('data', {}).get('ticker', [])
                for item in ticker_data:
                    volume = float(item.get('volValue', 0))
                    if volume > 10000:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['last']),
                            'volume': volume,
                            'change_24h': float(item.get('changeRate', 0)) * 100,
                            'timestamp': datetime.now()
                        }
                        
            # Add more enhanced parsers...
            elif exchange == 'gate':
                for item in data:
                    volume = float(item.get('quote_volume', 0))
                    if volume > 10000:
                        symbol = self.normalize_symbol(item['currency_pair'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['last']),
                            'volume': volume,
                            'change_24h': float(item.get('change_percentage', 0)),
                            'timestamp': datetime.now()
                        }
                        
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing {exchange} data: {str(e)}")
            return {}

    def normalize_symbol(self, symbol: str, exchange: str) -> str:
        """Enhanced symbol normalization"""
        normalized = symbol.upper().replace('/', '').replace('-', '').replace('_', '')
        
        # Exchange-specific cleaning
        if exchange == 'bitfinex' and normalized.startswith('T'):
            normalized = normalized[1:]
        elif exchange == 'kraken':
            # Kraken has special naming conventions
            normalized = normalized.replace('XBT', 'BTC')
        
        return normalized

    async def get_enhanced_arbitrage_opportunities(self, is_premium: bool = False, filters: Dict = None) -> Dict:
        """Get arbitrage opportunities with enhanced features"""
        current_time = time.time()
        
        # Check cache
        with self.cache_lock:
            if (current_time - self.cache_timestamp) < settings.cache_duration and self.cache_data:
                self.stats['cache_hits'] += 1
                return self._process_opportunities(self.cache_data, is_premium, filters)
        
        # Fetch fresh data
        self.stats['cache_misses'] += 1
        all_data = await self._fetch_all_enhanced_data()
        
        with self.cache_lock:
            self.cache_data = all_data
            self.cache_timestamp = current_time
            self.cache_metadata = {
                'last_update': datetime.now(),
                'exchange_count': len([ex for ex, data in all_data.items() if data]),
                'symbol_count': len(set(symbol for data in all_data.values() for symbol in data.keys()))
            }
        
        return self._process_opportunities(all_data, is_premium, filters)

    async def _fetch_all_enhanced_data(self) -> Dict:
        """Fetch data from all exchanges with priority"""
        # Prioritize tier 1 exchanges
        tier_1_tasks = [(ex, asyncio.create_task(self.fetch_enhanced_prices(ex))) 
                       for ex in self.tier_1_exchanges.keys()]
        tier_2_tasks = [(ex, asyncio.create_task(self.fetch_enhanced_prices(ex))) 
                       for ex in self.tier_2_exchanges.keys()]
        tier_3_tasks = [(ex, asyncio.create_task(self.fetch_enhanced_prices(ex))) 
                       for ex in self.tier_3_exchanges.keys()]
        
        all_tasks = tier_1_tasks + tier_2_tasks + tier_3_tasks
        results = {}
        
        for exchange, task in all_tasks:
            try:
                data = await task
                if data:
                    results[exchange] = data
            except Exception as e:
                logger.error(f"Error fetching {exchange}: {str(e)}")
        
        return results

    def _process_opportunities(self, all_data: Dict, is_premium: bool, filters: Dict = None) -> Dict:
        """Process opportunities with enhanced filtering and scoring"""
        opportunities = []
        
        # Collect all symbols
        all_symbols = set()
        for exchange_data in all_data.values():
            all_symbols.update(exchange_data.keys())
        
        for symbol in all_symbols:
            symbol_prices = []
            
            # Collect prices for this symbol
            for exchange, exchange_data in all_data.items():
                if symbol in exchange_data:
                    price_data = exchange_data[symbol]
                    symbol_prices.append({
                        'exchange': exchange,
                        'price': price_data['price'],
                        'volume': price_data['volume'],
                        'change_24h': price_data.get('change_24h', 0),
                        'tier': self.exchange_tiers.get(exchange, ExchangeTier.TIER_3)
                    })
            
            # Need at least 2 exchanges
            if len(symbol_prices) < 2:
                continue
            
            # Sort by price
            symbol_prices.sort(key=lambda x: x['price'])
            
            # Find best arbitrage opportunity for this symbol
            lowest = symbol_prices[0]
            highest = symbol_prices[-1]
            
            if lowest['price'] > 0:
                profit_percent = ((highest['price'] - lowest['price']) / lowest['price']) * 100
                
                if profit_percent < 0.1:  # Skip very small opportunities
                    continue
                
                opportunity = {
                    'symbol': symbol,
                    'exchange1': lowest['exchange'],
                    'exchange2': highest['exchange'],
                    'price1': lowest['price'],
                    'price2': highest['price'],
                    'profit_percent': profit_percent,
                    'volume_24h': min(lowest['volume'], highest['volume']),
                    'timestamp': datetime.now(),
                    'buy_exchange_tier': lowest['tier'].value,
                    'sell_exchange_tier': highest['tier'].value,
                    'total_exchanges': len(symbol_prices)
                }
                
                # Calculate risk and opportunity score
                risk_level, risk_data = self.calculate_risk_score(opportunity)
                opportunity_score = self.calculate_opportunity_score(opportunity, risk_data)
                
                opportunity.update({
                    'risk_level': risk_level.value,
                    'risk_data': risk_data,
                    'opportunity_score': opportunity_score,
                    'category': self.premium_coins.get(symbol, {}).get('category', 'other')
                })
                
                # Apply filters
                if self._passes_filters(opportunity, filters):
                    opportunities.append(opportunity)
                    self.stats['opportunities_found'] += 1
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x['opportunity_score'], reverse=True)
        
        # Apply tier limits
        if not is_premium:
            opportunities = opportunities[:10]  # Free users get top 10
        else:
            opportunities = opportunities[:100]  # Premium users get top 100
        
        return {
            'opportunities': opportunities,
            'metadata': {
                'total_found': len(opportunities),
                'is_premium': is_premium,
                'last_updated': datetime.now(),
                'cache_metadata': self.cache_metadata,
                'performance': self._get_performance_summary()
            }
        }

    def _passes_filters(self, opportunity: Dict, filters: Dict = None) -> bool:
        """Enhanced filtering system"""
        if not filters:
            return True
        
        # Risk level filter
        if 'risk_levels' in filters:
            if opportunity['risk_level'] not in filters['risk_levels']:
                self.stats['risk_filtered'] += 1
                return False
        
        # Minimum profit filter
        if 'min_profit' in filters:
            if opportunity['profit_percent'] < filters['min_profit']:
                return False
        
        # Volume filter
        if 'min_volume' in filters:
            if opportunity['volume_24h'] < filters['min_volume']:
                self.stats['volume_filtered'] += 1
                return False
        
        # Exchange filter
        if 'exchanges' in filters:
            if (opportunity['exchange1'] not in filters['exchanges'] and 
                opportunity['exchange2'] not in filters['exchanges']):
                return False
        
        # Category filter
        if 'categories' in filters:
            if opportunity['category'] not in filters['categories']:
                return False
        
        return True

    def _get_performance_summary(self) -> Dict:
        """Get performance metrics summary"""
        avg_response_times = list(self.performance_metrics['api_response_times'].values())
        avg_response_time = statistics.mean(avg_response_times) if avg_response_times else 0
        
        return {
            'avg_response_time': round(avg_response_time, 3),
            'active_exchanges': len(self.performance_metrics['api_response_times']),
            'success_rate': round(statistics.mean(list(self.performance_metrics['success_rates'].values())) * 100, 1) if self.performance_metrics['success_rates'] else 0,
            'total_api_requests': self.stats['api_requests']
        }

    def get_enhanced_stats(self) -> Dict:
        """Get comprehensive statistics"""
        return {
            **self.stats,
            'performance': self._get_performance_summary(),
            'exchange_health': {
                'tier_1': len([ex for ex in self.tier_1_exchanges if ex in self.performance_metrics['success_rates']]),
                'tier_2': len([ex for ex in self.tier_2_exchanges if ex in self.performance_metrics['success_rates']]),
                'tier_3': len([ex for ex in self.tier_3_exchanges if ex in self.performance_metrics['success_rates']])
            }
        }

    async def close(self):
        """Enhanced cleanup"""
        if self.session and not self.session.closed:
            await self.session.close()
        await self.connector.close()
        logger.info("Enhanced arbitrage engine closed")