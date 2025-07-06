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
        
        # Minimum 24h volume threshold - filter low volume coins
        self.min_volume_threshold = 100000  # $100k minimum 24h volume
        
        # Maximum profit threshold - very high differences are suspicious
        self.max_profit_threshold = 20.0  # 20%+ profit is suspicious
        
        # Free user maximum profit display
        self.free_user_max_profit = 2.0  # Show max 2% profit for free users
        
        # Premium users cache
        self.premium_users = set()

        self.affiliate_links = {}

        self.conn = None

        self.init_database()
        self.update_arbitrage_table()
        
        # Database connection details from environment variable
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if not self.DATABASE_URL:
            logger.error("DATABASE_URL environment variable not found!")
            raise ValueError("DATABASE_URL must be set for database connection.")

        self.conn = None
        self.init_database()
        self.load_premium_users()
        self.load_used_license_keys()

        self.max_profit_threshold = 20.0
        self.admin_max_profit_threshold = 40.0

        # License key validation cache
        self.used_license_keys = set()
        
        # Cache system
        self.cache_data = {}
        self.cache_timestamp = 0
        self.cache_duration = 30  # 30 seconds cache
        self.cache_lock = Lock()
        
        # API request limits
        self.is_fetching = False
        self.last_fetch_time = 0
        self.min_fetch_interval = 15  # Minimum 15 seconds between fetches

        # Connection pool
        self.connector = TCPConnector(
            limit=50,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self.session = None
        
        # Request semaphore (max 10 concurrent requests)
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
                url = urlparse(self.DATABASE_URL)
                self.conn = psycopg2.connect(
                    host=url.hostname,
                    port=url.port,
                    user=url.username,
                    password=url.password,
                    database=url.path[1:]
                )
                logger.info("Successfully connected to PostgreSQL database.")
            except Exception as e:
                logger.error(f"Error connecting to PostgreSQL: {e}")
                raise
        return self.conn

    def get_all_users(self) -> List[Dict]:
        """Get all users from database"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT user_id, username, is_premium FROM users')
                return [
                    {'user_id': row[0], 'username': row[1] or 'Unknown', 'is_premium': row[2]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

    def get_free_users(self) -> List[Dict]:
        """Get free users from database"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT user_id, username FROM users 
                    WHERE user_id NOT IN (SELECT user_id FROM premium_users)
                ''')
                return [
                    {'user_id': row[0], 'username': row[1] or 'Unknown'}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"Error getting free users: {e}")
            return []

    async def get_cached_arbitrage_data(self, is_premium: bool = False):
        """Get cached arbitrage data"""
        current_time = time.time()
    
        with self.cache_lock:
            if (current_time - self.cache_timestamp) < self.cache_duration and self.cache_data:
                logger.info("Returning cached data")
                return self.calculate_arbitrage(self.cache_data, is_premium)
        
            if self.is_fetching:
                if self.cache_data:
                    logger.info("Fetch in progress, returning last cached data")
                    return self.calculate_arbitrage(self.cache_data, is_premium)
        
            if (current_time - self.last_fetch_time) < self.min_fetch_interval:
                if self.cache_data:
                    logger.info("Rate limit protection, returning cached data")
                    return self.calculate_arbitrage(self.cache_data, is_premium)
    
        return await self._fetch_fresh_data(is_premium)

    def update_arbitrage_table(self):
        """Add user_id column to arbitrage_data table if it doesn't exist"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Check if column exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='arbitrage_data' AND column_name='user_id'
                """)
                if not cursor.fetchone():
                    # Add the column if it doesn't exist
                    cursor.execute("""
                        ALTER TABLE arbitrage_data 
                        ADD COLUMN user_id BIGINT,
                        ADD FOREIGN KEY (user_id) REFERENCES users(user_id)
                    """)
                    conn.commit()
                    logger.info("Added user_id column to arbitrage_data table")
                else:
                   logger.info("user_id column already exists in arbitrage_data")
        except Exception as e:
            logger.error(f"Error updating arbitrage_data table: {e}")
            conn.rollback()
        finally:
            if conn:
                conn.close()

    def save_arbitrage_data(self, opportunity: Dict, user_id: int = None):
        """Save arbitrage data to PostgreSQL with user_id"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO arbitrage_data 
                    (symbol, exchange1, exchange2, price1, price2, 
                     profit_percent, volume_24h, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    opportunity['symbol'],
                    opportunity['buy_exchange'],
                    opportunity['sell_exchange'],
                    opportunity['buy_price'],
                    opportunity['sell_price'],
                    opportunity['profit_percent'],
                    opportunity['avg_volume'],
                    user_id
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving arbitrage data: {e}")
            conn.rollback()



    def update_database_schema(self):
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    ALTER TABLE arbitrage_data 
                    ADD COLUMN IF NOT EXISTS user_id BIGINT,
                    ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ''')
                conn.commit()
                logger.info("Database schema updated successfully")
        except Exception as e:
            logger.error(f"Error updating database schema: {e}")
            conn.rollback()
        finally:
            if conn:
                conn.close()

    async def get_admin_arbitrage_data(self, is_premium: bool = False):
        """Get arbitrage data for admin with higher threshold"""
        original_limit = self.max_profit_threshold
    
        try:
            self.max_profit_threshold = self.admin_max_profit_threshold
        
            current_time = time.time()
            with self.cache_lock:
                if (current_time - self.cache_timestamp) < self.cache_duration and self.cache_data:
                    logger.info("Returning cached data for admin")
                    filtered_data = {ex: data for ex, data in self.cache_data.items() if ex != 'huobi'}
                    return self.calculate_arbitrage(filtered_data, True)

            all_data = await self.get_all_prices_with_volume()
            filtered_data = {ex: data for ex, data in all_data.items() if ex != 'huobi'}
        
            return self.calculate_arbitrage(filtered_data, True)
    
        finally:
            self.max_profit_threshold = original_limit

    async def get_session(self):
        """Get shared session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout,
                headers={'User-Agent': 'ArbitrageBot/1.0'}
            )
        return self.session

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
                    return self.parse_exchange_data(exchange, data)
                    
            except Exception as e:
                logger.error(f"{exchange} price/volume error: {str(e)}")
                return {}

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
                conn.commit()

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
                conn.commit()

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS premium_users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        added_by_admin BOOLEAN DEFAULT TRUE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        subscription_end DATE
                    )
                ''')
                conn.commit()

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

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS affiliates (
                        affiliate_code TEXT PRIMARY KEY,
                        influencer_id BIGINT,
                        influencer_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        uses INT DEFAULT 0
                    )
                ''')
                conn.commit()

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS affiliate_users (
                        user_id BIGINT,
                        affiliate_code TEXT,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, affiliate_code)
                    )
                ''')
                conn.commit()

        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            conn.rollback()
        finally:
            if conn:
                conn.close()

    async def cache_refresh_task(self):
        """Refresh cache every 25 seconds"""
        while True:
            try:
                await asyncio.sleep(25)
            
                current_time = time.time()
                if (current_time - self.cache_timestamp) > 20:
                    logger.info("Background cache refresh")
                    await self._fetch_fresh_data(False)
                
            except Exception as e:
                logger.error(f"Background cache refresh error: {e}")
                await asyncio.sleep(60)
    
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
            self.premium_users = set()

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
            self.used_license_keys = set()

    async def verify_gumroad_license(self, license_key: str) -> Dict:
        """Verify license key with Gumroad API"""
        try:
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
        
            logger.info(f"Verifying license: {license_key}")
            logger.info(f"Request URL: {url}")
            logger.info(f"Request data: {data}")
    
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                
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

    def create_affiliate_link(self, influencer_id: int, influencer_name: str) -> str:
        """Create a unique affiliate link"""
        code = f"ref-{influencer_id}-{int(time.time())}"
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO affiliates 
                    (affiliate_code, influencer_id, influencer_name)
                    VALUES (%s, %s, %s)
                ''', (code, influencer_id, influencer_name))
            conn.commit()
            return code
        except Exception as e:
            logger.error(f"Error creating affiliate link: {e}")
            conn.rollback()
            return None

    def track_affiliate_user(self, user_id: int, affiliate_code: str):
        """Track user who came from affiliate link"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO affiliate_users (user_id, affiliate_code)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                ''', (user_id, affiliate_code))
            
                cursor.execute('''
                    UPDATE affiliates 
                    SET uses = uses + 1
                    WHERE affiliate_code = %s
                ''', (affiliate_code,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error tracking affiliate user: {e}")
            conn.rollback()

    def get_affiliate_stats(self) -> List[Dict]:
        """Get affiliate statistics"""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT 
                        a.affiliate_code, 
                        a.influencer_name, 
                        a.uses, 
                        COUNT(p.user_id) as premium_conversions
                    FROM affiliates a
                    LEFT JOIN affiliate_users u ON a.affiliate_code = u.affiliate_code
                    LEFT JOIN premium_users p ON u.user_id = p.user_id
                    GROUP BY a.affiliate_code, a.influencer_name, a.uses
                    ORDER BY a.uses DESC
                ''')
                results = cursor.fetchall()
                return [
                    {
                        'code': row[0],
                        'name': row[1],
                        'total_uses': row[2],
                        'premium_conversions': row[3] or 0
                    }
                    for row in results
                ]
        except Exception as e:
            logger.error(f"Error getting affiliate stats: {e}")
            conn.rollback()
            return []
        finally:
            if conn:
                conn.close()
            
    def activate_license_key(self, license_key: str, user_id: int, username: str, sale_data: Dict):
        """Activate license key and add premium subscription in PostgreSQL."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO license_keys 
                    (license_key, user_id, username, gumroad_sale_id)
                    VALUES (%s, %s, %s, %s)
                ''', (license_key, user_id, username, sale_data.get('sale_id', '')))
                
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
            
            self.used_license_keys.add(license_key)
            self.premium_users.add(user_id)
            
            logger.info(f"License activated: {license_key} for user {user_id}.")
        except Exception as e:
            logger.error(f"Error activating license key: {e}")
            conn.rollback()

    async def show_send_message_options(self, query):
        text = "📩 **Send Message to Users**\n\nSelect recipient group:"
    
        keyboard = [
            [InlineKeyboardButton("👥 All Users", callback_data='send_all')],
            [InlineKeyboardButton("💎 Premium Users", callback_data='send_premium')],
            [InlineKeyboardButton("🆓 Free Users", callback_data='send_free')],
            [InlineKeyboardButton("👤 Specific User", callback_data='send_specific')],
            [InlineKeyboardButton("🔙 Admin Panel", callback_data='admin')]
        ]
    
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_send_message_choice(self, query):
        choice = query.data.replace('send_', '')
        query._bot_data['message_recipient'] = choice
    
        if choice == 'specific':
            await query.edit_message_text("👤 Enter the username or ID of the user you want to message:")
        else:
            await query.edit_message_text("✉️ Enter the message you want to send:")

    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            return
    
        recipient_type = context.user_data.get('message_recipient')
        message_text = update.message.text
    
        if recipient_type == 'specific':
            user_input = message_text.strip()
            try:
                if user_input.isdigit():
                    user_id = int(user_input)
                    await context.bot.send_message(user_id, f"📨 Admin Message:\n\n{context.user_data['message_text']}")
                    await update.message.reply_text(f"✅ Message sent to user ID {user_id}.")
                else:
                    username = user_input.replace('@', '')
                    user_id = self.get_user_id_by_username(username)
                    if user_id:
                        await context.bot.send_message(user_id, f"📨 Admin Message:\n\n{context.user_data['message_text']}")
                        await update.message.reply_text(f"✅ Message sent to @{username}.")
                    else:
                        await update.message.reply_text(f"❌ User @{username} not found.")
            except Exception as e:
                await update.message.reply_text(f"❌ Error sending message: {e}")
        else:
            users = []
            if recipient_type == 'all':
                users = self.get_all_users()
            elif recipient_type == 'premium':
                users = [{'user_id': uid} for uid in self.premium_users]
            elif recipient_type == 'free':
                users = self.get_free_users()
        
            success = 0
            failed = 0
        
            msg = await update.message.reply_text(f"📨 Sending message to {len(users)} users...")
        
            for user in users:
                try:
                    await context.bot.send_message(
                        user['user_id'],
                        f"📨 Admin Message:\n\n{message_text}"
                    )
                    success += 1
                except Exception as e:
                    failed += 1
        
            await msg.edit_text(
                f"📨 Message broadcast results:\n"
                f"• Total recipients: {len(users)}\n"
                f"• Successfully sent: {success}\n"
                f"• Failed to send: {failed}"
            )
    
    def add_premium_user(self, user_id: int, username: str = "", days: int = 30):
        """Add premium user (admin command) to PostgreSQL."""
        conn = self.get_db_connection()
        try:
            end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            with conn.cursor() as cursor:
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

    async def create_affiliate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("❌ Access denied. Admin only command.")
            return
    
        influencer_name = ' '.join(context.args) if context.args else update.effective_user.username
        code = self.create_affiliate_link(update.effective_user.id, influencer_name)
    
        if code:
            await update.message.reply_text(
                f"✅ Affiliate link created for {influencer_name}:\n\n"
                f"https://t.me/your_bot_username?start={code}\n\n"
                f"Share this link to track referrals."
            )
        else:
            await update.message.reply_text("❌ Error creating affiliate link.")

    async def affiliate_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("❌ Access denied. Admin only command.")
            return
    
        stats = self.get_affiliate_stats()
    
        if not stats:
            await update.message.reply_text("No affiliate data available.")
            return
    
        text = "📊 **Affiliate Statistics**\n\n"
        for stat in stats:
            text += (
                f"👤 Influencer: {stat['name']}\n"
                f"🔗 Code: {stat['code']}\n"
                f"👥 Total Referrals: {stat['total_uses']}\n"
                f"💎 Premium Conversions: {stat['premium_conversions']}\n"
                f"📈 Conversion Rate: {stat['premium_conversions']/stat['total_uses']*100:.1f}%\n\n"
            )
    
        await update.message.reply_text(text)

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
        normalized = symbol.upper().replace('/', '').replace('-', '').replace('_', '')
        
        if exchange == 'bitfinex' and normalized.startswith('T'):
            normalized = normalized[1:]
        
        if symbol in self.symbol_mapping:
            normalized = self.symbol_mapping[symbol]
        
        return normalized
    
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
            
        except Exception as e:
            logger.error(f"Error parsing {exchange} data: {str(e)}")
        
        return {}

    async def _fetch_fresh_data(self, is_premium: bool):
        """Fetch fresh data and cache it"""
        with self.cache_lock:
            if self.is_fetching:
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
        
        all_exchange_data = await self.get_all_prices_with_volume()
        
        found_prices = []
        for exchange_name, data_for_exchange in all_exchange_data.items():
            if normalized_symbol_to_find in data_for_exchange:
                price = data_for_exchange[normalized_symbol_to_find]['price']
                if price > 0:
                    found_prices.append((exchange_name, price))
        
        found_prices.sort(key=lambda x: x[1])
        return found_prices
    
    def is_symbol_safe(self, symbol: str, exchange_data: Dict[str, Dict]) -> Tuple[bool, str]:
        """Check if symbol is safe for arbitrage and return reason."""
        
        logger.info(f"Checking safety for symbol: {symbol}")
        logger.info(f"Exchange data for {symbol}: {exchange_data}")

        if symbol in self.trusted_symbols:
            logger.info(f"{symbol} is a trusted symbol.")
            return (True, "✅ Trusted symbol with verified history and high liquidity.")
        
        volumes = [data.get('volume', 0) for data in exchange_data.values()]
        non_zero_volumes = [v for v in volumes if v > 0]
        logger.info(f"Non-zero volumes for {symbol}: {non_zero_volumes}")

        if not non_zero_volumes:
            logger.warning(f"No current volume data available for {symbol}.")
            return (False, "❌ No current volume data available on any exchange.")

        total_volume = sum(non_zero_volumes)
        exchanges_with_sufficient_volume = sum(1 for v in non_zero_volumes if v >= self.min_volume_threshold)
        logger.info(f"Total volume for {symbol}: ${total_volume:,.0f}, Exchanges with sufficient volume: {exchanges_with_sufficient_volume}")
        
        base_symbol = symbol.replace('USDT', '').replace('USDC', '').replace('BUSD', '')
        is_suspicious_name = any(suspicious in base_symbol.upper() for suspicious in self.suspicious_symbols)
        logger.info(f"Is {symbol} a suspicious name? {is_suspicious_name}")

        if is_suspicious_name:
            if total_volume > self.min_volume_threshold * 5 and exchanges_with_sufficient_volume >= 3:
                logger.info(f"Suspicious symbol {symbol} deemed safe due to high volume and sufficient exchanges.")
                return (True, f"🔍 Symbol has a suspicious name, but is deemed safe due to high total volume (${total_volume:,.0f}) and presence on {exchanges_with_sufficient_volume} major exchanges.")
            else:
                logger.warning(f"Suspicious symbol {symbol} deemed unsafe. Total volume: ${total_volume:,.0f}, Exchanges with sufficient volume: {exchanges_with_sufficient_volume}.")
                return (False, f"❌ Symbol has a suspicious name. Total volume (${total_volume:,.0f}) is insufficient or not present on enough major exchanges ({exchanges_with_sufficient_volume} of minimum 3 needed for suspicious symbols).")

        if total_volume < self.min_volume_threshold * 2:
            logger.warning(f"Total volume for {symbol} (${total_volume:,.0f}) is below the required threshold (${self.min_volume_threshold * 2:,.0f}).")
            return (False, f"❌ Total volume (${total_volume:,.0f}) is below the required threshold (${self.min_volume_threshold * 2:,.0f}).")
        
        if exchanges_with_sufficient_volume < 2:
            logger.warning(f"{symbol} found on only {exchanges_with_sufficient_volume} exchange(s) with sufficient volume (minimum 2 required).")
            return (False, f"❌ Found on only {exchanges_with_sufficient_volume} exchange(s) with sufficient volume (minimum 2 required).")

        if len(non_zero_volumes) >= 2:
            max_vol = max(non_zero_volumes)
            min_vol = min(non_zero_volumes)
            if min_vol > 0 and max_vol > min_vol * 100:
                logger.warning(f"Significant volume discrepancy detected for {symbol}. Max volume (${max_vol:,.0f}) is more than 100x minimum volume (${min_vol:,.0f}).")
                return (False, f"❌ Significant volume discrepancy detected. Max volume (${max_vol:,.0f}) is more than 100x minimum volume (${min_vol:,.0f}), indicating potential liquidity issues or data anomalies.")

        logger.info(f"{symbol} met general safety criteria.")
        return (True, f"✅ General safety criteria met: Sufficient total volume (${total_volume:,.0f}) and presence on {exchanges_with_sufficient_volume} exchanges.")
    
    def validate_arbitrage_opportunity(self, opportunity: Dict) -> bool:
        """Validate if arbitrage opportunity is real"""
        
        if opportunity['profit_percent'] > self.max_profit_threshold:
            logger.warning(f"Suspicious high profit: {opportunity['symbol']} - {opportunity['profit_percent']:.2f}%")
            return False
        
        price_ratio = opportunity['sell_price'] / opportunity['buy_price']
        if price_ratio > 1.3:
            return False
        
        if opportunity['profit_percent'] < 0.1:
            return False
        
        return True
    
    def calculate_arbitrage(self, all_data: Dict[str, Dict[str, Dict]], is_premium: bool = False) -> List[Dict]:
        """Enhanced arbitrage calculation"""
        opportunities = []
        
        all_symbols = set()
        for exchange_data in all_data.values():
            if exchange_data:
                all_symbols.update(exchange_data.keys())
        
        common_symbols = set()
        for symbol in all_symbols:
            exchanges_with_symbol = sum(1 for exchange_data in all_data.values() if symbol in exchange_data)
            if exchanges_with_symbol >= 2:
                common_symbols.add(symbol)
        
        logger.info(f"Found {len(common_symbols)} common symbols")
        
        for symbol in common_symbols:
            exchange_data = {ex: all_data[ex][symbol] for ex in all_data if symbol in all_data[ex]}
            
            is_safe, _ = self.is_symbol_safe(symbol, exchange_data)
            if not is_safe:
                continue
            
            if len(exchange_data) >= 2:
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

    def check_table_columns(self):
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'arbitrage_data'")
                columns = [row[0] for row in cursor.fetchall()]
                logger.info(f"arbitrage_data columns: {columns}")
        except Exception as e:
           logger.error(f"Error checking table columns: {e}")
        finally:
            if conn:
                conn.close()

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

# Global bot instance
bot = ArbitrageBot()

# Admin user ID - set your Telegram user ID here
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.save_user(user.id, user.username or "")
    
    if context.args and context.args[0].startswith('ref-'):
        affiliate_code = context.args[0]
        bot.track_affiliate_user(user.id, affiliate_code)
    
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
    elif query.data == 'send_message' and query.from_user.id == ADMIN_USER_ID:
        await bot.show_send_message_options(query)

async def handle_arbitrage_check(query):
    await query.edit_message_text("🔄 Scanning prices across exchanges... (Security filters active)")
    
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
        trust_icon = "✅" if opp['symbol'] in bot.trusted_symbols else "🔍"
        
        text += f"{i}. {trust_icon} {opp['symbol']}\n"
        text += f"   ⬇️ Buy: {opp['buy_exchange']} ${opp['buy_price']:.6f}\n"
        text += f"   ⬆️ Sell: {opp['sell_exchange']} ${opp['sell_price']:.6f}\n"
        text += f"   💰 Profit: {opp['profit_percent']:.2f}%\n"
        text += f"   📊 Volume: ${opp['avg_volume']:,.0f}\n\n"
        
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
        reply_markup=InlineKeyboardMarkup(keyboard)
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
    
    logger.info(f"Received license key from user {user.id}: '{license_key}'")
    logger.info(f"License key length: {len(license_key)}")
    
    if not license_key or len(license_key) < 10:
        logger.info("License key too short, ignoring")
        return
    
    if not any(c.isalnum() for c in license_key):
        logger.info("License key contains no alphanumeric characters, ignoring")
        return
    
    await update.message.reply_text("🔄 Verifying license key...")
    
    if license_key in bot.used_license_keys:
        await update.message.reply_text("❌ This license key has already been used.")
        return
    
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
    """Start background tasks"""
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
• Total free users: {}
• Total users: {}
• Trusted symbols: {}

🛠️ **Available Commands:**
• /addpremium <user_id> [days] - Add premium user
• /removepremium <user_id> - Remove premium user
• /listpremium - List all premium users
• /stats - Bot statistics
• /admincheck - Admin arbitrage check
• /broadcast - Send message to users

📋 **Quick Actions:""".format(
        len(bot.premium_users), 
        len(bot.get_free_users()),
        len(bot.get_all_users()),
        len(bot.trusted_symbols)
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 List Premium Users", callback_data='list_premium')],
        [InlineKeyboardButton("📩 Send Message to Users", callback_data='send_message')],
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def list_premium_users(query):
    users = bot.get_premium_users_list()
    
    if not users:
        text = "📋 **Premium Users List**\n\nNo premium users found."
    else:
        text = f"📋 **Premium Users List** ({len(users)} users)\n\n"
        for i, user in enumerate(users[:20], 1):
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
            user_id = int(user_input)
            bot.remove_premium_user(user_id)
            await update.message.reply_text(f"✅ User {user_id} removed from premium.")
        else:
            username = user_input.replace('@', '')
            user_id = bot.get_user_id_by_username(username)
            
            if user_id:
                bot.remove_premium_user(user_id)
                await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) removed from premium.")
            else:
                await update.message.reply_text(f"❌ User @{username} not found in database.")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Use numbers only.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def create_affiliate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    influencer_name = ' '.join(context.args) if context.args else update.effective_user.username
    code = bot.create_affiliate_link(update.effective_user.id, influencer_name)
    
    if code:
        await update.message.reply_text(
            f"✅ Affiliate link created for {influencer_name}:\n\n"
            f"https://t.me/{context.bot.username}?start={code}\n\n"
            f"Share this link to track referrals."
        )
    else:
        await update.message.reply_text("❌ Error creating affiliate link.")

async def affiliate_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    stats = bot.get_affiliate_stats()
    
    if not stats:
        await update.message.reply_text("No affiliate data available.")
        return
    
    text = "📊 **Affiliate Statistics**\n\n"
    for stat in stats:
        conversion_rate = (stat['premium_conversions'] / stat['total_uses'] * 100) if stat['total_uses'] > 0 else 0
        text += (
            f"👤 Influencer: {stat['name']}\n"
            f"🔗 Code: {stat['code']}\n"
            f"👥 Total Referrals: {stat['total_uses']}\n"
            f"💎 Premium Conversions: {stat['premium_conversions']}\n"
            f"📈 Conversion Rate: {conversion_rate:.1f}%\n\n"
        )
    
    await update.message.reply_text(text)

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
        
        if user_input.isdigit():
            user_id = int(user_input)
            bot.add_premium_user(user_id, "", days)
            await update.message.reply_text(f"✅ User {user_id} added as premium for {days} days.")
        else:
            username = user_input.replace('@', '')
            user_id = bot.get_user_id_by_username(username)
            
            if user_id:
                bot.add_premium_user(user_id, username, days)
                await update.message.reply_text(f"✅ User @{username} (ID: {user_id}) added as premium for {days} days.")
            else:
                await update.message.reply_text(f"❌ User @{username} not found in database. User must start the bot first.")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid days parameter. Use numbers only for days.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

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
    
    try:
        # First update the table schema if needed
        bot.update_arbitrage_table()
        
        conn = bot.get_db_connection()
        
        text = "📊 **Advanced Bot Statistics**\n\n"
        
        # Basic counts
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            text += f"👥 Total users: {total_users}\n"
            
            cursor.execute('SELECT COUNT(*) FROM premium_users')
            premium_users = cursor.fetchone()[0]
            text += f"💎 Premium users: {premium_users}\n"
            
            cursor.execute('SELECT COUNT(*) FROM arbitrage_data')
            total_records = cursor.fetchone()[0]
            text += f"📈 Arbitrage records: {total_records}\n\n"
        
        # Top users - with fallback if user_id not available
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT u.username, COUNT(a.id) as activity_count
                    FROM arbitrage_data a
                    JOIN users u ON a.user_id = u.user_id
                    GROUP BY u.username
                    ORDER BY activity_count DESC
                    LIMIT 5
                ''')
                top_users = cursor.fetchall()
                
                if top_users:
                    text += "🏆 **Top Active Users:**\n"
                    for i, (username, count) in enumerate(top_users, 1):
                        text += f"{i}. @{username or 'Unknown'}: {count} checks\n"
                else:
                    text += "ℹ️ No user activity data available\n"
        except psycopg2.Error as e:
            logger.warning(f"Couldn't get user activity stats: {e}")
            text += "⚠️ User activity stats not available\n"
        
        # Recent premium activations
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT username, added_date 
                FROM premium_users 
                ORDER BY added_date DESC 
                LIMIT 5
            ''')
            recent_premium = cursor.fetchall()
            
            text += "\n🆕 **Recent Premium Activations:**\n"
            for i, (username, added_date) in enumerate(recent_premium, 1):
                text += f"{i}. @{username or 'Unknown'} on {added_date}\n"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error in stats_command: {e}")
        await update.message.reply_text("❌ Error fetching statistics. Please try again later.")
    finally:
        if conn:
            conn.close()

async def admin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    for i, opp in enumerate(opportunities[:20], 1):
        trust_icon = "✅" if opp['symbol'] in bot.trusted_symbols else "🔍"
        text += f"{i}. {trust_icon} {opp['symbol']}\n"
        text += f"   ⬇️ Buy: {opp['buy_exchange']} ${opp['buy_price']:.6f}\n"
        text += f"   ⬆️ Sell: {opp['sell_exchange']} ${opp['sell_price']:.6f}\n"
        text += f"   💰 Profit: {opp['profit_percent']:.2f}%\n"
        text += f"   📊 Volume: ${opp['avg_volume']:,.0f}\n\n"
        
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
        all_exchange_data = await bot.get_all_prices_with_volume()

        symbol_specific_exchange_data = {}
        for exchange_name, data_for_exchange in all_exchange_data.items():
            normalized_symbol = bot.normalize_symbol(symbol_to_check, exchange_name)
            if normalized_symbol in data_for_exchange:
                symbol_specific_exchange_data[exchange_name] = data_for_exchange[normalized_symbol]

        is_safe, safety_reason = bot.is_symbol_safe(symbol_to_check, symbol_specific_exchange_data)

        safety_text = f"🛡️ **Security Check for {symbol_to_check}:**\n{safety_reason}\n\n"

        if not is_safe:
            await msg.edit_text(f"❌ Security check failed for **{symbol_to_check}**.\n\n{safety_text}")
            return

        found_prices = []
        for exchange_name, data_for_exchange in symbol_specific_exchange_data.items():
            price = data_for_exchange['price']
            if price > 0:
                found_prices.append((exchange_name, price))
        
        if not found_prices:
            await msg.edit_text(f"❌ **{symbol_to_check}** not found on any monitored exchange, or prices are unavailable.\n\n{safety_text}")
            return

        text = f"📈 **{symbol_to_check} Prices Across Exchanges**\n\n"
        
        found_prices.sort(key=lambda x: x[1])
        for exchange, price in found_prices:
            text += f"• {exchange.capitalize()}: `${price:.6f}`\n"
        
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

        text += safety_text

        await msg.edit_text(text)

    except Exception as e:
        logger.error(f"Error in price_check_command for {symbol_to_check}: {e}")
        await msg.edit_text(f"❌ An error occurred while fetching prices for **{symbol_to_check}**.")


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.save_user(user.id, user.username or "")
    
    msg = await update.message.reply_text("🔄 Scanning arbitrage opportunities...")
    
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

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not found!")
        return
    
    global ADMIN_USER_ID
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
    
    if ADMIN_USER_ID == 0:
        logger.warning("ADMIN_USER_ID not set! Admin commands will not work.")
    
    app = Application.builder().token(TOKEN).post_init(start_background_tasks).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("addpremium", add_premium_command))
    app.add_handler(CommandHandler("removepremium", remove_premium_command))
    app.add_handler(CommandHandler("listpremium", list_premium_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("admincheck", admin_check_command))
    app.add_handler(CommandHandler("price", price_check_command))
    
    app.add_handler(CommandHandler("createaffiliate", create_affiliate_command))
    app.add_handler(CommandHandler("affiliatestats", affiliate_stats_command))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_license_activation))
    
    app.add_handler(CallbackQueryHandler(button_handler))

    try:
        logger.info("Starting bot in polling mode...")
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}")
    finally:
        logger.info("Bot stopped")
        
    
if __name__ == '__main__':
    main()
