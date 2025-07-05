import asyncio
import aiohttp
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
from threading import Lock
from aiohttp import TCPConnector

from app.config import settings

logger = logging.getLogger(__name__)

class ArbitrageEngine:
    def __init__(self):
        # Major cryptocurrency exchanges with their APIs
        self.exchanges = {
            'binance': 'https://api.binance.com/api/v3/ticker/24hr',
            'kucoin': 'https://api.kucoin.com/api/v1/market/allTickers',
            'gate': 'https://api.gateio.ws/api/v4/spot/tickers',
            'mexc': 'https://api.mexc.com/api/v3/ticker/24hr',
            'bybit': 'https://api.bybit.com/v5/market/tickers?category=spot',
            'okx': 'https://www.okx.com/api/v5/market/tickers?instType=SPOT',
            'huobi': 'https://api.huobi.pro/market/tickers',
            'bitget': 'https://api.bitget.com/api/spot/v1/market/tickers',
            'coinbase': 'https://api.exchange.coinbase.com/products',
            'kraken': 'https://api.kraken.com/0/public/Ticker',
            'bitfinex': 'https://api-pub.bitfinex.com/v2/tickers?symbols=ALL',
            'cryptocom': 'https://api.crypto.com/v2/public/get-ticker',
            'bingx': 'https://open-api.bingx.com/openApi/spot/v1/ticker/24hr',
            'lbank': 'https://api.lbkex.com/v2/ticker/24hr.do',
            'digifinex': 'https://openapi.digifinex.com/v3/ticker',
            'bitmart': 'https://api-cloud.bitmart.com/spot/v1/ticker',
            'xt': 'https://api.xt.com/data/api/v1/getTickers',
            'phemex': 'https://api.phemex.com/md/ticker/24hr/all',
            'bitstamp': 'https://www.bitstamp.net/api/v2/ticker/',
            'gemini': 'https://api.gemini.com/v1/pricefeed',
            'poloniex': 'https://api.poloniex.com/markets/ticker24h',
            'ascendex': 'https://ascendex.com/api/pro/v1/ticker',
            'coinex': 'https://api.coinex.com/v1/market/ticker/all',
            'hotcoin': 'https://api.hotcoin.top/v1/market/ticker',
            'bigone': 'https://big.one/api/v3/asset_pairs/tickers',
            'probit': 'https://api.probit.com/api/exchange/v1/ticker',
            'latoken': 'https://api.latoken.com/v2/ticker',
            'bitrue': 'https://www.bitrue.com/api/v1/ticker/24hr',
            'tidex': 'https://api.tidex.com/api/3/ticker',
            'p2pb2b': 'https://api.p2pb2b.com/api/v2/public/tickers'
        }
        
        # Trusted major cryptocurrencies
        self.trusted_symbols = {
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT', 
            'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT',
            'LINKUSDT', 'LTCUSDT', 'BCHUSDT', 'UNIUSDT', 'ATOMUSDT',
            'VETUSDT', 'FILUSDT', 'TRXUSDT', 'ETCUSDT', 'XLMUSDT',
            'ALGOUSDT', 'ICPUSDT', 'THETAUSDT', 'AXSUSDT', 'SANDUSDT',
            'MANAUSDT', 'CHZUSDT', 'ENJUSDT', 'GALAUSDT', 'APTUSDT',
            'NEARUSDT', 'FLOWUSDT', 'AAVEUSDT', 'COMPUSDT', 'SUSHIUSDT',
            'YFIUSDT', 'SNXUSDT', 'MKRUSDT', 'CRVUSDT', '1INCHUSDT',
            'RUNEUSDT', 'LUNA2USDT', 'FTMUSDT', 'ONEUSDT', 'ZILUSDT',
            'ZECUSDT', 'DASHUSDT', 'WAVESUSDT', 'ONTUSDT', 'QTUMUSDT'
        }
        
        # Suspicious symbols - common names used for different coins
        self.suspicious_symbols = {
            'SUN', 'MOON', 'DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BABY',
            'SAFE', 'MINI', 'MICRO', 'MEGA', 'SUPER', 'ULTRA', 'ELON',
            'MARS', 'ROCKET', 'DIAMOND', 'GOLD', 'SILVER', 'TITAN',
            'RISE', 'FIRE', 'ICE', 'SNOW', 'STORM', 'THUNDER', 'LIGHTNING'
        }
        
        # Symbol mapping for different exchange formats
        self.symbol_mapping = {
            'BTC/USDT': 'BTCUSDT',
            'BTC-USDT': 'BTCUSDT',
            'BTC_USDT': 'BTCUSDT',
            'tBTCUSDT': 'BTCUSDT',
            'ETH/USDT': 'ETHUSDT',
            'ETH-USDT': 'ETHUSDT',
            'ETH_USDT': 'ETHUSDT',
            'tETHUSDT': 'ETHUSDT'
        }
        
        # Cache sistemi
        self.cache_data = {}
        self.cache_timestamp = 0
        self.cache_lock = Lock()
        
        # API request limitleri
        self.is_fetching = False
        self.last_fetch_time = 0
        
        # Connection pool
        self.connector = TCPConnector(
            limit=50,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self.session = None
        
        # Request semaphore
        self.request_semaphore = asyncio.Semaphore(settings.max_concurrent_requests)
        
        # Stats
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_requests': 0,
            'concurrent_users': 0
        }

    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={'User-Agent': 'ArbitrageBot/1.0'}
            )
        return self.session

    def normalize_symbol(self, symbol: str, exchange: str) -> str:
        """Normalize symbol format across exchanges"""
        normalized = symbol.upper().replace('/', '').replace('-', '').replace('_', '')
        
        if exchange == 'bitfinex' and normalized.startswith('T'):
            normalized = normalized[1:]
        
        if symbol in self.symbol_mapping:
            normalized = self.symbol_mapping[symbol]
        
        return normalized

    async def fetch_prices_with_volume(self, exchange: str) -> Dict[str, Dict]:
        """Fetch prices and volumes from exchange"""
        async with self.request_semaphore:
            try:
                session = await self.get_session()
                url = self.exchanges[exchange]
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"{exchange} returned status {response.status}")
                        return {}
                    
                    data = await response.json()
                    self.stats['api_requests'] += 1
                    return self.parse_exchange_data(exchange, data)
                    
            except Exception as e:
                logger.error(f"{exchange} price/volume error: {str(e)}")
                return {}

    def parse_exchange_data(self, exchange: str, data) -> Dict[str, Dict]:
        """Parse exchange-specific data format"""
        try:
            parsed_data = {}
            
            if exchange == 'binance':
                for item in data:
                    if float(item.get('volume', 0)) > settings.min_volume_threshold:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['lastPrice']),
                            'volume': float(item['quoteVolume'])
                        }
                        
            elif exchange == 'kucoin':
                for item in data.get('data', {}).get('ticker', []):
                    if float(item.get('volValue', 0)) > settings.min_volume_threshold:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['last']),
                            'volume': float(item['volValue'])
                        }
                        
            elif exchange == 'gate':
                for item in data:
                    if float(item.get('quote_volume', 0)) > settings.min_volume_threshold:
                        symbol = self.normalize_symbol(item['currency_pair'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['last']),
                            'volume': float(item['quote_volume'])
                        }
                        
            elif exchange == 'mexc':
                for item in data:
                    if float(item.get('quoteVolume', 0)) > settings.min_volume_threshold:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        parsed_data[symbol] = {
                            'price': float(item['lastPrice']),
                            'volume': float(item['quoteVolume'])
                        }
                        
            # Add more exchange parsers as needed...
                        
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing {exchange} data: {str(e)}")
            return {}

    async def get_all_prices_with_volume(self) -> Dict[str, Dict[str, Dict]]:
        """Fetch prices from all exchanges concurrently"""
        tasks = []
        for exchange in self.exchanges.keys():
            task = asyncio.create_task(self.fetch_prices_with_volume(exchange))
            tasks.append((exchange, task))
        
        results = {}
        for exchange, task in tasks:
            try:
                data = await task
                if data:
                    results[exchange] = data
            except Exception as e:
                logger.error(f"Error fetching {exchange}: {str(e)}")
        
        return results

    def is_symbol_safe(self, symbol: str, exchange_data: Dict[str, Dict]) -> Tuple[bool, str]:
        """Check if symbol is safe for arbitrage"""
        # Trusted symbols are always safe
        if symbol in self.trusted_symbols:
            return True, "trusted"
        
        # Check suspicious symbol names
        symbol_base = symbol.replace('USDT', '').replace('BTC', '').replace('ETH', '')
        if symbol_base in self.suspicious_symbols:
            return False, f"suspicious_name_{symbol_base}"
        
        # Count exchanges that have this symbol
        exchange_count = sum(1 for ex_data in exchange_data.values() if symbol in ex_data)
        
        if exchange_count < 2:
            return False, "insufficient_exchanges"
        
        if exchange_count >= 5:
            return True, f"multiple_exchanges_{exchange_count}"
        
        return True, f"limited_exchanges_{exchange_count}"

    def validate_arbitrage_opportunity(self, opportunity: Dict) -> bool:
        """Validate arbitrage opportunity"""
        profit = opportunity['profit_percent']
        volume = opportunity['volume_24h']
        
        # Check volume threshold
        if volume < settings.min_volume_threshold:
            return False
        
        # Check profit threshold (suspicious if too high)
        if profit > settings.max_profit_threshold:
            return False
        
        # Check minimum profit
        if profit < 0.1:  # 0.1% minimum
            return False
        
        return True

    def calculate_arbitrage(self, all_data: Dict[str, Dict[str, Dict]], is_premium: bool = False) -> List[Dict]:
        """Calculate arbitrage opportunities"""
        opportunities = []
        
        # Collect all symbols across exchanges
        all_symbols = set()
        for exchange_data in all_data.values():
            all_symbols.update(exchange_data.keys())
        
        for symbol in all_symbols:
            symbol_prices = []
            
            # Get prices from all exchanges for this symbol
            for exchange, exchange_data in all_data.items():
                if symbol in exchange_data:
                    price_data = exchange_data[symbol]
                    symbol_prices.append({
                        'exchange': exchange,
                        'price': price_data['price'],
                        'volume': price_data['volume']
                    })
            
            # Need at least 2 exchanges for arbitrage
            if len(symbol_prices) < 2:
                continue
            
            # Check if symbol is safe
            is_safe, safety_reason = self.is_symbol_safe(symbol, all_data)
            if not is_safe:
                continue
            
            # Sort by price
            symbol_prices.sort(key=lambda x: x['price'])
            
            # Calculate arbitrage between lowest and highest
            lowest = symbol_prices[0]
            highest = symbol_prices[-1]
            
            if lowest['price'] > 0:
                profit_percent = ((highest['price'] - lowest['price']) / lowest['price']) * 100
                
                opportunity = {
                    'symbol': symbol,
                    'exchange1': lowest['exchange'],
                    'exchange2': highest['exchange'],
                    'price1': lowest['price'],
                    'price2': highest['price'],
                    'profit_percent': profit_percent,
                    'volume_24h': min(lowest['volume'], highest['volume']),
                    'timestamp': datetime.now()
                }
                
                # Validate opportunity
                if self.validate_arbitrage_opportunity(opportunity):
                    # Apply premium/free user filters
                    if not is_premium and profit_percent > settings.free_user_max_profit:
                        opportunity['profit_percent'] = settings.free_user_max_profit
                    
                    opportunities.append(opportunity)
        
        # Sort by profit percentage
        opportunities.sort(key=lambda x: x['profit_percent'], reverse=True)
        
        # Limit results for free users
        if not is_premium:
            opportunities = opportunities[:10]  # Top 10 for free users
        
        return opportunities

    async def get_cached_arbitrage_data(self, is_premium: bool = False) -> List[Dict]:
        """Get cached arbitrage data or fetch fresh data"""
        current_time = time.time()
        
        with self.cache_lock:
            if (current_time - self.cache_timestamp) < settings.cache_duration and self.cache_data:
                self.stats['cache_hits'] += 1
                return self.calculate_arbitrage(self.cache_data, is_premium)
        
        # Fetch fresh data
        self.stats['cache_misses'] += 1
        return await self._fetch_fresh_data(is_premium)

    async def _fetch_fresh_data(self, is_premium: bool) -> List[Dict]:
        """Fetch fresh data from exchanges"""
        if self.is_fetching:
            # Wait for ongoing fetch
            while self.is_fetching:
                await asyncio.sleep(0.1)
            return self.calculate_arbitrage(self.cache_data, is_premium)
        
        self.is_fetching = True
        try:
            all_data = await self.get_all_prices_with_volume()
            
            with self.cache_lock:
                self.cache_data = all_data
                self.cache_timestamp = time.time()
            
            return self.calculate_arbitrage(all_data, is_premium)
        
        finally:
            self.is_fetching = False

    async def get_specific_symbol_prices(self, symbol_to_find: str) -> List[Tuple[str, float]]:
        """Get prices for a specific symbol across exchanges"""
        all_data = await self.get_all_prices_with_volume()
        symbol_prices = []
        
        normalized_symbol = symbol_to_find.upper()
        
        for exchange, exchange_data in all_data.items():
            if normalized_symbol in exchange_data:
                price_data = exchange_data[normalized_symbol]
                symbol_prices.append({
                    'exchange': exchange,
                    'price': price_data['price'],
                    'volume': price_data.get('volume', 0)
                })
        
        # Sort by price
        symbol_prices.sort(key=lambda x: x['price'])
        return symbol_prices

    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return self.stats.copy()

    async def close(self):
        """Close connections"""
        if self.session and not self.session.closed:
            await self.session.close()
        await self.connector.close()