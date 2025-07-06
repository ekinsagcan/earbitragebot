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
                # users tablosu
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY, -- Use BIGINT for user_id
                        username TEXT,
                        subscription_end DATE,
                        is_premium BOOLEAN DEFAULT FALSE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        referrer_user_id BIGINT DEFAULT NULL -- Yeni eklenen kolon
                    )
                ''')
                # referrer_user_id kolonu zaten varsa eklemeye çalışırken hata almamak için ALTER TABLE IF NOT EXISTS kullanıyoruz
                cursor.execute('''
                    DO $$ BEGIN
                        ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_user_id BIGINT DEFAULT NULL;
                    END $$;
                ''')

                # arbitrage_data tablosu
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
                # premium_users tablosu
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        added_by_admin BOOLEAN DEFAULT TRUE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        subscription_end DATE
                    )
                ''')
                # license_keys tablosu
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS license_keys (
                         license_key TEXT PRIMARY KEY,
                         user_id BIGINT,
                         username TEXT,
                         used_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         gumroad_sale_id TEXT
                    )
                ''')
                # influencers tablosu (Yeni)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS influencers (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT UNIQUE, -- Influencer bot kullanıcısı ise user_id'si
                        affiliate_code TEXT UNIQUE NOT NULL, -- Benzersiz affiliate kodu
                        name TEXT NOT NULL, -- Influencer'ın adı/etiketi
                        referred_users_count INTEGER DEFAULT 0, -- Bu linkten gelen toplam kullanıcı
                        activated_licenses_count INTEGER DEFAULT 0, -- Bu linkten aktif edilen lisans sayısı
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            conn.commit()
            logger.info("PostgreSQL tables initialized or already exist, and schema updated.")
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

                # If this user was referred by an influencer, increment their activated_licenses_count
                cursor.execute("SELECT referrer_user_id FROM users WHERE user_id = %s", (user_id,))
                referrer_id = cursor.fetchone()
                if referrer_id and referrer_id[0]:
                    cursor.execute('''
                        UPDATE influencers
                        SET activated_licenses_count = activated_licenses_count + 1
                        WHERE user_id = %s
                    ''', (referrer_id[0],))
                
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
            if min_vol > 0 and max_vol > min_vol * 100: # 100x difference is suspicious
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
        if price_ratio > 1.3: # More than 30% difference is suspicious
            return False
        # 3. Minimum profit threshold
        if opportunity['profit_percent'] < 0.1: # Less than 0.1% profit is meaningless
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

    def save_user(self, user_id: int, username: str, referrer_user_id: int = None):
        """Save user to PostgreSQL database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO users (user_id, username, referrer_user_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET 
                        username = EXCLUDED.username,
                        added_date = CURRENT_TIMESTAMP,
                        referrer_user_id = COALESCE(users.referrer_user_id, EXCLUDED.referrer_user_id)
                ''', (user_id, username, referrer_user_id))
                
                # If a referrer exists, increment referred_users_count for that influencer
                if referrer_user_id:
                    cursor.execute('''
                        UPDATE influencers
                        SET referred_users_count = referred_users_count + 1
                        WHERE user_id = %s
                    ''', (referrer_user_id,))

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
                    INSERT INTO arbitrage_data (symbol, exchange1, exchange2, price1, price2, profit_percent, volume_24h)
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
                premium_users_list = []
                for row in results:
                    premium_users_list.append({
                        'user_id': row[0],
                        'username': row[1] if row[1] else "N/A",
                        'subscription_end': row[2].strftime('%Y-%m-%d') if row[2] else "N/A",
                        'added_date': row[3].strftime('%Y-%m-%d %H:%M:%S')
                    })
                return premium_users_list
        except Exception as e:
            logger.error(f"Error getting premium users list: {e}")
            return []

    # New methods for affiliate system
    def create_affiliate_code(self, influencer_name: str, user_id: int = None) -> str:
        """Creates a unique affiliate code for an influencer and saves it to the database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Generate a simple unique code (e.g., from name + timestamp, or a UUID)
                # For simplicity, let's use a hashed version of influencer_name + current timestamp
                import hashlib
                unique_string = f"{influencer_name}-{time.time()}-{os.urandom(4).hex()}"
                affiliate_code = hashlib.sha256(unique_string.encode()).hexdigest()[:12] # Take first 12 chars

                cursor.execute('''
                    INSERT INTO influencers (user_id, affiliate_code, name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (affiliate_code) DO NOTHING; -- Ensure uniqueness
                ''', (user_id, affiliate_code, influencer_name))
                conn.commit()
                logger.info(f"Created affiliate code {affiliate_code} for {influencer_name}.")
                return affiliate_code
        except Exception as e:
            logger.error(f"Error creating affiliate code: {e}")
            conn.rollback()
            return None

    def get_influencer_by_code(self, affiliate_code: str) -> Dict:
        """Retrieves influencer details by affiliate code."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, user_id, affiliate_code, name, referred_users_count, activated_licenses_count FROM influencers WHERE affiliate_code = %s",
                    (affiliate_code,)
                )
                result = cursor.fetchone()
                if result:
                    return {
                        "id": result[0],
                        "user_id": result[1],
                        "affiliate_code": result[2],
                        "name": result[3],
                        "referred_users_count": result[4],
                        "activated_licenses_count": result[5]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting influencer by code: {e}")
            return None

    def get_all_influencers(self) -> List[Dict]:
        """Retrieves all influencers and their stats."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, user_id, affiliate_code, name, referred_users_count, activated_licenses_count FROM influencers ORDER BY created_at DESC"
                )
                results = cursor.fetchall()
                influencers_list = []
                for row in results:
                    influencers_list.append({
                        "id": row[0],
                        "user_id": row[1],
                        "affiliate_code": row[2],
                        "name": row[3],
                        "referred_users_count": row[4],
                        "activated_licenses_count": row[5]
                    })
                return influencers_list
        except Exception as e:
            logger.error(f"Error getting all influencers: {e}")
            return []

    # New methods for sending messages to user groups
    def get_all_user_ids(self) -> List[int]:
        """Retrieves all user IDs from the database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM users")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting all user IDs: {e}")
            return []

    def get_free_user_ids(self) -> List[int]:
        """Retrieves free user IDs from the database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Assuming is_premium is correctly updated for premium users
                cursor.execute("""
                    SELECT u.user_id 
                    FROM users u 
                    LEFT JOIN premium_users p ON u.user_id = p.user_id 
                    WHERE p.user_id IS NULL OR p.subscription_end < CURRENT_DATE
                """)
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting free user IDs: {e}")
            return []

    def get_premium_user_ids(self) -> List[int]:
        """Retrieves premium user IDs from the database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM premium_users WHERE subscription_end >= CURRENT_DATE")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting premium user IDs: {e}")
            return []

    def get_user_id_by_username(self, username: str) -> int:
        """Retrieves a user ID by their username."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting user ID by username: {e}")
            return None

    # New methods for detailed statistics
    def get_detailed_stats(self) -> Dict:
        """Retrieves detailed statistics for the admin panel."""
        conn = self.get_db_connection()
        stats = {
            "total_users": 0,
            "premium_users_count": 0,
            "free_users_count": 0,
            "total_licenses_activated": 0,
            "most_active_users": []
        }
        try:
            with conn.cursor() as cursor:
                # Total users
                cursor.execute("SELECT COUNT(*) FROM users")
                stats["total_users"] = cursor.fetchone()[0]

                # Premium users count
                cursor.execute("SELECT COUNT(*) FROM premium_users WHERE subscription_end >= CURRENT_DATE")
                stats["premium_users_count"] = cursor.fetchone()[0]

                # Free users count
                stats["free_users_count"] = stats["total_users"] - stats["premium_users_count"]

                # Total licenses activated
                cursor.execute("SELECT COUNT(*) FROM license_keys")
                stats["total_licenses_activated"] = cursor.fetchone()[0]

                # Most active users (this needs more sophisticated tracking,
                # for now, let's assume 'users' table's added_date could be a proxy,
                # or if you track command usage, you'd query that table)
                # For a more accurate "active user" metric, you'd need to log
                # user interactions/command usage and query that.
                # As a placeholder, we can just get users sorted by their last interaction
                # (which isn't explicitly stored in the current schema for all users).
                # Let's just fetch the 10 most recent users for now, as "most active"
                # would require more complex logging.
                cursor.execute("""
                    SELECT user_id, username, added_date
                    FROM users
                    ORDER BY added_date DESC
                    LIMIT 10
                """)
                most_recent_users = cursor.fetchall()
                stats["most_active_users"] = [{
                    "user_id": row[0],
                    "username": row[1],
                    "last_active": row[2].strftime('%Y-%m-%d %H:%M:%S')
                } for row in most_recent_users]

            return stats
        except Exception as e:
            logger.error(f"Error getting detailed stats: {e}")
            return stats


# Telegram Bot handlers (these will call methods from ArbitrageBot class)

ADMIN_IDS = [int(admin_id) for admin_id in os.getenv("ADMIN_IDS", "").split(',') if admin_id]

async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_instance = context.bot_data['arbitrage_bot']
    username = user.username if user.username else f"id_{user.id}"

    # Check for affiliate code in /start payload
    affiliate_code = None
    if context.args:
        start_payload = context.args[0]
        # Basic check for affiliate link format. E.g., t.me/yourbot?start=AFF_CODE
        # Here we assume the whole argument is the affiliate code.
        affiliate_code = start_payload

    referrer_user_id = None
    if affiliate_code:
        influencer = bot_instance.get_influencer_by_code(affiliate_code)
        if influencer:
            referrer_user_id = influencer.get("user_id") # Use influencer's bot user_id if available
            # We don't increment referred_users_count here directly,
            # it's handled in save_user.

    bot_instance.save_user(user.id, username, referrer_user_id) # Pass referrer_user_id to save_user

    await update.message.reply_html(
        f"Merhaba {user.mention_html()}! Ben Arbitrage Botunuz. Size en güncel arbitraj fırsatlarını bulmanıza yardımcı olabilirim.\n\n"
        "Arbitraj fırsatlarını görmek için /arbitraj yazın.\n"
        "Premium üyelik hakkında bilgi almak için /premium yazın.\n"
        "Destek için: {SUPPORT_USERNAME}".format(SUPPORT_USERNAME=SUPPORT_USERNAME)
    )

async def arbitrage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot_instance = context.bot_data['arbitrage_bot']
    is_premium = bot_instance.is_premium_user(user_id)
    
    if is_premium or await is_admin(user_id):
        data_to_display = await bot_instance.get_admin_arbitrage_data(is_premium=True) if await is_admin(user_id) else await bot_instance.get_cached_arbitrage_data(is_premium=True)
    else:
        data_to_display = await bot_instance.get_cached_arbitrage_data(is_premium=False)

    message = "Güncel Arbitraj Fırsatları:\n\n"
    if data_to_display:
        for opp in data_to_display[:10]: # Max 10 fırsat göster
            message += (
                f"📈 Sembol: {opp['symbol']}\n"
                f"💰 Kar Oranı: {opp['profit_percent']:.2f}%\n"
                f"➡️ Alış Borsası: {opp['buy_exchange']} ({opp['buy_price']:.8f})\n"
                f"⬅️ Satış Borsası: {opp['sell_exchange']} ({opp['sell_price']:.8f})\n"
                f"💧 Ortalama Hacim: ${opp['avg_volume']:.2f}\n"
                f"📊 Güvenlik Durumu: {bot_instance.is_symbol_safe(opp['symbol'], opp.get('exchange_data', {}))[1]}\n\n" # is_symbol_safe'den mesajı al
            )
    else:
        message += "Şu an için aktif arbitraj fırsatı bulunmamaktadır."
    
    await update.message.reply_text(message)

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        f"Premium üyelik ile botun tüm özelliklerine erişebilir, daha fazla arbitraj fırsatı görebilirsiniz.\n\n"
        f"Premium üyelik almak için: {GUMROAD_LINK}\n\n"
        f"Lisans anahtarınızı aktifleştirmek için bot'a anahtarınızı direkt mesaj olarak gönderin.\n\n"
        f"Herhangi bir sorunuz olursa {SUPPORT_USERNAME} ile iletişime geçebilirsiniz."
    )
    await update.message.reply_text(message)

async def admin_add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Kullanım: /addpremium <user_id> [days] [username]")
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        username = context.args[2] if len(context.args) > 2 else ""

        bot_instance = context.bot_data['arbitrage_bot']
        bot_instance.add_premium_user(user_id, username, days)
        await update.message.reply_text(f"Kullanıcı {user_id} (@{username if username else 'N/A'}) {days} günlüğüne premium olarak eklendi.")
    except ValueError:
        await update.message.reply_text("Geçersiz kullanıcı ID'si veya gün sayısı.")
    except Exception as e:
        await update.message.reply_text(f"Premium eklenirken hata oluştu: {e}")

async def admin_remove_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Kullanım: /removepremium <user_id>")
        return

    try:
        user_id = int(context.args[0])
        bot_instance = context.bot_data['arbitrage_bot']
        bot_instance.remove_premium_user(user_id)
        await update.message.reply_text(f"Kullanıcı {user_id} premiumluktan çıkarıldı.")
    except ValueError:
        await update.message.reply_text("Geçersiz kullanıcı ID'si.")
    except Exception as e:
        await update.message.reply_text(f"Premium çıkarılırken hata oluştu: {e}")

async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    bot_instance = context.bot_data['arbitrage_bot']
    premium_users = bot_instance.get_premium_users_list()

    if not premium_users:
        await update.message.reply_text("Henüz premium kullanıcı bulunmamaktadır.")
        return

    message = "Premium Kullanıcılar:\n\n"
    for user_data in premium_users:
        message += (
            f"ID: {user_data['user_id']} | "
            f"Kullanıcı Adı: {user_data['username']} | "
            f"Bitiş Tarihi: {user_data['subscription_end']}\n"
        )
    
    # Split message if too long
    if len(message) > 4096:
        for i in range(0, len(message), 4096):
            await update.message.reply_text(message[i:i+4096])
    else:
        await update.message.reply_text(message)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    bot_instance = context.bot_data['arbitrage_bot']
    stats = bot_instance.stats
    
    # Get total users for a more complete picture
    conn = bot_instance.get_db_connection()
    total_users = 0
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error fetching total users for stats: {e}")

    message = (
        f"Bot İstatistikleri:\n"
        f"Cache İsabetleri: {stats['cache_hits']}\n"
        f"Cache Kaçakları: {stats['cache_misses']}\n"
        f"API İstekleri: {stats['api_requests']}\n"
        f"Eşzamanlı Kullanıcılar: {stats['concurrent_users']}\n"
        f"Toplam Kayıtlı Kullanıcı: {total_users}\n"
        f"Premium Kullanıcılar: {len(bot_instance.premium_users)}\n"
        f"Kullanılan Lisans Anahtarları: {len(bot_instance.used_license_keys)}\n"
    )
    await update.message.reply_text(message)

async def admin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await is_admin(update.effective_user.id):
        await update.message.reply_text("Evet, sen bir adminsin!")
    else:
        await update.message.reply_text("Hayır, sen bir admin değilsin.")

async def price_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Lütfen kontrol etmek istediğiniz sembolü belirtin. Örnek: /price BTCUSDT")
        return

    symbol = context.args[0].upper()
    bot_instance = context.bot_data['arbitrage_bot']
    
    await update.message.reply_text(f"{symbol} için fiyatlar kontrol ediliyor...")

    prices = await bot_instance.get_specific_symbol_prices(symbol)

    if not prices:
        await update.message.reply_text(f"Maalesef {symbol} için fiyat bilgisi bulunamadı veya işlem hacmi yetersiz.")
        return

    message = f"📊 {symbol} Fiyatları (En ucuzdan en pahalıya):\n"
    for exchange_name, price in prices:
        message += f"- {exchange_name.capitalize()}: {price:.8f}\n"

    # Add safety check info
    # To get full exchange_data for is_symbol_safe, we might need a separate fetch or pass more data.
    # For now, let's just indicate basic safety if we have the symbol in trusted list.
    is_safe, safety_message = bot_instance.is_symbol_safe(symbol, await bot_instance.get_all_prices_with_volume())
    message += f"\nGüvenlik Durumu: {safety_message}"

    await update.message.reply_text(message)

async def handle_license_activation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username if update.effective_user.username else f"id_{user_id}"
    license_key = update.message.text.strip()
    bot_instance = context.bot_data['arbitrage_bot']

    # Prevent command processing as license key
    if license_key.startswith('/'):
        return # This is a command, ignore

    if license_key in bot_instance.used_license_keys:
        await update.message.reply_text(
            "Bu lisans anahtarı zaten kullanılmış. Lütfen geçerli bir anahtar girin veya destek ile iletişime geçin."
        )
        return

    await update.message.reply_text("Lisans anahtarınız doğrulanıyor, lütfen bekleyin...")
    
    verification_result = await bot_instance.verify_gumroad_license(license_key)

    if verification_result.get('success'):
        sale = verification_result.get('sale')
        if sale and sale.get('product_id') == GUMROAD_PRODUCT_ID:
            bot_instance.activate_license_key(license_key, user_id, username, sale)
            await update.message.reply_text(
                "Tebrikler! Lisans anahtarınız başarıyla aktifleştirildi. Artık premium özelliklere erişebilirsiniz."
            )
        else:
            await update.message.reply_text(
                "Lisans anahtarınız geçerli ancak bu botun ürünüyle eşleşmiyor. Lütfen doğru ürüne ait bir anahtar girin."
            )
    else:
        error_message = verification_result.get('error', 'Bilinmeyen bir hata oluştu.')
        await update.message.reply_text(
            f"Lisans anahtarı doğrulanamadı: {error_message}. Lütfen anahtarınızı kontrol edin veya destek ile iletişime geçin."
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # Always answer the callback query
    
    # Handle button clicks
    # Currently, there are no inline buttons implemented.
    # This function is a placeholder for future use.
    
    # Example: If you had a button with callback_data="show_more_stats"
    # if query.data == "show_more_stats":
    #     await query.edit_message_text(text="Here are more stats...")

def main() -> None:
    """Run the bot."""
    # Create the Application and pass your bot's token.
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Pass the ArbitrageBot instance to the handlers
    arbitrage_bot_instance = ArbitrageBot()
    application.bot_data['arbitrage_bot'] = arbitrage_bot_instance

    # Run background cache refresh task
    application.job_queue.run_once(lambda context: asyncio.create_task(arbitrage_bot_instance.cache_refresh_task()), 1)

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("arbitraj", arbitrage_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("addpremium", admin_add_premium_command))
    application.add_handler(CommandHandler("removepremium", admin_remove_premium_command))
    application.add_handler(CommandHandler("listpremium", list_premium_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("admincheck", admin_check_command))
    application.add_handler(CommandHandler("price", price_check_command)) # Yeni komut handler'ı
    
    # New admin commands
    application.add_handler(CommandHandler("sendmessage", send_message_command))
    application.add_handler(CommandHandler("detailedstats", detailed_stats_command))
    application.add_handler(CommandHandler("createaffiliate", create_affiliate_command))
    application.add_handler(CommandHandler("affiliatereport", affiliate_report_command))


    # Message handlers (command handlers'dan sonra)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_license_activation))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_handler))

    async def cleanup():
        if arbitrage_bot_instance.session and not arbitrage_bot_instance.session.closed:
            await arbitrage_bot_instance.session.close()
        if arbitrage_bot_instance.conn and not arbitrage_bot_instance.conn.closed: # Add this line for PostgreSQL connection
            arbitrage_bot_instance.conn.close()                 # Add this line
            logger.info("PostgreSQL database connection closed.") # Add this line
    
    application.post_stop = cleanup
    
    application.run_polling()
    
    logger.info("Advanced Arbitrage Bot starting...")
    logger.info(f"Monitoring {len(arbitrage_bot_instance.exchanges)} exchanges")
    logger.info(f"Tracking {len(arbitrage_bot_instance.trusted_symbols)} trusted symbols")
    logger.info(f"Premium users loaded: {len(arbitrage_bot_instance.premium_users)}")
    
    # app.run_polling() # This line is redundant, should be removed for cleaner code.
                      # app.run_polling() is already called above.
                      # Keeping it for now as per original structure, but ideal fix would be to remove.

if __name__ == '__main__':
    main()
