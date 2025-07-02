import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set
import aiohttp
from aiohttp import TCPConnector
import psycopg2
from urllib.parse import urlparse
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
        
        # Database connection details from environment variable
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if not self.DATABASE_URL:
            logger.error("DATABASE_URL environment variable not found!")
            raise ValueError("DATABASE_URL must be set for database connection.")

        self.conn = None
        self.init_database()
        self.load_premium_users()
        self.load_used_license_keys()
        self.settings = {} # Store dynamic settings
        self.load_settings() # Load settings from DB

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
    
    def init_database(self):
        """Initialize PostgreSQL database tables."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        subscription_end DATE,
                        is_premium BOOLEAN DEFAULT FALSE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS arbitrage_data (
                        id SERIAL PRIMARY KEY,
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
                # New table for dynamic settings
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                ''')
                # New table for command logs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS command_logs (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT,
                        command TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            conn.commit()
            logger.info("PostgreSQL tables initialized or already exist.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            pass # Connection handled by get_db_connection

    def load_settings(self):
        """Load dynamic settings from the database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT key, value FROM settings')
                rows = cursor.fetchall()
                for key, value in rows:
                    self.settings[key] = float(value) if '.' in value or 'e' in value.lower() else int(value)
            
            # Set default values if not present and insert into DB
            default_settings = {
                'min_volume_threshold': 100000.0,
                'max_profit_threshold': 20.0,
                'free_user_max_profit': 2.0,
                'admin_max_profit_threshold': 40.0,
                'max_volatility_percent': 10.0, # New default
                'max_spread_percent': 1.0 # New default (1% spread)
            }
            
            for key, default_value in default_settings.items():
                if key not in self.settings:
                    self.settings[key] = default_value
                    self.update_setting(key, str(default_value)) # Save default to DB
            
            logger.info(f"Loaded settings: {self.settings}")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Fallback to hardcoded defaults if DB loading fails
            self.settings = {
                'min_volume_threshold': 100000.0,
                'max_profit_threshold': 20.0,
                'free_user_max_profit': 2.0,
                'admin_max_profit_threshold': 40.0,
                'max_volatility_percent': 10.0,
                'max_spread_percent': 1.0
            }

    def update_setting(self, key: str, value: str):
        """Update a dynamic setting in the database and in memory."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                ''', (key, value))
            conn.commit()
            self.settings[key] = float(value) if '.' in value or 'e' in value.lower() else int(value)
            logger.info(f"Setting updated: {key} = {value}")
        except Exception as e:
            logger.error(f"Error updating setting {key}: {e}")
            conn.rollback()

    def log_command(self, user_id: int, command: str):
        """Log command usage to the database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO command_logs (user_id, command) VALUES (%s, %s)
                ''', (user_id, command))
            conn.commit()
        except Exception as e:
            logger.error(f"Error logging command {command} for user {user_id}: {e}")
            conn.rollback()

    async def get_cached_arbitrage_data(self, is_premium: bool = False):
        """Cache'den veri döndür, gerekirse yenile"""
        current_time = time.time()
    
        with self.cache_lock:
            # Cache geçerli mi kontrol et
            if (current_time - self.cache_timestamp) < self.cache_duration and self.cache_data:
                self.stats['cache_hits'] += 1 # Update stats here
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

    async def get_admin_arbitrage_data(self, is_premium: bool = False):
        """Adminler için Huobi hariç ve yüksek limitli arbitraj verisi getir"""
        # Admin limitini geçici olarak ayarla
        original_max_profit = self.settings['max_profit_threshold']
        self.settings['max_profit_threshold'] = self.settings['admin_max_profit_threshold']
    
        try:
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
            self.settings['max_profit_threshold'] = original_max_profit

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
    
    async def cache_refresh_task(self):
        """Her 25 saniyede bir cache'i yenile"""
        while True:
            try:
                await asyncio.sleep(25)  # 25 saniye bekle
            
                # Sadece cache eski ise yenile
                current_time = time.time()
                # Check against cache_duration setting
                if (current_time - self.cache_timestamp) > (self.settings.get('cache_duration', 30) - 10): # 10 saniye önce yenile
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
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
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
        """
        Parse exchange-specific data format, including bid/ask prices and price change percentage
        for volatility and spread analysis.
        """
        parsed_data = {}
        try:
            if exchange == 'binance':
                for item in data:
                    symbol = self.normalize_symbol(item['symbol'], exchange)
                    volume = float(item.get('quoteVolume', 0))
                    # Check for bidPrice, askPrice, priceChangePercent
                    bid_price = float(item.get('bidPrice', 0))
                    ask_price = float(item.get('askPrice', 0))
                    price_change_percent = float(item.get('priceChangePercent', 0))

                    if volume >= self.settings['min_volume_threshold']:
                        parsed_data[symbol] = {
                            'price': float(item['lastPrice']),
                            'volume': volume,
                            'bid_price': bid_price,
                            'ask_price': ask_price,
                            'volatility': price_change_percent # Price change percentage
                        }
            
            elif exchange == 'kucoin':
                if 'data' in data and 'ticker' in data['data']:
                    for item in data['data']['ticker']:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        volume = float(item.get('volValue', 0)) # Ensure volume is parsed correctly
                        bid_price = float(item.get('buy', 0))
                        ask_price = float(item.get('sell', 0))
                        # KuCoin's 24hr ticker doesn't directly provide priceChangePercent.
                        # You might need to calculate it from 'changeRate' or fetch candlestick data.
                        # For now, we'll set it to 0 or derive if a 'changeRate' field exists and is usable.
                        volatility = float(item.get('changeRate', 0)) * 100 # Assuming changeRate is decimal

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': float(item['last']),
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'gate':
                for item in data:
                    symbol = self.normalize_symbol(item['currency_pair'], exchange)
                    volume = float(item.get('quote_volume', 0))
                    bid_price = float(item.get('buy_price', 0))
                    ask_price = float(item.get('sell_price', 0))
                    # Gate.io's ticker includes 'change_percentage'
                    volatility = float(item.get('change_percentage', 0)) # Already a percentage

                    if volume >= self.settings['min_volume_threshold']:
                        parsed_data[symbol] = {
                            'price': float(item['last']),
                            'volume': volume,
                            'bid_price': bid_price,
                            'ask_price': ask_price,
                            'volatility': volatility
                        }
            
            elif exchange == 'mexc':
                for item in data:
                    symbol = self.normalize_symbol(item['symbol'], exchange)
                    volume = float(item.get('quoteVolume', 0))
                    bid_price = float(item.get('bidPrice', 0))
                    ask_price = float(item.get('askPrice', 0))
                    volatility = float(item.get('priceChangePercent', 0))

                    if volume >= self.settings['min_volume_threshold']:
                        parsed_data[symbol] = {
                            'price': float(item['lastPrice']),
                            'volume': volume,
                            'bid_price': bid_price,
                            'ask_price': ask_price,
                            'volatility': volatility
                        }
            
            elif exchange == 'bybit':
                if 'result' in data and 'list' in data['result']:
                    for item in data['result']['list']:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        volume = float(item.get('turnover24h', 0))
                        bid_price = float(item.get('bid1Price', 0))
                        ask_price = float(item.get('ask1Price', 0))
                        # Bybit's ticker has price24hPcnt
                        volatility = float(item.get('price24hPcnt', 0)) * 100 # Convert to percentage

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': float(item['lastPrice']),
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'okx':
                if 'data' in data:
                    for item in data['data']:
                        symbol = self.normalize_symbol(item['instId'], exchange)
                        volume = float(item.get('volCcy24h', 0))
                        bid_price = float(item.get('bidPx', 0))
                        ask_price = float(item.get('askPx', 0))
                        # OKX's ticker has 'sodUtc8H' (start of day UTC+8 prices) for change calculation
                        # For simplicity, we might derive volatility from 'high24h' and 'low24h' or set 0 if no direct percentage
                        # For now, let's assume we can derive from last price and open price if available, or set to 0.
                        # OKX v5 ticker provides 'last' and 'sodUtc0' (open price 24h ago).
                        last_price = float(item.get('last', 0))
                        open_price = float(item.get('sodUtc0', 0)) # Open price 24h ago
                        volatility = ((last_price - open_price) / open_price) * 100 if open_price else 0

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': last_price,
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'huobi':
                if 'data' in data:
                    for item in data['data']:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        volume = float(item.get('vol', 0))
                        bid_price = float(item.get('bid', 0))
                        ask_price = float(item.get('ask', 0))
                        # Huobi's ticker has 'amount' for 24h volume. No direct volatility.
                        # Price change can be calculated from 'open' and 'close'
                        open_price = float(item.get('open', 0))
                        close_price = float(item.get('close', 0))
                        volatility = ((close_price - open_price) / open_price) * 100 if open_price else 0

                        if volume >= self.settings['min_volume_threshold'] / 100: # Huobi volume often lower in USDT
                            parsed_data[symbol] = {
                                'price': close_price,
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'bitget':
                if 'data' in data:
                    for item in data['data']:
                        symbol = self.normalize_symbol(item['symbol'], exchange)
                        volume = float(item.get('quoteVol', 0))
                        bid_price = float(item.get('buy', 0))
                        ask_price = float(item.get('sell', 0))
                        # Bitget has 'change' for 24h percentage change
                        volatility = float(item.get('change', 0)) # Already a percentage

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': float(item['close']),
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'bitfinex':
                if isinstance(data, list):
                    for item in data:
                        if len(item) >= 8:
                            symbol = self.normalize_symbol(item[0], exchange)
                            volume = float(item[7]) if item[7] else 0
                            bid_price = float(item[1]) if item[1] else 0 # BID
                            ask_price = float(item[3]) if item[3] else 0 # ASK
                            # Bitfinex has 'LAST_PRICE' (item[6]) and 'DAILY_CHANGE_PERC' (item[5])
                            volatility = float(item[5]) * 100 # Convert to percentage

                            if volume >= self.settings['min_volume_threshold']:
                                parsed_data[symbol] = {
                                    'price': float(item[6]),
                                    'volume': volume,
                                    'bid_price': bid_price,
                                    'ask_price': ask_price,
                                    'volatility': volatility
                                }
            
            elif exchange == 'kraken':
                for symbol_id, ticker_data in data.get('result', {}).items():
                    # Kraken symbols can be tricky (e.g., XBTUSDT)
                    symbol = self.normalize_symbol(symbol_id, exchange)
                    if 'c' in ticker_data and 'v' in ticker_data and 'b' in ticker_data and 'a' in ticker_data:
                        price = float(ticker_data['c'][0]) # Last trade price
                        volume = float(ticker_data['v'][1]) * price # Volume in quote currency
                        bid_price = float(ticker_data['b'][0])
                        ask_price = float(ticker_data['a'][0])
                        # Kraken has 'p' (volume weighted average price) and 'c' (last trade price)
                        # Volatility can be derived from 24h low/high or simple change from open
                        # For now, let's just use 0 if no direct percentage is available in ticker.
                        volatility = 0.0 # Not directly available in basic ticker

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': price,
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'coinbase':
                for item in data:
                    if 'id' in item and 'price' in item and 'volume_24h' in item:
                        symbol = self.normalize_symbol(item['id'], exchange)
                        volume = float(item.get('volume_24h', 0))
                        bid_price = float(item.get('bid', 0))
                        ask_price = float(item.get('ask', 0))
                        # Coinbase Pro API's /products does not have volatility directly
                        # You'd need /products/<product-id>/stats for 24hr stats including open/high/low
                        volatility = 0.0 # Not directly available in /products endpoint

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': float(item['price']),
                                'volume': volume,
                                'bid_price': bid_price,
                                'ask_price': ask_price,
                                'volatility': volatility
                            }
            
            elif exchange == 'poloniex':
                for symbol_id, ticker_data in data.items():
                    if 'close' in ticker_data and 'quoteVolume' in ticker_data:
                        symbol = self.normalize_symbol(symbol_id, exchange)
                        volume = float(ticker_data.get('quoteVolume', 0))
                        bid_price = float(ticker_data.get('high24h', 0)) # Poloniex ticker'da direkt bid/ask yok, high/low kullanabiliriz ya da 0
                        ask_price = float(ticker_data.get('low24h', 0)) # Bu kısım yanlış, gerçek bid/ask alınmalı. Eğer yoksa API dökümanına bakılmalı.
                        volatility = float(ticker_data.get('percentChange', 0)) * 100 # Poloniex'te percentChange var

                        if volume >= self.settings['min_volume_threshold']:
                            parsed_data[symbol] = {
                                'price': float(ticker_data['close']),
                                'volume': volume,
                                'bid_price': bid_price, # Placeholder, needs actual bid from order book or better ticker
                                'ask_price': ask_price, # Placeholder, needs actual ask from order book or better ticker
                                'volatility': volatility
                            }
            
            # TODO: Add parsers for other exchanges to extract bid/ask and volatility if available
            # ... (cryptocom, bingx, lbank, digifinex, bitmart, xt, phemex, bitstamp, gemini, ascendex, coinex, hotcoin, bigone, probit, latoken, bitrue, tidex, p2pb2b)

        except Exception as e:
            logger.error(f"Error parsing {exchange} data: {str(e)}")
        
        return parsed_data

    async def get_cached_arbitrage_data(self, is_premium: bool = False):
        """Cache'den veri döndür, gerekirse yenile"""
        current_time = time.time()
    
        with self.cache_lock:
            # Cache geçerli mi kontrol et
            if (current_time - self.cache_timestamp) < self.settings.get('cache_duration', 30) and self.cache_data:
                self.stats['cache_hits'] += 1
                logger.info("Returning cached data")
                return self.calculate_arbitrage(self.cache_data, is_premium)
        
            # Eğer başka bir request zaten fetch yapıyorsa bekle
            if self.is_fetching:
                # Son cache'i döndür (varsa)
                if self.cache_data:
                    logger.info("Fetch in progress, returning last cached data")
                    return self.calculate_arbitrage(self.cache_data, is_premium)
        
            # Minimum fetch interval kontrolü
            if (current_time - self.last_fetch_time) < self.settings.get('min_fetch_interval', 15):
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
            self.stats['api_requests'] += 1 # Increment API request counter
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
        
        # 1. Trusted symbols list
        if symbol in self.trusted_symbols:
            return (True, "✅ Trusted symbol with verified history and high liquidity.")
        
        # 2. Extract volumes and filter non-zero
        volumes = [data.get('volume', 0) for data in exchange_data.values()]
        non_zero_volumes = [v for v in volumes if v > 0]
        if not non_zero_volumes:
            return (False, "❌ No current volume data available on any exchange.")
        
        total_volume = sum(non_zero_volumes)
        exchanges_with_sufficient_volume = sum(1 for v in non_zero_volumes if v >= self.settings['min_volume_threshold'])

        # 3. Volatility Check
        volatilities = [abs(data.get('volatility', 0)) for data in exchange_data.values()]
        avg_volatility = sum(volatilities) / len(volatilities) if volatilities else 0
        if avg_volatility > self.settings['max_volatility_percent']:
            return (False, f"❌ Volatility for {symbol} is too high ({avg_volatility:.2f}%). Max allowed: {self.settings['max_volatility_percent']:.2f}%.")

        # 4. Spread Check
        # Calculate average spread for the symbol across exchanges that provide bid/ask
        spreads = []
        for data in exchange_data.values():
            bid = data.get('bid_price', 0)
            ask = data.get('ask_price', 0)
            if bid > 0 and ask > 0:
                spread = ((ask - bid) / bid) * 100
                if spread > 0: # Only consider positive spreads
                    spreads.append(spread)
        
        avg_spread = sum(spreads) / len(spreads) if spreads else 0
        if avg_spread > self.settings['max_spread_percent']:
            return (False, f"❌ Average spread for {symbol} is too wide ({avg_spread:.2f}%). Max allowed: {self.settings['max_spread_percent']:.2f}%.")
        
        # 5. Suspicious symbol check
        base_symbol = symbol.replace('USDT', '').replace('USDC', '').replace('BUSD', '')
        is_suspicious_name = any(suspicious in base_symbol.upper() for suspicious in self.suspicious_symbols)
        if is_suspicious_name:
            if total_volume > self.settings['min_volume_threshold'] * 5 and exchanges_with_sufficient_volume >= 3:
                # Require more exchanges for suspicious names
                return (True, f"🔍 Symbol has a suspicious name, but is deemed safe due to high total volume (${total_volume:,.0f}) and presence on {exchanges_with_sufficient_volume} major exchanges.")
            else:
                return (False, f"❌ Symbol has a suspicious name. Total volume (${total_volume:,.0f}) is insufficient or not present on enough major exchanges ({exchanges_with_sufficient_volume} of minimum 3 needed for suspicious symbols).")
        
        # 6. General safety checks for non-trusted, non-suspicious symbols
        if total_volume < self.settings['min_volume_threshold'] * 2: # Require higher total volume for non-trusted symbols
            return (False, f"❌ Total volume (${total_volume:,.0f}) is below the required threshold (${self.settings['min_volume_threshold'] * 2:,.0f}).")
        
        if exchanges_with_sufficient_volume < 2:
            return (False, f"❌ Found on only {exchanges_with_sufficient_volume} exchange(s) with sufficient volume (minimum 2 required).")
        
        # 7. Volume differences too large? (one exchange very high, another very low)
        if len(non_zero_volumes) >= 2:
            max_vol = max(non_zero_volumes)
            min_vol = min(non_zero_volumes)
            if min_vol > 0 and max_vol > min_vol * 100: # 100x difference is suspicious
                return (False, f"❌ Significant volume discrepancy detected. Max volume (${max_vol:,.0f}) is more than 100x minimum volume (${min_vol:,.0f}), indicating potential liquidity issues or data anomalies.")
        
        return (True, f"✅ General safety criteria met: Sufficient total volume (${total_volume:,.0f}) and presence on {exchanges_with_sufficient_volume} exchanges.")

    def validate_arbitrage_opportunity(self, opportunity: Dict) -> bool:
        """Validate if arbitrage opportunity is real"""
        # 1. Profit ratio too high?
        if opportunity['profit_percent'] > self.settings['max_profit_threshold']:
            logger.warning(f"Suspicious high profit: {opportunity['symbol']} - {opportunity['profit_percent']:.2f}%")
            return False
        
        # 2. Price difference reasonable?
        price_ratio = opportunity['sell_price'] / opportunity['buy_price']
        if price_ratio > 1.3: # More than 30% difference is suspicious
            return False
        
        # 3. Minimum profit threshold
        if opportunity['profit_percent'] < 0.1: # Less than 0.1% profit is meaningless
            return False
        
        # TODO: Slippage consideration. Requires order book depth fetching and calculation.
        # This is a complex feature that requires more sophisticated API calls (e.g., /depth or /orderbook)
        # to fetch granular bid/ask quantities, and then simulate placing an order
        # to determine how much the effective price would change given a certain trade size.
        # For a basic implementation, we skip it, but it's crucial for real trading.

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
            exchange_data_for_symbol = {ex: all_data[ex][symbol] for ex in all_data if symbol in all_data[ex]}
            
            # Safety check (includes volume, volatility, spread)
            is_safe, safety_reason = self.is_symbol_safe(symbol, exchange_data_for_symbol)
            if not is_safe:
                logger.debug(f"Skipping {symbol} due to safety check: {safety_reason}")
                continue

            if len(exchange_data_for_symbol) >= 2:
                # Sort by price
                sorted_exchanges = sorted(exchange_data_for_symbol.items(), key=lambda x: x[1]['price'])
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
                        'avg_volume': (lowest_data.get('volume', 0) + highest_data.get('volume', 0)) / 2,
                        'buy_bid_price': lowest_data.get('bid_price', 0), # Add bid/ask for more detail
                        'buy_ask_price': lowest_data.get('ask_price', 0),
                        'sell_bid_price': highest_data.get('bid_price', 0),
                        'sell_ask_price': highest_data.get('ask_price', 0),
                        'volatility': (lowest_data.get('volatility', 0) + highest_data.get('volatility', 0)) / 2 # Avg volatility
                    }
                    
                    if self.validate_arbitrage_opportunity(opportunity):
                        # For free users, only show opportunities up to free_user_max_profit
                        if not is_premium and opportunity['profit_percent'] > self.settings['free_user_max_profit']:
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
                    INSERT INTO users (user_id, username) VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
                ''', (user_id, username))
            conn.commit()
            logger.info(f"User {user_id} (@{username}) saved/updated in PostgreSQL.")
        except Exception as e:
            logger.error(f"Error saving user {user_id}: {e}")
            conn.rollback()

# Telegram Bot Commands and Handlers
bot = ArbitrageBot()
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

if ADMIN_USER_ID == 0:
    logger.warning("ADMIN_USER_ID not set! Admin commands will not work.")

# --- Helper Functions ---
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID

async def send_arbitrage_results(chat_id: int, opportunities: List[Dict], is_premium: bool):
    if not opportunities:
        await bot_app.bot.send_message(chat_id=chat_id, text="Şu an için uygun arbitraj fırsatı bulunamadı.")
        return

    message_parts = ["*Mevcut Arbitraj Fırsatları:*\n\n"]
    for i, opp in enumerate(opportunities):
        if not is_premium and i >= 10: # Limit free users to 10 opportunities
            message_parts.append("\n*Daha fazla fırsat görmek için premium üyeliğe yükseltin.*")
            break

        profit_text = f"*{opp['profit_percent']:.2f}%*"
        if not is_premium:
            profit_text = f"<{opp['profit_percent']:.2f}%" if opp['profit_percent'] > bot.settings['free_user_max_profit'] else f"*{opp['profit_percent']:.2f}%*"
        
        message_parts.append(
            f"📈 *{opp['symbol']}*\n"
            f"  ➡️ Al: `{opp['buy_exchange']}` @ `{opp['buy_price']:.8f}`\n"
            f"  ⬅️ Sat: `{opp['sell_exchange']}` @ `{opp['sell_price']:.8f}`\n"
            f"  🔥 Kar: {profit_text}\n"
            f"  📊 Hacim: ~${opp['avg_volume']:.0f} (avg 24h)\n"
            f"  ⚠️ Volatilite: {opp.get('volatility', 0):.2f}%\n" # Display volatility
            f"\n"
        )
    
    full_message = "".join(message_parts)
    # Telegram'ın mesaj uzunluğu limiti 4096 karakterdir.
    # Eğer mesaj çok uzun olursa, parçalara ayırarak gönderebiliriz.
    if len(full_message) > 4096:
        # Basit bir parçalama, daha akıllı bir bölme yapılabilir
        chunks = [full_message[i:i + 4000] for i in range(0, len(full_message), 4000)]
        for chunk in chunks:
            await bot_app.bot.send_message(chat_id=chat_id, text=chunk, parse_mode='Markdown')
    else:
        await bot_app.bot.send_message(chat_id=chat_id, text=full_message, parse_mode='Markdown')

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"id_{user_id}"
    bot.log_command(user_id, "/start") # Log command
    bot.save_user(user_id, username)

    keyboard = [
        [InlineKeyboardButton("Arbitraj Fırsatlarını Kontrol Et", callback_data='check_arbitrage')],
        [InlineKeyboardButton("Premium Ol", url=GUMROAD_LINK)],
        [InlineKeyboardButton("Destek", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Merhaba! Ben gelişmiş arbitraj botuyum. Farklı borsalardaki kripto para fiyat farklarını tespit ederek arbitraj fırsatlarını bulmama yardımcı olabilirim. Başlamak için aşağıdaki butona tıklayın veya /check yazın.",
        reply_markup=reply_markup
    )

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"id_{user_id}"
    bot.log_command(user_id, "/check") # Log command
    bot.save_user(user_id, username)

    is_premium = bot.is_premium_user(user_id)
    
    await update.message.reply_text("Fiyatlar taranıyor ve arbitraj fırsatları hesaplanıyor... Lütfen bekleyin.")
    
    start_time = time.time()
    try:
        opportunities = await bot.get_cached_arbitrage_data(is_premium)
        duration = time.time() - start_time
        logger.info(f"Check command for user {user_id} completed in {duration:.2f} seconds.")
        await send_arbitrage_results(update.effective_chat.id, opportunities, is_premium)
    except Exception as e:
        logger.error(f"Error in check_command for user {user_id}: {e}")
        await update.message.reply_text("Fırsatları alırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

async def admin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"id_{user_id}"
    bot.log_command(user_id, "/admincheck") # Log command
    bot.save_user(user_id, username)

    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    await update.message.reply_text("Admin moduyla fiyatlar taranıyor ve arbitraj fırsatları hesaplanıyor... Lütfen bekleyin.")
    
    start_time = time.time()
    try:
        opportunities = await bot.get_admin_arbitrage_data(True) # Admin olduğu için True gönder
        duration = time.time() - start_time
        logger.info(f"Admin check command for user {user_id} completed in {duration:.2f} seconds.")
        await send_arbitrage_results(update.effective_chat.id, opportunities, True) # Admin her zaman tüm fırsatları görür
    except Exception as e:
        logger.error(f"Error in admin_check_command for user {user_id}: {e}")
        await update.message.reply_text("Admin fırsatlarını alırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

async def add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, "/addpremium") # Log command
    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Kullanım: /addpremium <user_id> [gün_sayısı]")
        return
    
    try:
        target_user_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        # Get username of the target user if available in chat context
        target_username = ""
        if update.message.reply_to_message:
            target_username = update.message.reply_to_message.from_user.username or f"id_{target_user_id}"
        
        bot.add_premium_user(target_user_id, target_username, days)
        await update.message.reply_text(f"Kullanıcı {target_user_id} ({target_username}) {days} gün boyunca premium olarak eklendi.")
    except ValueError:
        await update.message.reply_text("Geçersiz kullanıcı ID'si veya gün sayısı.")
    except Exception as e:
        logger.error(f"Error in add_premium_command: {e}")
        await update.message.reply_text("Premium kullanıcı eklenirken bir hata oluştu.")

async def remove_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, "/removepremium") # Log command
    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Kullanım: /removepremium <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        bot.remove_premium_user(target_user_id)
        await update.message.reply_text(f"Kullanıcı {target_user_id} premiumluktan çıkarıldı.")
    except ValueError:
        await update.message.reply_text("Geçersiz kullanıcı ID'si.")
    except Exception as e:
        logger.error(f"Error in remove_premium_command: {e}")
        await update.message.reply_text("Premium kullanıcı silinirken bir hata oluştu.")

async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, "/listpremium") # Log command
    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    conn = bot.get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, username, subscription_end FROM premium_users ORDER BY subscription_end DESC")
            premium_users_data = cursor.fetchall()
        
        if not premium_users_data:
            await update.message.reply_text("Hiç premium kullanıcı yok.")
            return

        message = "Premium Kullanıcılar:\n"
        for user_id, username, sub_end in premium_users_data:
            message += f"- {username if username else f'ID: {user_id}'} (Bitiş: {sub_end.strftime('%Y-%m-%d')})\n"
        
        await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error listing premium users: {e}")
        await update.message.reply_text("Premium kullanıcılar listelenirken bir hata oluştu.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, "/stats") # Log command
    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    conn = bot.get_db_connection()
    stats_message = "Bot İstatistikleri:\n"
    
    try:
        with conn.cursor() as cursor:
            # Total Users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            stats_message += f"👥 Toplam Kullanıcı: {total_users}\n"

            # Total Premium Users
            cursor.execute("SELECT COUNT(*) FROM premium_users")
            total_premium_users = cursor.fetchone()[0]
            stats_message += f"⭐ Premium Kullanıcı: {total_premium_users}\n"

            # Command Usage
            cursor.execute("SELECT command, COUNT(*) as count FROM command_logs GROUP BY command ORDER BY count DESC LIMIT 10")
            command_usage = cursor.fetchall()
            stats_message += "\nTop 10 Komut Kullanımı:\n"
            if command_usage:
                for command, count in command_usage:
                    stats_message += f"- {command}: {count}\n"
            else:
                stats_message += "- Henüz komut kullanımı yok.\n"

            # Most Active Users (by command count)
            cursor.execute("SELECT user_id, COUNT(*) as count FROM command_logs GROUP BY user_id ORDER BY count DESC LIMIT 10")
            active_users_raw = cursor.fetchall()
            stats_message += "\nEn Aktif 10 Kullanıcı (Komut Sayısı):\n"
            if active_users_raw:
                for uid, count in active_users_raw:
                    # Try to get username
                    cursor.execute("SELECT username FROM users WHERE user_id = %s", (uid,))
                    username_row = cursor.fetchone()
                    username = username_row[0] if username_row and username_row[0] else f"ID: {uid}"
                    stats_message += f"- {username}: {count} komut\n"
            else:
                stats_message += "- Henüz aktif kullanıcı yok.\n"
            
            # Cache Stats
            stats_message += "\nCache İstatistikleri:\n"
            stats_message += f"  Cache İsabetleri: {bot.stats['cache_hits']}\n"
            stats_message += f"  Cache Kaçırmaları: {bot.stats['cache_misses']}\n"
            stats_message += f"  API İstekleri (Bot Çalıştığından Beri): {bot.stats['api_requests']}\n"

            # Current Settings
            stats_message += "\nAktif Bot Ayarları:\n"
            for key, value in bot.settings.items():
                stats_message += f"  {key}: {value}\n"


    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        stats_message += "İstatistikler alınırken bir hata oluştu."
    
    await update.message.reply_text(stats_message)

async def price_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, "/price") # Log command
    
    if not context.args:
        await update.message.reply_text("Kullanım: /price <symbol> (örn: /price BTCUSDT)")
        return
    
    symbol_to_find = context.args[0].upper()
    
    await update.message.reply_text(f"{symbol_to_find} için fiyatlar aranıyor... Lütfen bekleyin.")
    
    try:
        prices = await bot.get_specific_symbol_prices(symbol_to_find)
        
        if not prices:
            await update.message.reply_text(f"{symbol_to_find} için herhangi bir borsada fiyat bulunamadı.")
            return

        message = f"*{symbol_to_find} Fiyatları (Düşükten Yükseğe):*\n\n"
        for exchange, price in prices:
            message += f"  • {exchange.capitalize()}: `{price:.8f}`\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in price_check_command for {symbol_to_find}: {e}")
        await update.message.reply_text("Fiyatları alırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

# --- Admin Setting Commands ---
async def set_setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE, setting_key: str) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, f"/set_{setting_key}") # Log command

    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(f"Kullanım: /set_{setting_key} <değer>")
        return
    
    try:
        value_str = context.args[0]
        # Attempt to convert to float, then int. Store as string in DB.
        try:
            value = float(value_str)
            if value_str.isdigit(): # If it was a whole number, store as int
                value = int(value)
        except ValueError:
            await update.message.reply_text(f"Geçersiz değer. Lütfen sayısal bir değer girin. (örn: /set_{setting_key} 100000 veya /set_{setting_key} 2.5)")
            return

        bot.update_setting(setting_key, str(value))
        await update.message.reply_text(f"'{setting_key}' ayarı başarıyla '{value}' olarak güncellendi.")
    except Exception as e:
        logger.error(f"Error setting {setting_key}: {e}")
        await update.message.reply_text(f"'{setting_key}' ayarı güncellenirken bir hata oluştu.")

async def set_volume_threshold_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_setting_command(update, context, 'min_volume_threshold')

async def set_free_profit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_setting_command(update, context, 'free_user_max_profit')

async def set_admin_profit_command(update: Update, ContextTypes: ContextTypes.DEFAULT_TYPE) -> None:
    await set_setting_command(update, context, 'admin_max_profit_threshold')

async def set_volatility_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_setting_command(update, context, 'max_volatility_percent')

async def set_spread_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_setting_command(update, context, 'max_spread_percent')

async def refresh_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.log_command(user_id, "/refresh_cache") # Log command
    if not is_admin(user_id):
        await update.message.reply_text("Bu komutu kullanma yetkiniz yok.")
        return
    
    await update.message.reply_text("Önbellek yenileniyor... Lütfen bekleyin.")
    try:
        await bot._fetch_fresh_data(True) # Force refresh for admin, assume premium for calculation
        await update.message.reply_text("Önbellek başarıyla yenilendi.")
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        await update.message.reply_text("Önbellek yenilenirken bir hata oluştu.")


# --- Callback Handler ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # Always answer callback queries

    user_id = query.from_user.id
    username = query.from_user.username or f"id_{user_id}"
    bot.log_command(user_id, f"callback:{query.data}") # Log callback as command
    bot.save_user(user_id, username) # Ensure user is saved

    if query.data == 'check_arbitrage':
        is_premium = bot.is_premium_user(user_id)
        
        await query.edit_message_text(text="Fiyatlar taranıyor ve arbitraj fırsatları hesaplanıyor... Lütfen bekleyin.")
        
        start_time = time.time()
        try:
            opportunities = await bot.get_cached_arbitrage_data(is_premium)
            duration = time.time() - start_time
            logger.info(f"Check arbitrage via button for user {user_id} completed in {duration:.2f} seconds.")
            await send_arbitrage_results(query.message.chat_id, opportunities, is_premium)
        except Exception as e:
            logger.error(f"Error in button_handler (check_arbitrage) for user {user_id}: {e}")
            await query.message.reply_text("Fırsatları alırken bir hata oluştu. Lütfen daha sonra tekrar deneyin.")

async def handle_license_activation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"id_{user_id}"
    bot.log_command(user_id, "license_text_input") # Log command
    bot.save_user(user_id, username)

    license_key = update.message.text.strip()
    
    if license_key in bot.used_license_keys:
        await update.message.reply_text("Bu lisans anahtarı zaten kullanılmış.")
        return

    await update.message.reply_text("Lisans anahtarı doğrulanıyor... Lütfen bekleyin.")
    
    verification_result = await bot.verify_gumroad_license(license_key)
    
    if verification_result.get('success'):
        sale = verification_result.get('purchase', {})
        if sale.get('cancelled'):
            await update.message.reply_text("Bu lisans anahtarı iptal edilmiş.")
            return
        
        # Check if the product matches GUMROAD_PRODUCT_ID if Gumroad API supports it
        # Currently, verify_gumroad_license sends product_id in request, so it implicitly checks.

        bot.activate_license_key(license_key, user_id, username, sale)
        await update.message.reply_text(
            f"Tebrikler! Lisans anahtarınız başarıyla etkinleştirildi.\n"
            f"Premium üyeliğiniz şimdi aktif ve {bot.premium_users.add(user_id) or '30 gün'} süresince geçerli."
        )
    else:
        error_message = verification_result.get('error', 'Bilinmeyen bir hata oluştu.')
        await update.message.reply_text(f"Lisans anahtarı doğrulanamadı: {error_message}")


async def start_background_tasks(application: Application):
    """Start background tasks on bot startup."""
    asyncio.create_task(bot.cache_refresh_task())
    logger.info("Background cache refresh task started.")

def main() -> None:
    """Run the bot."""
    global bot_app # Make bot_app global so it can be accessed by handlers

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not found!")
        raise ValueError("TELEGRAM_BOT_TOKEN must be set for the bot to run.")

    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
    
    if ADMIN_USER_ID == 0:
        logger.warning("ADMIN_USER_ID not set! Admin commands will not work.")
    
    bot_app = Application.builder().token(TOKEN).build()

    bot_app.post_init = start_background_tasks
    
    # Command handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("check", check_command))
    bot_app.add_handler(CommandHandler("addpremium", add_premium_command))
    bot_app.add_handler(CommandHandler("removepremium", remove_premium_command))
    bot_app.add_handler(CommandHandler("listpremium", list_premium_command))
    bot_app.add_handler(CommandHandler("stats", stats_command))
    bot_app.add_handler(CommandHandler("admincheck", admin_check_command))
    bot_app.add_handler(CommandHandler("price", price_check_command)) # Mevcut komut

    # Yeni Admin Ayar Komutları
    bot_app.add_handler(CommandHandler("set_volume_threshold", set_volume_threshold_command))
    bot_app.add_handler(CommandHandler("set_free_profit", set_free_profit_command))
    bot_app.add_handler(CommandHandler("set_admin_profit", set_admin_profit_command))
    bot_app.add_handler(CommandHandler("set_volatility", set_volatility_command))
    bot_app.add_handler(CommandHandler("set_spread", set_spread_command))
    bot_app.add_handler(CommandHandler("refresh_cache", refresh_cache_command)) # Yeni manuel önbellek yenileme

    # Message handlers (command handlers'dan sonra)
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_license_activation))
    
    # Callback handlers
    bot_app.add_handler(CallbackQueryHandler(button_handler))

    async def cleanup():
        if bot.session and not bot.session.closed:
            await bot.session.close()
        if bot.conn and not bot.conn.closed:
            bot.conn.close()
            logger.info("PostgreSQL database connection closed.")
    
    bot_app.post_stop = cleanup
    
    bot_app.run_polling()
    
    logger.info("Advanced Arbitrage Bot starting...")
    logger.info(f"Monitoring {len(bot.exchanges)} exchanges")
    logger.info(f"Tracking {len(bot.trusted_symbols)} trusted symbols")
    logger.info(f"Premium users loaded: {len(bot.premium_users)}")
    
if __name__ == '__main__':
    main()
