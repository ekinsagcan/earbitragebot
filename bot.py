import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
import aiohttp
from aiohttp import TCPConnector
import psycopg2 # PostgreSQL için yeni import
from urllib.parse import urlparse # DATABASE_URL'yi parse etmek için yeni import
import time
from threading import Lock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Gumroad API settings
GUMROAD_PRODUCT_ID = os.getenv("GUMROAD_PRODUCT_ID", "")
GUMROAD_ACCESS_TOKEN = os.getenv("GUMROAD_ACCESS_TOKEN", "")

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Gumroad link and support username from environment variables
GUMROAD_LINK = os.getenv("GUMROAD_LINK", "https://gumroad.com/l/your-product")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@arbitragebotsupport")

class ArbitrageBot:
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
        
        # Trusted major cryptocurrencies - these are generally the same across all exchanges
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
        
        # Minimum 24h volume threshold - filter low volume coins
        self.min_volume_threshold = 100000  # $100k minimum 24h volume
        
        # Maximum profit threshold - very high differences are suspicious
        self.max_profit_threshold = 20.0  # 20%+ profit is suspicious
        
        # Free user maximum profit display
        self.free_user_max_profit = 2.0  # Show max 2% profit for free users
        
        # Premium users cache
        self.premium_users = set()
        
        # Database connection details from environment variable
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if not self.DATABASE_URL:
            logger.error("DATABASE_URL environment variable not found!")
            raise ValueError("DATABASE_URL must be set for database connection.")

        self.conn = None # We will establish connection when needed
        self.init_database()
        self.load_premium_users()
        self.load_used_license_keys()

        self.max_profit_threshold = 20.0  # Normal kullanıcılar için %20 limit
        self.admin_max_profit_threshold = 40.0 # Adminler için %40 limit (önceki komuttan kalma, şu an yeni komutta kullanılmayacak)

        # License key validation cache
        self.used_license_keys = set()
        
        # Cache sistemi
        self.cache_data = {}
        self.cache_timestamp = 0
        self.cache_duration = 30  # 30 saniye cache
        self.cache_lock = Lock()
        
        # API request limitleri
        self.is_fetching = False
        self.last_fetch_time = 0
        self.min_fetch_interval = 15  # Minimum 15 saniye arayla fetch

        # Connection pool
        self.connector = TCPConnector(
            limit=50,  # Toplam connection sayısı
            limit_per_host=5,  # Her host için max connection
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self.session = None
        
        # Request semaphore (aynı anda max 10 request)
        self.request_semaphore = asyncio.Semaphore(10)
        
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_requests': 0,
            'concurrent_users': 0
        }

    def get_db_connection(self):
        """Get or create a PostgreSQL database connection."""
        if self.conn is None or self.conn.closed:
            try:
                # Parse the DATABASE_URL to get individual components
                url = urlparse(self.DATABASE_URL)
                self.conn = psycopg2.connect(
                    host=url.hostname,
                    port=url.port,
                    user=url.username,
                    password=url.password,
                    database=url.path[1:] # Slice to remove the leading '/'
                )
                logger.info("Successfully connected to PostgreSQL database.")
            except Exception as e:
                logger.error(f"Error connecting to PostgreSQL: {e}")
                raise
        return self.conn

    async def get_cached_arbitrage_data(self, is_premium: bool = False):
        # Cache hit/miss sayacı
        if self.cache_data and (time.time() - self.cache_timestamp) < self.cache_duration:
            self.stats['cache_hits'] += 1
        else:
            self.stats['cache_misses'] += 1

    async def get_admin_arbitrage_data(self, is_premium: bool = False):
        """Adminler için Huobi hariç ve yüksek limitli arbitraj verisi getir"""
        # Orijinal limiti sakla
        original_limit = self.max_profit_threshold
    
        try:
            # Admin limitini geçici olarak ayarla
            self.max_profit_threshold = self.admin_max_profit_threshold
        
            current_time = time.time()
            with self.cache_lock:
                if (current_time - self.cache_timestamp) < self.cache_duration and self.cache_data:
                    logger.info("Returning cached data for admin")
                    # Huobi verilerini filtrele
                    filtered_data = {ex: data for ex, data in self.cache_data.items() if ex != 'huobi'}
                    return self.calculate_arbitrage(filtered_data, True)  # Admin olduğu için premium=True

            # Yeni veri çek
            all_data = await self.get_all_prices_with_volume()
            # Huobi verilerini filtrele
            filtered_data = {ex: data for ex, data in all_data.items() if ex != 'huobi'}
        
            return self.calculate_arbitrage(filtered_data, True)  # Admin olduğu için premium=True
    
        finally:
            # Orijinal limiti geri yükle
            self.max_profit_threshold = original_limit

    async def get_session(self):
        """Paylaşılan session döndür"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={'User-Agent': 'ArbitrageBot/1.0'}
            )
        return self.session

    async def fetch_prices_with_volume(self, exchange: str) -> Dict[str, Dict]:
        """Rate limited price fetch"""
        async with self.request_semaphore:
            try:
                session = await self.get_session()
                url = self.exchanges[exchange]
                
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"{exchange} returned status {response.status}")
                        return {}
                    
                    data = await response.json()
                    return self.parse_exchange_data(exchange, data)
                    
            except Exception as e:
                logger.error(f"{exchange} error: {str(e)}")
                return {}
    
    def init_database(self):
        """Initialize PostgreSQL database tables."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY, -- Use BIGINT for user_id
                        username TEXT,
                        subscription_end DATE,
                        is_premium BOOLEAN DEFAULT FALSE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS arbitrage_data (
                        id SERIAL PRIMARY KEY, -- SERIAL for auto-incrementing ID
                        symbol TEXT,
                        exchange1 TEXT,
                        exchange2 TEXT,
                        price1 REAL,
                        price2 REAL,
                        profit_percent REAL,
                        volume_24h REAL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        added_by_admin BOOLEAN DEFAULT TRUE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        subscription_end DATE
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS license_keys (
                         license_key TEXT PRIMARY KEY,
                         user_id BIGINT,
                         username TEXT,
                         used_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         gumroad_sale_id TEXT
                    )
                ''')
            conn.commit()
            logger.info("PostgreSQL tables initialized or already exist.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback() # Rollback in case of error
        finally:
            # No need to close connection here, get_db_connection handles it
            pass

    async def cache_refresh_task(self):
        """Her 25 saniyede bir cache'i yenile"""
        while True:
            try:
                await asyncio.sleep(25)  # 25 saniye bekle
            
                # Sadece cache eski ise yenile
                current_time = time.time()
                if (current_time - self.cache_timestamp) > 20:  # Cache 20 saniyeden eski ise
                    logger.info("Background cache refresh")
                    await self._fetch_fresh_data(False)
                
            except Exception as e:
                logger.error(f"Background cache refresh error: {e}")
                await asyncio.sleep(60)  # Hata durumunda 1 dakika bekle
    
    def load_premium_users(self):
        """Load premium users into memory from PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id FROM premium_users')
                results = cursor.fetchall()
                self.premium_users = {row[0] for row in results}
                logger.info(f"Loaded {len(self.premium_users)} premium users from PostgreSQL.")
        except Exception as e:
            logger.error(f"Error loading premium users: {e}")
            self.premium_users = set() # Ensure it's still a set if error occurs

    def load_used_license_keys(self):
        """Load used license keys into memory from PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT license_key FROM license_keys')
                results = cursor.fetchall()
                self.used_license_keys = {row[0] for row in results}
        except Exception as e:
            logger.error(f"Error loading used license keys: {e}")
            self.used_license_keys = set() # Ensure it's still a set if error occurs

    async def verify_gumroad_license(self, license_key: str) -> Dict:
        """Verify license key with Gumroad API"""
        try:
            # Debug: Environment variables kontrolü
            logger.info(f"GUMROAD_PRODUCT_ID: {GUMROAD_PRODUCT_ID}")
            logger.info(f"GUMROAD_ACCESS_TOKEN: {'SET' if GUMROAD_ACCESS_TOKEN else 'EMPTY'}")
        
            headers = {
                'Authorization': f'Bearer {GUMROAD_ACCESS_TOKEN}',
                'Content-Type': 'application/json'
            }
    
            url = f"https://api.gumroad.com/v2/licenses/verify"
            data = {
                'product_id': GUMROAD_PRODUCT_ID,
                'license_key': license_key,
                'increment_uses_count': 'false'
            }
        
            # Debug: Request bilgilerini log'la
            logger.info(f"Verifying license: {license_key}")
            logger.info(f"Request URL: {url}")
            logger.info(f"Request data: {data}")
    
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                
                    # Debug: Response bilgilerini log'la
                    logger.info(f"Response status: {response.status}")
                    logger.info(f"Response text: {response_text}")
                
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"Response JSON: {result}")
                        return result
                    else:
                        logger.error(f"Gumroad API error: {response.status} - {response_text}")
                        return {'success': False, 'error': f'API Error: {response.status}'}
        
        except Exception as e:
            logger.error(f"License verification error: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def activate_license_key(self, license_key: str, user_id: int, username: str, sale_data: Dict):
        """Activate license key and add premium subscription in PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Save license key usage
                cursor.execute('''
                    INSERT INTO license_keys 
                    (license_key, user_id, username, gumroad_sale_id)
                    VALUES (%s, %s, %s, %s)
                ''', (license_key, user_id, username, sale_data.get('sale_id', '')))
                
                # Add premium subscription (30 days)
                end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                cursor.execute('''
                    INSERT INTO premium_users 
                    (user_id, username, subscription_end)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET 
                        username = EXCLUDED.username,
                        subscription_end = EXCLUDED.subscription_end,
                        added_date = CURRENT_TIMESTAMP
                ''', (user_id, username, end_date))
                
            conn.commit()
            
            # Update memory cache
            self.used_license_keys.add(license_key)
            self.premium_users.add(user_id)
            
            logger.info(f"License activated: {license_key} for user {user_id}.")
        except Exception as e:
            logger.error(f"Error activating license key: {e}")
            conn.rollback() # Rollback changes if an error occurs
    
    def add_premium_user(self, user_id: int, username: str = "", days: int = 30):
        """Add premium user (admin command) to PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
                cursor.execute('''
                    INSERT INTO premium_users 
                    (user_id, username, subscription_end)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET 
                        username = EXCLUDED.username,
                        subscription_end = EXCLUDED.subscription_end,
                        added_date = CURRENT_TIMESTAMP
                ''', (user_id, username, end_date))
            conn.commit()
            self.premium_users.add(user_id)
            logger.info(f"Added premium user: {user_id} (@{username}) for {days} days to PostgreSQL.")
        except Exception as e:
            logger.error(f"Error adding premium user: {e}")
            conn.rollback()

    def remove_premium_user(self, user_id: int):
        """Remove premium user (admin command) from PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM premium_users WHERE user_id = %s', (user_id,))
                conn.commit()
                self.premium_users.discard(user_id)
        except Exception as e:
            logger.error(f"Error removing premium user: {e}")
            conn.rollback()
    
    def normalize_symbol(self, symbol: str, exchange: str) -> str:
        """Normalize symbol format across exchanges"""
        # Remove common separators and convert to standard format
        normalized = symbol.upper().replace('/', '').replace('-', '').replace('_', '')
        
        # Handle exchange-specific prefixes
        if exchange == 'bitfinex' and normalized.startswith('T'):
            normalized = normalized[1:]  # Remove 't' prefix
        
        # Handle specific mappings
        if symbol in self.symbol_mapping:
            normalized = self.symbol_mapping[symbol]
        
        return normalized
    
    async def fetch_prices_with_volume(self, exchange: str) -> Dict[str, Dict]:
        """Fetch prices and volumes from exchange"""
        async with self.request_semaphore: # This semaphore is correctly used here
            try:
                session = await self.get_session() # Use the shared session
                url = self.exchanges[exchange]
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.warning(f"{exchange} returned status {response.status}")
                        return {}
                    
                    data = await response.json()
                    return self.parse_exchange_data(exchange, data)
                    
            except Exception as e:
                logger.error(f"{exchange} price/volume error: {str(e)}")
                return {}
    
    def parse_exchange_data(self, exchange: str, data) -> Dict[str, Dict]:
        """Parse exchange-specific data format"""
        try:
            if exchange == 'binance':
                return {
                    self.normalize_symbol(item['symbol'], exchange): {
                        'price': float(item['lastPrice']),
                        'volume': float(item['quoteVolume']),
                        'count': int(item['count'])
                    } for item in data 
                    if float(item['quoteVolume']) > self.min_volume_threshold
                }
            
            elif exchange == 'kucoin':
                if 'data' in data and 'ticker' in data['data']:
                    return {
                        self.normalize_symbol(item['symbol'], exchange): {
                            'price': float(item['last']),
                            'volume': float(item['volValue']) if item['volValue'] else 0
                        } for item in data['data']['ticker'] 
                        if item['volValue'] and float(item['volValue']) > self.min_volume_threshold
                    }
            
            elif exchange == 'gate':
                return {
                    self.normalize_symbol(item['currency_pair'], exchange): {
                        'price': float(item['last']),
                        'volume': float(item['quote_volume']) if item['quote_volume'] else 0
                    } for item in data 
                    if item['quote_volume'] and float(item['quote_volume']) > self.min_volume_threshold
                }
            
            elif exchange == 'mexc':
                return {
                    self.normalize_symbol(item['symbol'], exchange): {
                        'price': float(item['lastPrice']),
                        'volume': float(item['quoteVolume'])
                    } for item in data 
                    if float(item.get('quoteVolume', 0)) > self.min_volume_threshold
                }
            
            elif exchange == 'bybit':
                if 'result' in data and 'list' in data['result']:
                    return {
                        self.normalize_symbol(item['symbol'], exchange): {
                            'price': float(item['lastPrice']),
                            'volume': float(item['turnover24h']) if item['turnover24h'] else 0
                        } for item in data['result']['list'] 
                        if item['turnover24h'] and float(item['turnover24h']) > self.min_volume_threshold
                    }
            
            elif exchange == 'okx':
                if 'data' in data:
                    return {
                        self.normalize_symbol(item['instId'], exchange): {
                            'price': float(item['last']),
                            'volume': float(item['volCcy24h']) if item['volCcy24h'] else 0
                        } for item in data['data'] 
                        if item['volCcy24h'] and float(item['volCcy24h']) > self.min_volume_threshold
                    }
            
            elif exchange == 'huobi':
                if 'data' in data:
                    return {
                        self.normalize_symbol(item['symbol'], exchange): {
                            'price': float(item['close']),
                            'volume': float(item['vol']) if item['vol'] else 0
                        } for item in data['data'] 
                        if item['vol'] and float(item['vol']) > self.min_volume_threshold / 100
                    }
            
            elif exchange == 'bitget':
                if 'data' in data:
                    return {
                        self.normalize_symbol(item['symbol'], exchange): {
                            'price': float(item['close']),
                            'volume': float(item['quoteVol']) if item['quoteVol'] else 0
                        } for item in data['data'] 
                        if item['quoteVol'] and float(item['quoteVol']) > self.min_volume_threshold
                    }
            
            elif exchange == 'bitfinex':
                if isinstance(data, list):
                    result = {}
                    for item in data:
                        if len(item) >= 8:
                            symbol = self.normalize_symbol(item[0], exchange)
                            if item[7] and float(item[7]) > self.min_volume_threshold:
                                result[symbol] = {
                                    'price': float(item[6]),
                                    'volume': float(item[7])
                                }
                    return result
            
            elif exchange == 'kraken':
                result = {}
                for symbol, ticker_data in data.get('result', {}).items():
                    if 'c' in ticker_data and 'v' in ticker_data:
                        normalized_symbol = self.normalize_symbol(symbol, exchange)
                        volume = float(ticker_data['v'][1]) * float(ticker_data['c'][0])
                        if volume > self.min_volume_threshold:
                            result[normalized_symbol] = {
                                'price': float(ticker_data['c'][0]),
                                'volume': volume
                            }
                return result
            
            elif exchange == 'coinbase':
                if isinstance(data, list):
                    result = {}
                    for item in data:
                        if 'id' in item and 'price' in item and 'volume_24h' in item:
                            symbol = self.normalize_symbol(item['id'], exchange)
                            volume = float(item['volume_24h']) if item['volume_24h'] else 0
                            if volume > self.min_volume_threshold:
                                result[symbol] = {
                                    'price': float(item['price']),
                                    'volume': volume
                                }
                    return result
            
            elif exchange == 'poloniex':
                result = {}
                for symbol, ticker_data in data.items():
                    if 'close' in ticker_data and 'quoteVolume' in ticker_data:
                        normalized_symbol = self.normalize_symbol(symbol, exchange)
                        volume = float(ticker_data['quoteVolume'])
                        if volume > self.min_volume_threshold:
                            result[normalized_symbol] = {
                                'price': float(ticker_data['close']),
                                'volume': volume
                            }
                return result
            
            # Add more exchange parsers as needed...
            
        except Exception as e:
            logger.error(f"Error parsing {exchange} data: {str(e)}")
        
        return {}

    async def get_cached_arbitrage_data(self, is_premium: bool = False):
        """Cache'den veri döndür, gerekirse yenile"""
        current_time = time.time()
    
        with self.cache_lock:
            # Cache geçerli mi kontrol et
            if (current_time - self.cache_timestamp) < self.cache_duration and self.cache_data:
                logger.info("Returning cached data")
                return self.calculate_arbitrage(self.cache_data, is_premium)
        
            # Eğer başka bir request zaten fetch yapıyorsa bekle
            if self.is_fetching:
                # Son cache'i döndür (varsa)
                if self.cache_data:
                    logger.info("Fetch in progress, returning last cached data")
                    return self.calculate_arbitrage(self.cache_data, is_premium)
        
            # Minimum fetch interval kontrolü
            if (current_time - self.last_fetch_time) < self.min_fetch_interval:
                if self.cache_data:
                    logger.info("Rate limit protection, returning cached data")
                    return self.calculate_arbitrage(self.cache_data, is_premium)
    
        # Yeni veri fetch et
        return await self._fetch_fresh_data(is_premium)

    async def _fetch_fresh_data(self, is_premium: bool):
        """Yeni veri çek ve cache'le"""
        with self.cache_lock:
            if self.is_fetching:  # Double-check locking
                if self.cache_data:
                    return self.calculate_arbitrage(self.cache_data, is_premium)
        
            self.is_fetching = True
    
        try:
            logger.info("Fetching fresh data from exchanges")
            all_data = await self.get_all_prices_with_volume()
        
            with self.cache_lock:
                self.cache_data = all_data
                self.cache_timestamp = time.time()
                self.last_fetch_time = time.time()
        
            return self.calculate_arbitrage(all_data, is_premium)
    
        finally:
            with self.cache_lock:
                self.is_fetching = False
    
    async def get_all_prices_with_volume(self) -> Dict[str, Dict[str, Dict]]:
        """Fetch price and volume data from all exchanges"""
        tasks = [self.fetch_prices_with_volume(exchange) for exchange in self.exchanges]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        exchange_data = {}
        for exchange, result in zip(self.exchanges.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {exchange}: {result}")
                exchange_data[exchange] = {}
            else:
                exchange_data[exchange] = result
                logger.info(f"{exchange}: {len(result)} symbols fetched")
        
        return exchange_data

    async def get_specific_symbol_prices(self, symbol_to_find: str) -> List[Tuple[str, float]]:
        """
        Fetches the price of a specific symbol from all exchanges and returns them sorted.
        Returns a list of (exchange_name, price) tuples.
        """
        normalized_symbol_to_find = self.normalize_symbol(symbol_to_find, "general")
        
        # Fetch data from all exchanges
        all_exchange_data = await self.get_all_prices_with_volume()
        
        found_prices = []
        for exchange_name, data_for_exchange in all_exchange_data.items():
            if normalized_symbol_to_find in data_for_exchange:
                price = data_for_exchange[normalized_symbol_to_find]['price']
                if price > 0: # Only include valid prices
                    found_prices.append((exchange_name, price))
        
        # Sort by price (cheapest to most expensive)
        found_prices.sort(key=lambda x: x[1])
        return found_prices
    
    def is_symbol_safe(self, symbol: str, exchange_data: Dict[str, Dict]) -> Tuple[bool, str]:
        """Check if symbol is safe for arbitrage and return reason."""
        
        logger.info(f"Checking safety for symbol: {symbol}")
        logger.info(f"Exchange data for {symbol}: {exchange_data}")

        # 1. Trusted symbols list
        if symbol in self.trusted_symbols:
            logger.info(f"{symbol} is a trusted symbol.")
            return (True, "✅ Trusted symbol with verified history and high liquidity.")
        
        # 2. Extract volumes and filter non-zero
        volumes = [data.get('volume', 0) for data in exchange_data.values()]
        non_zero_volumes = [v for v in volumes if v > 0]
        logger.info(f"Non-zero volumes for {symbol}: {non_zero_volumes}")

        if not non_zero_volumes:
            logger.warning(f"No current volume data available for {symbol}.")
            return (False, "❌ No current volume data available on any exchange.")

        total_volume = sum(non_zero_volumes)
        exchanges_with_sufficient_volume = sum(1 for v in non_zero_volumes if v >= self.min_volume_threshold)
        logger.info(f"Total volume for {symbol}: ${total_volume:,.0f}, Exchanges with sufficient volume: {exchanges_with_sufficient_volume}")
        
        # 3. Suspicious symbol check
        base_symbol = symbol.replace('USDT', '').replace('USDC', '').replace('BUSD', '')
        is_suspicious_name = any(suspicious in base_symbol.upper() for suspicious in self.suspicious_symbols)
        logger.info(f"Is {symbol} a suspicious name? {is_suspicious_name}")

        if is_suspicious_name:
            if total_volume > self.min_volume_threshold * 5 and exchanges_with_sufficient_volume >= 3: # Require more exchanges for suspicious names
                logger.info(f"Suspicious symbol {symbol} deemed safe due to high volume and sufficient exchanges.")
                return (True, f"🔍 Symbol has a suspicious name, but is deemed safe due to high total volume (${total_volume:,.0f}) and presence on {exchanges_with_sufficient_volume} major exchanges.")
            else:
                logger.warning(f"Suspicious symbol {symbol} deemed unsafe. Total volume: ${total_volume:,.0f}, Exchanges with sufficient volume: {exchanges_with_sufficient_volume}.")
                return (False, f"❌ Symbol has a suspicious name. Total volume (${total_volume:,.0f}) is insufficient or not present on enough major exchanges ({exchanges_with_sufficient_volume} of minimum 3 needed for suspicious symbols).")

        # 4. General safety checks for non-trusted, non-suspicious symbols
        if total_volume < self.min_volume_threshold * 2: # Require higher total volume for non-trusted symbols
            logger.warning(f"Total volume for {symbol} (${total_volume:,.0f}) is below the required threshold (${self.min_volume_threshold * 2:,.0f}).")
            return (False, f"❌ Total volume (${total_volume:,.0f}) is below the required threshold (${self.min_volume_threshold * 2:,.0f}).")
        
        if exchanges_with_sufficient_volume < 2:
            logger.warning(f"{symbol} found on only {exchanges_with_sufficient_volume} exchange(s) with sufficient volume (minimum 2 required).")
            return (False, f"❌ Found on only {exchanges_with_sufficient_volume} exchange(s) with sufficient volume (minimum 2 required).")

        # 5. Volume differences too large? (one exchange very high, another very low)
        if len(non_zero_volumes) >= 2:
            max_vol = max(non_zero_volumes)
            min_vol = min(non_zero_volumes)
            if min_vol > 0 and max_vol > min_vol * 100:  # 100x difference is suspicious
                logger.warning(f"Significant volume discrepancy detected for {symbol}. Max volume (${max_vol:,.0f}) is more than 100x minimum volume (${min_vol:,.0f}).")
                return (False, f"❌ Significant volume discrepancy detected. Max volume (${max_vol:,.0f}) is more than 100x minimum volume (${min_vol:,.0f}), indicating potential liquidity issues or data anomalies.")

        logger.info(f"{symbol} met general safety criteria.")
        return (True, f"✅ General safety criteria met: Sufficient total volume (${total_volume:,.0f}) and presence on {exchanges_with_sufficient_volume} exchanges.")
    
    def validate_arbitrage_opportunity(self, opportunity: Dict) -> bool:
        """Validate if arbitrage opportunity is real"""
        
        # 1. Profit ratio too high?
        if opportunity['profit_percent'] > self.max_profit_threshold:
            logger.warning(f"Suspicious high profit: {opportunity['symbol']} - {opportunity['profit_percent']:.2f}%")
            return False
        
        # 2. Price difference reasonable?
        price_ratio = opportunity['sell_price'] / opportunity['buy_price']
        if price_ratio > 1.3:  # More than 30% difference is suspicious
            return False
        
        # 3. Minimum profit threshold
        if opportunity['profit_percent'] < 0.1:  # Less than 0.1% profit is meaningless
            return False
        
        return True
    
    def calculate_arbitrage(self, all_data: Dict[str, Dict[str, Dict]], is_premium: bool = False) -> List[Dict]:
        """Enhanced arbitrage calculation"""
        opportunities = []
        
        # Find common symbols across exchanges
        all_symbols = set()
        for exchange_data in all_data.values():
            if exchange_data:
                all_symbols.update(exchange_data.keys())
        
        # Filter symbols that appear in at least 2 exchanges
        common_symbols = set()
        for symbol in all_symbols:
            exchanges_with_symbol = sum(1 for exchange_data in all_data.values() if symbol in exchange_data)
            if exchanges_with_symbol >= 2:
                common_symbols.add(symbol)
        
        logger.info(f"Found {len(common_symbols)} common symbols")
        
        for symbol in common_symbols:
            # Collect all exchange data for this symbol
            exchange_data = {ex: all_data[ex][symbol] for ex in all_data if symbol in all_data[ex]}
            
            # Safety check
            is_safe, _ = self.is_symbol_safe(symbol, exchange_data) # Only check boolean here for arbitrage calculation
            if not is_safe:
                continue
            
            if len(exchange_data) >= 2:
                # Sort by price
                sorted_exchanges = sorted(exchange_data.items(), key=lambda x: x[1]['price'])
                lowest_ex, lowest_data = sorted_exchanges[0]
                highest_ex, highest_data = sorted_exchanges[-1]
                
                lowest_price = lowest_data['price']
                highest_price = highest_data['price']
                
                if lowest_price > 0:
                    profit_percent = ((highest_price - lowest_price) / lowest_price) * 100
                    
                    opportunity = {
                        'symbol': symbol,
                        'buy_exchange': lowest_ex,
                        'sell_exchange': highest_ex,
                        'buy_price': lowest_price,
                        'sell_price': highest_price,
                        'profit_percent': profit_percent,
                        'buy_volume': lowest_data.get('volume', 0),
                        'sell_volume': highest_data.get('volume', 0),
                        'avg_volume': (lowest_data.get('volume', 0) + highest_data.get('volume', 0)) / 2
                    }
                    
                    if self.validate_arbitrage_opportunity(opportunity):
                        # For free users, only show opportunities up to 2%
                        if not is_premium and opportunity['profit_percent'] > self.free_user_max_profit:
                            continue
                        opportunities.append(opportunity)
        
        return sorted(opportunities, key=lambda x: x['profit_percent'], reverse=True)
    
    def is_premium_user(self, user_id: int) -> bool:
        """Check if user is premium"""
        return user_id in self.premium_users
    
    def save_user(self, user_id: int, username: str):
        """Save user to PostgreSQL database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO users (user_id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET 
                        username = EXCLUDED.username,
                        added_date = CURRENT_TIMESTAMP
                ''', (user_id, username))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            conn.rollback()
    
    def save_arbitrage_data(self, opportunity: Dict):
        """Save arbitrage data to PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO arbitrage_data 
                    (symbol, exchange1, exchange2, price1, price2, profit_percent, volume_24h)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (
                    opportunity['symbol'],
                    opportunity['buy_exchange'],
                    opportunity['sell_exchange'],
                    opportunity['buy_price'],
                    opportunity['sell_price'],
                    opportunity['profit_percent'],
                    opportunity['avg_volume']
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving arbitrage data: {e}")
            conn.rollback()
    
    def get_premium_users_list(self) -> List[Dict]:
        """Get list of premium users from PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT user_id, username, subscription_end, added_date 
                    FROM premium_users 
                    ORDER BY added_date DESC
                ''')
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1] or 'Unknown',
                        'subscription_end': row[2],
                        'added_date': row[3]
                    } for row in results
                ]
        except Exception as e:
            logger.error(f"Error getting premium users list: {e}")
            return []

    def get_user_id_by_username(self, username: str) -> int:
        """Get user ID by username from PostgreSQL database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id FROM users WHERE username = %s', (username,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting user ID by username: {e}")
            return None

    def get_all_users(self) -> List[Dict]:
        """Get all users from PostgreSQL database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id, username FROM users')
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1] or 'Unknown'
                    } for row in results
                ]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

# Global bot instance
bot = ArbitrageBot()

# Admin user ID - set your Telegram user ID here
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))  # Replace with your user ID

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.save_user(user.id, user.username or "")
    
    is_premium = bot.is_premium_user(user.id)
    welcome_text = "🎯 Premium" if is_premium else "🔍 Free"
    
    keyboard = [
        [InlineKeyboardButton("🔍 Check Arbitrage", callback_data='check')],
        [InlineKeyboardButton("📊 Trusted Coins", callback_data='trusted')],
        [InlineKeyboardButton("💎 Premium Info", callback_data='premium')],
        [InlineKeyboardButton("ℹ️ Help", callback_data='help')]
    ]
    
    if user.id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data='admin')])
    
    await update.message.reply_text(
        f"Hello {user.first_name}! 👋\n"
        f"Welcome to the Advanced Crypto Arbitrage Bot\n\n"
        f"🔐 Account: {welcome_text}\n"
        f"📈 {len(bot.exchanges)} Exchanges Supported\n"
        f"✅ Security filters active\n"
        f"📊 Volume-based validation\n"
        f"🔍 Suspicious coin detection",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'check':
        await handle_arbitrage_check(query)
    elif query.data == 'trusted':
        await show_trusted_symbols(query)
    elif query.data == 'premium':
        await show_premium_info(query)
    elif query.data == 'help':
        await show_help(query)
    elif query.data == 'admin' and query.from_user.id == ADMIN_USER_ID:
        await show_admin_panel(query)
    elif query.data == 'list_premium' and query.from_user.id == ADMIN_USER_ID:
        await list_premium_users(query)
    elif query.data == 'back':
        await show_main_menu(query)
    elif query.data == 'activate_license':
        await show_license_activation(query)
    elif query.data == 'broadcast' and query.from_user.id == ADMIN_USER_ID:
        await ask_for_broadcast_message(query)
    elif query.data == 'cancel_broadcast' and query.from_user.id == ADMIN_USER_ID:
        await show_admin_panel(query)

async def handle_arbitrage_check(query):
    # Yüklenme mesajını göster
    await query.edit_message_text("🔄 Scanning prices across exchanges... (Security filters active)")
    
    # 3 saniye bekle
    await asyncio.sleep(3)
    
    user_id = query.from_user.id
    is_premium = bot.is_premium_user(user_id)
    
    opportunities = await bot.get_cached_arbitrage_data(is_premium)
    
    if not opportunities:
        await query.edit_message_text(
            "❌ No safe arbitrage opportunities found\n\n"
            "🔒 Security filters applied:\n"
            "• Minimum volume control ($100k+)\n"
            "• Suspicious coin detection\n"
            "• Reasonable profit ratio control\n"
            f"• Max profit shown: {bot.free_user_max_profit}%" if not is_premium else "• Full profit range available"
        )
        return
    
    text = "💎 Premium Safe Arbitrage:\n\n" if is_premium else f"🔍 Safe Arbitrage (≤{bot.free_user_max_profit}%):\n\n"
    
    max_opps = 20 if is_premium else 8
    for i, opp in enumerate(opportunities[:max_opps], 1):
        # Trusted coin indicator
        trust_icon = "✅" if opp['symbol'] in bot.trusted_symbols else "🔍"
        
        text += f"{i}. {trust_icon} {opp['symbol']}\n"
        text += f"   ⬇️ Buy: {opp['buy_exchange']} ${opp['buy_price']:.6f}\n"
        text += f"   ⬆️ Sell: {opp['sell_exchange']} ${opp['sell_price']:.6f}\n"
        text += f"   💰 Profit: {opp['profit_percent']:.2f}%\n"
        text += f"   📊 Volume: ${opp['avg_volume']:,.0f}\n\n"
        
        # Save data for premium users
        if is_premium:
            bot.save_arbitrage_data(opp)
    
    if not is_premium:
        total_opportunities = len(opportunities)
        hidden_opportunities = max(0, total_opportunities - max_opps)
        text += f"\n💎 Showing {min(max_opps, total_opportunities)} of {total_opportunities} opportunities"
        if hidden_opportunities > 0:
            text += f"\n🔒 {hidden_opportunities} more opportunities available for premium users"
        text += f"\n📈 Higher profit rates (>{bot.free_user_max_profit}%) available with premium!"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data='check')],
        [InlineKeyboardButton("📊 Trusted Coins", callback_data='trusted')],
        [InlineKeyboardButton("💎 Premium", callback_data='premium')],
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_trusted_symbols(query):
    text = "✅ **Trusted Cryptocurrencies**\n\n"
    text += "These coins are verified across all exchanges:\n\n"
    
    symbols_list = list(bot.trusted_symbols)
    symbols_list.sort()
    
    # Group symbols for better display
    for i in range(0, len(symbols_list), 3):
        group = symbols_list[i:i+3]
        text += " • ".join(group) + "\n"
    
    text += f"\n📊 Total: {len(bot.trusted_symbols)} trusted coins"
    text += "\n🔒 These symbols have additional security validation"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='back')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_main_menu(query):
    user = query.from_user
    is_premium = bot.is_premium_user(user.id)
    welcome_text = "🎯 Premium" if is_premium else "🔍 Free"
    
    keyboard = [
        [InlineKeyboardButton("🔍 Check Arbitrage", callback_data='check')],
        [InlineKeyboardButton("📊 Trusted Coins", callback_data='trusted')],
        [InlineKeyboardButton("💎 Premium Info", callback_data='premium')],
        [InlineKeyboardButton("ℹ️ Help", callback_data='help')]
    ]
    
    if user.id == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data='admin')])
    
    await query.edit_message_text(
        f"Hello {user.first_name}! 👋\n"
        f"Welcome to the Advanced Crypto Arbitrage Bot\n\n"
        f"🔐 Account: {welcome_text}\n"
        f"📈 {len(bot.exchanges)} Exchanges Supported\n"
        f"✅ Security filters active\n"
        f"📊 Volume-based validation\n"
        f"🔍 Suspicious coin detection",
        reply_markup=InlineKeyboardMarkup(keyboard))
    )

async def show_license_activation(query):
    text = """🔑 **License Key Activation**

Enter your Gumroad license key to activate premium subscription.

📝 **How to get your license key:**
1. Purchase premium subscription from Gumroad
2. Check your email for the license key
3. Copy and paste the key here

💡 **Format:** 6F0E4C97-B72A4E69-A11BF6C4-AF6517E7 (SAMPLE)

Please send your license key as a message."""
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='premium')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_license_activation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle license key messages"""
    user = update.effective_user
    license_key = update.message.text.strip()
    
    # Debug: License key formatını kontrol et
    logger.info(f"Received license key from user {user.id}: '{license_key}'")
    logger.info(f"License key length: {len(license_key)}")
    
    # License key format kontrolü (Gumroad format: XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX)
    if not license_key or len(license_key) < 10:
        logger.info("License key too short, ignoring")
        return  # Not a license key, ignore
    
    # Daha detaylı format kontrolü
    if not any(c.isalnum() for c in license_key):
        logger.info("License key contains no alphanumeric characters, ignoring")
        return
    
    await update.message.reply_text("🔄 Verifying license key...")
    
    # Check if already used
    if license_key in bot.used_license_keys:
        await update.message.reply_text("❌ This license key has already been used.")
        return
    
    # Verify with Gumroad
    verification_result = await bot.verify_gumroad_license(license_key)
    
    logger.info(f"Verification result: {verification_result}")
    
    if not verification_result.get('success', False):
        error_msg = verification_result.get('error', 'Unknown error')
        await update.message.reply_text(
            f"❌ License verification failed.\n\n"
            f"Error: {error_msg}\n\n"
            f"Please check:\n"
            f"• Key is correct (copy-paste recommended)\n"
            f"• Key hasn't been used before\n"
            f"• Purchase was successful\n\n"
            f"Contact support: {SUPPORT_USERNAME}"
        )
        return
    
    # Activate license
    bot.activate_license_key(
        license_key, 
        user.id, 
        user.username or "", 
        verification_result.get('purchase', {})
    )
    
    await update.message.reply_text(
        "✅ **License Activated Successfully!**\n\n"
        "🎉 Welcome to Premium Membership!\n"
        "📅 Valid for: 30 days\n"
        "💎 All premium features are now active\n\n"
        "Use /start to see your premium status!"
    )

async def show_premium_info(query):
    user_id = query.from_user.id
    is_premium = bot.is_premium_user(user_id)
    
    if is_premium:
        text = """💎 **Premium Member Benefits**
        
✅ **Active Premium Features:**
- Unlimited arbitrage scanning
- Full profit range display (up to 20%)
- Access to all exchanges data
- Advanced security filters
- Volume-based validation
- Historical data storage
- Priority support
- **📈 Specific Coin Price Analysis with Safety Check**

📊 **Statistics:**
- {} exchanges monitored
- {} trusted cryptocurrencies
- Real-time price monitoring

🔄 **Your subscription is active**

📞 **Support:** {}""".format(len(bot.exchanges), len(bot.trusted_symbols), SUPPORT_USERNAME)
    else:
        text = """💎 **Premium Membership Benefits**

🆓 **Free Account Limitations:**
- Max 2% profit rate display
- Limited opportunities shown
- Basic security filters
- **🚫 Specific Coin Price Analysis not available**

💎 **Premium Benefits:**
- Full profit range (up to 20%)
- Unlimited opportunities
- {} exchanges access
- {} trusted coins validation
- Advanced security filters
- Volume analysis
- Historical data
- Priority support
- **📈 Specific Coin Price Analysis with Safety Check**

💰 **Get Premium Access:**
🛒 Purchase subscription below

📞 **Support:** {}""".format(len(bot.exchanges), len(bot.trusted_symbols), SUPPORT_USERNAME)
    
    if is_premium:
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='back')]]
    else:
        keyboard = [
            [InlineKeyboardButton("💎 Buy Premium", url=GUMROAD_LINK)],
            [InlineKeyboardButton("🔑 Activate License", callback_data='activate_license')],
            [InlineKeyboardButton("🔙 Back", callback_data='back')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def start_background_tasks(app):
    """Background task'ları başlat"""
    asyncio.create_task(bot.cache_refresh_task())

async def show_help(query):
    text = """ℹ️ **Bot Usage Guide**

🔍 **Main Features:**
• Real-time arbitrage scanning
• {} exchanges supported
• Security filters active
• Volume-based validation
• **📈 Specific Coin Price Analysis (Premium)**

📋 **Commands:**
/start - Start the bot
/check - Quick arbitrage scan
/premium - Premium information
/help - Show this help
/price <symbol> - Check specific coin price (Premium)

🔒 **Security Features:**
• Suspicious coin detection
• Volume threshold filtering
• Price ratio validation
• Trusted symbols priority

📊 **Data Sources:**
Multiple cryptocurrency exchanges with real-time price feeds

📞 **Support:** {}""".format(len(bot.exchanges), SUPPORT_USERNAME)
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data='back')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_admin_panel(query):
    text = """👑 **Admin Panel**
    
📊 **Statistics:**
• Total premium users: {}
• Total exchanges: {}
• Trusted symbols: {}

🛠️ **Available Commands:**
• /addpremium <user_id> [days] - Add premium user
• /removepremium <user_id> - Remove premium user
• /listpremium - List all premium users
• /stats - Bot statistics
• /admincheck - Admin arbitrage check (Huobi excluded, 40% max profit)

📋 **Quick Actions:**""".format(
        len(bot.premium_users), 
        len(bot.exchanges), 
        len(bot.trusted_symbols)
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 List Premium Users", callback_data='list_premium')],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data='broadcast')],
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def list_premium_users(query):
    users = bot.get_premium_users_list()
    
    if not users:
        text = "📋 **Premium Users List**\n\nNo premium users found."
    else:
        text = f"📋 **Premium Users List** ({len(users)} users)\n\n"
        for i, user in enumerate(users[:20], 1):  # Show max 20 users
            text += f"{i}. **{user['username']}** (ID: {user['user_id']})\n"
            text += f"   └ Until: {user['subscription_end']}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data='list_premium')],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Admin Commands
async def remove_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /removepremium <user_id_or_username>\n"
            "Example: /removepremium 123456789\n"
            "Example: /removepremium @username"
        )
        return
    
    try:
        user_input = context.args[0]
        
        if user_input.isdigit():
            # User ID
            user_id = int(user_input)
            bot.remove_premium_user(user_id)
            await update.message.reply_text(f"✅ User {user_id} removed from premium.")
        else:
            # Username
            username = user_input.replace('@', '')
            user_id = await get_user_id_by_username(username)
            
            if user_id:
                bot.remove_premium_user(user_id)
                await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) removed from premium.")
            else:
                await update.message.reply_text(f"❌ User @{username} not found in database.")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Use numbers only.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /addpremium <user_id_or_username> [days]\n"
            "Example: /addpremium 123456789 30\n"
            "Example: /addpremium @username 30\n"
            "Example: /addpremium username 30"
        )
        return
    
    try:
        user_input = context.args[0]
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        # Kullanıcı ID mi username mi kontrol et
        if user_input.isdigit():
            # User ID
            user_id = int(user_input)
            bot.add_premium_user(user_id, "", days)
            await update.message.reply_text(f"✅ User {user_id} added as premium for {days} days.")
        else:
            # Username
            username = user_input.replace('@', '')  # @ işaretini kaldır
            user_id = await get_user_id_by_username(username)
            
            if user_id:
                bot.add_premium_user(user_id, username, days)
                await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) added as premium for {days} days.")
            else:
                await update.message.reply_text(f"❌ User @{username} not found in database. User must start the bot first.")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid days parameter. Use numbers only for days.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def get_user_id_by_username(username: str) -> int:
    """Get user ID by username from PostgreSQL database"""
    return bot.get_user_id_by_username(username)

async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    users = bot.get_premium_users_list()
    
    if not users:
        await update.message.reply_text("📋 No premium users found.")
        return
    
    text = f"📋 **Premium Users** ({len(users)} total)\n\n"
    for i, user in enumerate(users[:30], 1):
        text += f"{i}. {user['username']} (ID: {user['user_id']})\n"
        text += f"   Until: {user['subscription_end']}\n\n"
    
    if len(users) > 30:
        text += f"... and {len(users) - 30} more users"
    
    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    conn = bot.get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get total users
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Get arbitrage data count
            cursor.execute('SELECT COUNT(*) FROM arbitrage_data')
            total_arbitrage_records = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error fetching stats from database: {e}")
        total_users = 0
        total_arbitrage_records = 0
    
    text = f"""📊 **Bot Statistics**

👥 **Users:**
• Total users: {total_users}
• Premium users: {len(bot.premium_users)}
• Free users: {total_users - len(bot.premium_users)}

📈 **Data:**
• Exchanges monitored: {len(bot.exchanges)}
• Trusted symbols: {len(bot.trusted_symbols)}
• Arbitrage records: {total_arbitrage_records}

🔒 **Security:**
• Volume threshold: ${bot.min_volume_threshold:,}
• Max profit threshold: {bot.max_profit_threshold}%
• Free user limit: {bot.free_user_max_profit}%

⚡ **System:**
• Bot status: Active
• Database: Connected"""
    
    await update.message.reply_text(text)

async def admin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sadece adminler için Huobi hariç ve %40 limitli arbitraj kontrolü"""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    user = update.effective_user
    bot.save_user(user.id, user.username or "")
    
    msg = await update.message.reply_text("🔍 [ADMIN] Scanning exchanges (Huobi excluded, 40% max profit)...")
    
    await asyncio.sleep(3)
    
    opportunities = await bot.get_admin_arbitrage_data()
    
    if not opportunities:
        await msg.edit_text("❌ No arbitrage opportunities found (Huobi excluded, max 40% profit).")
        return
    
    text = "💎 **Admin Arbitrage (Huobi Excluded, Max 40% Profit)**\n\n"
    
    for i, opp in enumerate(opportunities[:20], 1):  # Max 20 fırsat göster
        trust_icon = "✅" if opp['symbol'] in bot.trusted_symbols else "🔍"
        text += f"{i}. {trust_icon} {opp['symbol']}\n"
        text += f"   ⬇️ Buy: {opp['buy_exchange']} ${opp['buy_price']:.6f}\n"
        text += f"   ⬆️ Sell: {opp['sell_exchange']} ${opp['sell_price']:.6f}\n"
        text += f"   💰 Profit: {opp['profit_percent']:.2f}%\n"
        text += f"   📊 Volume: ${opp['avg_volume']:,.0f}\n\n"
        
        # Veriyi kaydet
        bot.save_arbitrage_data(opp)
    
    await msg.edit_text(text)

async def price_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    is_premium = bot.is_premium_user(user_id)
    is_admin = (user_id == ADMIN_USER_ID)

    if not is_premium and not is_admin:
        await update.message.reply_text(
            "🔒 This feature is for **Premium Users Only**.\n\n"
            "💎 Upgrade to Premium to access: \n"
            "• Specific Coin Price Analysis with Safety Check\n"
            "• Unlimited Arbitrage Scanning\n"
            "• And much more!\n\n"
            "Use /premium for more info."
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: /price <SYMBOL>\nExample: /price BTCUSDT")
        return

    symbol_to_check = context.args[0].upper()
    
    msg = await update.message.reply_text(f"🔄 Fetching data and analyzing safety for **{symbol_to_check}**...")

    try:
        # Fetch all exchange data first
        all_exchange_data = await bot.get_all_prices_with_volume()

        # Extract data for the specific symbol across all exchanges for safety check
        symbol_specific_exchange_data = {}
        for exchange_name, data_for_exchange in all_exchange_data.items():
            normalized_symbol = bot.normalize_symbol(symbol_to_check, exchange_name)
            if normalized_symbol in data_for_exchange:
                symbol_specific_exchange_data[exchange_name] = data_for_exchange[normalized_symbol]

        # Perform security filter check using the extracted symbol-specific data
        is_safe, safety_reason = bot.is_symbol_safe(symbol_to_check, symbol_specific_exchange_data)

        safety_text = f"🛡️ **Security Check for {symbol_to_check}:**\n{safety_reason}\n\n"

        if not is_safe:
            await msg.edit_text(f"❌ Security check failed for **{symbol_to_check}**.\n\n{safety_text}")
            return

        # If safe, proceed to fetch and display prices
        found_prices = []
        for exchange_name, data_for_exchange in symbol_specific_exchange_data.items():
            price = data_for_exchange['price']
            if price > 0: # Only include valid prices
                found_prices.append((exchange_name, price))
        
        if not found_prices:
            await msg.edit_text(f"❌ **{symbol_to_check}** not found on any monitored exchange, or prices are unavailable.\n\n{safety_text}")
            return

        text = f"📈 **{symbol_to_check} Prices Across Exchanges**\n\n"
        
        # Display prices from cheapest to most expensive
        found_prices.sort(key=lambda x: x[1]) # Re-sort to ensure cheapest-to-expensive order
        for exchange, price in found_prices:
            text += f"• {exchange.capitalize()}: `${price:.6f}`\n"
        
        # Calculate and display price difference
        cheapest_exchange, cheapest_price = found_prices[0]
        most_expensive_exchange, most_expensive_price = found_prices[-1]
        
        price_difference = most_expensive_price - cheapest_price
        
        if cheapest_price > 0:
            percentage_difference = (price_difference / cheapest_price) * 100
            text += f"\nLowest Price: {cheapest_exchange.capitalize()} `${cheapest_price:.6f}`\n"
            text += f"Highest Price: {most_expensive_exchange.capitalize()} `${most_expensive_price:.6f}`\n"
            text += f"Absolute Difference: `${price_difference:.6f}`\n"
            text += f"Percentage Difference: `{percentage_difference:.2f}%`\n\n"
        else:
             text += "\nCould not calculate percentage difference (cheapest price is zero).\n\n"

        text += safety_text # Add safety text at the end

        await msg.edit_text(text)

    except Exception as e:
        logger.error(f"Error in price_check_command for {symbol_to_check}: {e}")
        await msg.edit_text(f"❌ An error occurred while fetching prices for **{symbol_to_check}**.")

# Quick check command
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.save_user(user.id, user.username or "")
    
    msg = await update.message.reply_text("🔄 Scanning arbitrage opportunities...")
    
    # 3 saniye bekle
    await asyncio.sleep(3)
    
    all_data = await bot.get_all_prices_with_volume()
    is_premium = bot.is_premium_user(user.id)
    
    opportunities = bot.calculate_arbitrage(all_data, is_premium)
    
    if not opportunities:
        await msg.edit_text("❌ No safe arbitrage opportunities found at the moment.")
        return
    
    text = f"🔍 Quick Arbitrage Scan Results:\n\n"
    
    max_opps = 10 if is_premium else 5
    for i, opp in enumerate(opportunities[:max_opps], 1):
        trust_icon = "✅" if opp['symbol'] in bot.trusted_symbols else "🔍"
        text += f"{i}. {trust_icon} {opp['symbol']}\n"
        text += f"   💰 {opp['profit_percent']:.2f}% profit\n"
        text += f"   📊 ${opp['avg_volume']:,.0f} volume\n\n"
    
    if not is_premium and len(opportunities) > max_opps:
        text += f"💎 {len(opportunities) - max_opps} more opportunities available with premium!"
    
    await msg.edit_text(text)

# Broadcast message functions
async def ask_for_broadcast_message(query):
    """Ask admin to enter the broadcast message"""
    text = """📢 **Broadcast Message to All Users**

Please enter the message you want to send to all users.

⚠️ **Note:** This will be sent to all users in the database.

You can include formatting like:
- *Bold text*
- _Italic text_
- `Code blocks`
- [Links](https://example.com)"""
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='cancel_broadcast')]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    # Set a flag in context to indicate we're waiting for a broadcast message
    return 'waiting_for_broadcast'

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the actual broadcast message sending"""
    if update.effective_user.id != ADMIN_USER_ID:
        return
    
    message_text = update.message.text
    users = bot.get_all_users()
    
    if not users:
        await update.message.reply_text("❌ No users found in database.")
        return
    
    total_users = len(users)
    await update.message.reply_text(f"📢 Starting broadcast to {total_users} users...")
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user['user_id'],
                text=f"📢 **Announcement from Admin**\n\n{message_text}",
                parse_mode='Markdown'
            )
            success_count += 1
            # Small delay to avoid hitting rate limits
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Failed to send broadcast to user {user['user_id']}: {e}")
            fail_count += 1
    
    await update.message.reply_text(
        f"✅ Broadcast completed!\n\n"
        f"• Successfully sent: {success_count}\n"
        f"• Failed to send: {fail_count}\n\n"
        f"Total users: {total_users}"
    )

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not found!")
        return
    
    # Set admin user ID from environment
    global ADMIN_USER_ID
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
    
    if ADMIN_USER_ID == 0:
        logger.warning("ADMIN_USER_ID not set! Admin commands will not work.")
    
    app = Application.builder().token(TOKEN).build()

    app.post_init = start_background_tasks
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("addpremium", add_premium_command))
    app.add_handler(CommandHandler("removepremium", remove_premium_command))
    app.add_handler(CommandHandler("listpremium", list_premium_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("admincheck", admin_check_command))
    app.add_handler(CommandHandler("price", price_check_command)) # Yeni komut handler'ı
    
    # Message handlers (command handlers'dan sonra)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_license_activation))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_USER_ID), handle_broadcast_message))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(button_handler))

    async def cleanup():
        if bot.session and not bot.session.closed:
            await bot.session.close()
        if bot.conn and not bot.conn.closed: # Add this line for PostgreSQL connection
            bot.conn.close()                 # Add this line
            logger.info("PostgreSQL database connection closed.") # Add this line
    
    app.post_stop = cleanup
    
    app.run_polling()
    
    logger.info("Advanced Arbitrage Bot starting...")
    logger.info(f"Monitoring {len(bot.exchanges)} exchanges")
    logger.info(f"Tracking {len(bot.trusted_symbols)} trusted symbols")
    logger.info(f"Premium users loaded: {len(bot.premium_users)}")

if __name__ == '__main__':
    main()
