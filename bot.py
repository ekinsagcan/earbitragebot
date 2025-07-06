import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional
import aiohttp
from aiohttp import TCPConnector
import psycopg2
from urllib.parse import urlparse, parse_qs
import time
from threading import Lock
import uuid
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
        
        # Suspicious symbols
        self.suspicious_symbols = {
            'SUN', 'MOON', 'DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BABY',
            'SAFE', 'MINI', 'MICRO', 'MEGA', 'SUPER', 'ULTRA', 'ELON',
            'MARS', 'ROCKET', 'DIAMOND', 'GOLD', 'SILVER', 'TITAN',
            'RISE', 'FIRE', 'ICE', 'SNOW', 'STORM', 'THUNDER', 'LIGHTNING'
        }
        
        # Symbol mapping
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
        
        # Thresholds
        self.min_volume_threshold = 100000
        self.max_profit_threshold = 20.0
        self.free_user_max_profit = 2.0
        self.admin_max_profit_threshold = 40.0

        # Database connection
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        if not self.DATABASE_URL:
            logger.error("DATABASE_URL environment variable not found!")
            raise ValueError("DATABASE_URL must be set for database connection.")

        self.conn = None
        self.init_database()
        self.load_premium_users()
        self.load_used_license_keys()
        self.load_affiliates()

        # Cache system
        self.cache_data = {}
        self.cache_timestamp = 0
        self.cache_duration = 30
        self.cache_lock = Lock()
        
        # API request limits
        self.is_fetching = False
        self.last_fetch_time = 0
        self.min_fetch_interval = 15

        # Connection pool
        self.connector = TCPConnector(
            limit=50,
            limit_per_host=5,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        self.session = None
        
        # Request semaphore
        self.request_semaphore = asyncio.Semaphore(10)
        
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_requests': 0,
            'concurrent_users': 0
        }

        # Affiliate tracking
        self.affiliates = {}  # affiliate_id: {name, user_id, date_added, referred_users, activated_licenses}
        self.user_affiliate_map = {}  # user_id: affiliate_id

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

    def init_database(self):
        """Initialize PostgreSQL database tables."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Existing tables
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        subscription_end DATE,
                        is_premium BOOLEAN DEFAULT FALSE,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        affiliate_id TEXT,
                        FOREIGN KEY (affiliate_id) REFERENCES affiliates(affiliate_id)
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
                # New tables for affiliate system
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS affiliates (
                        affiliate_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        user_id BIGINT,
                        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        referred_users INT DEFAULT 0,
                        activated_licenses INT DEFAULT 0
                    )
                ''')
                # Table for admin messages
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS admin_messages (
                        id SERIAL PRIMARY KEY,
                        admin_id BIGINT,
                        message_text TEXT,
                        target_type TEXT, -- 'all', 'free', 'premium', 'specific'
                        target_user_id BIGINT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Table for user activity tracking
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS user_activity (
                        user_id BIGINT,
                        activity_date DATE,
                        command_count INT DEFAULT 0,
                        PRIMARY KEY (user_id, activity_date)
                    )
                ''')
            conn.commit()
            logger.info("PostgreSQL tables initialized or already exist.")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()

    def load_affiliates(self):
        """Load affiliates from database into memory."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('SELECT affiliate_id, name, user_id, date_added, referred_users, activated_licenses FROM affiliates')
                results = cursor.fetchall()
                for row in results:
                    self.affiliates[row[0]] = {
                        'name': row[1],
                        'user_id': row[2],
                        'date_added': row[3],
                        'referred_users': row[4],
                        'activated_licenses': row[5]
                    }
                
                # Load user-affiliate mapping
                cursor.execute('SELECT user_id, affiliate_id FROM users WHERE affiliate_id IS NOT NULL')
                results = cursor.fetchall()
                for row in results:
                    self.user_affiliate_map[row[0]] = row[1]
                
                logger.info(f"Loaded {len(self.affiliates)} affiliates and {len(self.user_affiliate_map)} user-affiliate mappings")
        except Exception as e:
            logger.error(f"Error loading affiliates: {e}")

    def create_affiliate(self, name: str, user_id: Optional[int] = None) -> str:
        """Create a new affiliate and return the affiliate ID."""
        affiliate_id = str(uuid.uuid4())
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO affiliates (affiliate_id, name, user_id)
                    VALUES (%s, %s, %s)
                ''', (affiliate_id, name, user_id))
            conn.commit()
            
            self.affiliates[affiliate_id] = {
                'name': name,
                'user_id': user_id,
                'date_added': datetime.now(),
                'referred_users': 0,
                'activated_licenses': 0
            }
            
            logger.info(f"Created new affiliate: {name} (ID: {affiliate_id})")
            return affiliate_id
        except Exception as e:
            logger.error(f"Error creating affiliate: {e}")
            conn.rollback()
            return ""

    def track_referral(self, user_id: int, affiliate_id: str):
        """Track a user referral by an affiliate."""
        if affiliate_id not in self.affiliates:
            logger.warning(f"Invalid affiliate ID: {affiliate_id}")
            return
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Update user's affiliate reference
                cursor.execute('''
                    UPDATE users SET affiliate_id = %s 
                    WHERE user_id = %s AND affiliate_id IS NULL
                ''', (affiliate_id, user_id))
                
                # Only count if this is a new referral
                if cursor.rowcount > 0:
                    # Update affiliate stats
                    cursor.execute('''
                        UPDATE affiliates SET referred_users = referred_users + 1 
                        WHERE affiliate_id = %s
                    ''', (affiliate_id,))
                    
                    # Update in-memory cache
                    self.affiliates[affiliate_id]['referred_users'] += 1
                    self.user_affiliate_map[user_id] = affiliate_id
                    
                    conn.commit()
                    logger.info(f"Tracked referral for user {user_id} by affiliate {affiliate_id}")
        except Exception as e:
            logger.error(f"Error tracking referral: {e}")
            conn.rollback()

    def track_license_activation(self, user_id: int):
        """Track a license activation for affiliate tracking."""
        if user_id not in self.user_affiliate_map:
            return
        
        affiliate_id = self.user_affiliate_map[user_id]
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE affiliates SET activated_licenses = activated_licenses + 1 
                    WHERE affiliate_id = %s
                ''', (affiliate_id,))
                
                # Update in-memory cache
                self.affiliates[affiliate_id]['activated_licenses'] += 1
                
                conn.commit()
                logger.info(f"Tracked license activation for user {user_id} by affiliate {affiliate_id}")
        except Exception as e:
            logger.error(f"Error tracking license activation: {e}")
            conn.rollback()

    def get_affiliate_stats(self, affiliate_id: str) -> Optional[Dict]:
        """Get affiliate statistics."""
        if affiliate_id not in self.affiliates:
            return None
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE affiliate_id = %s AND is_premium = TRUE
                ''', (affiliate_id,))
                premium_conversions = cursor.fetchone()[0]
                
                return {
                    'name': self.affiliates[affiliate_id]['name'],
                    'referred_users': self.affiliates[affiliate_id]['referred_users'],
                    'activated_licenses': self.affiliates[affiliate_id]['activated_licenses'],
                    'premium_conversions': premium_conversions,
                    'conversion_rate': (premium_conversions / self.affiliates[affiliate_id]['referred_users'] * 100 
                                        if self.affiliates[affiliate_id]['referred_users'] > 0 else 0)
                }
        except Exception as e:
            logger.error(f"Error getting affiliate stats: {e}")
            return None

    def get_all_affiliates(self) -> List[Dict]:
        """Get list of all affiliates with their stats."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT a.affiliate_id, a.name, a.user_id, a.date_added, a.referred_users, a.activated_licenses,
                           COUNT(u.user_id) FILTER (WHERE u.is_premium = TRUE) as premium_conversions
                    FROM affiliates a
                    LEFT JOIN users u ON a.affiliate_id = u.affiliate_id
                    GROUP BY a.affiliate_id, a.name, a.user_id, a.date_added, a.referred_users, a.activated_licenses
                    ORDER BY a.referred_users DESC
                ''')
                results = cursor.fetchall()
                return [
                    {
                        'affiliate_id': row[0],
                        'name': row[1],
                        'user_id': row[2],
                        'date_added': row[3],
                        'referred_users': row[4],
                        'activated_licenses': row[5],
                        'premium_conversions': row[6],
                        'conversion_rate': (row[6] / row[4] * 100 if row[4] > 0 else 0)
                    } for row in results
                ]
        except Exception as e:
            logger.error(f"Error getting all affiliates: {e}")
            return []

    def log_user_activity(self, user_id: int):
        """Log user activity for statistics."""
        today = datetime.now().date()
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO user_activity (user_id, activity_date, command_count)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (user_id, activity_date) 
                    DO UPDATE SET command_count = user_activity.command_count + 1
                ''', (user_id, today))
                
                # Also update last active timestamp in users table
                cursor.execute('''
                    UPDATE users SET last_active = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                ''', (user_id,))
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging user activity: {e}")
            conn.rollback()

    def get_active_users(self, days: int = 7, limit: int = 10) -> List[Dict]:
        """Get most active users in the last N days."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT u.user_id, u.username, SUM(ua.command_count) as total_commands
                    FROM user_activity ua
                    JOIN users u ON ua.user_id = u.user_id
                    WHERE ua.activity_date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY u.user_id, u.username
                    ORDER BY total_commands DESC
                    LIMIT %s
                ''', (days, limit))
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1] or 'Unknown',
                        'activity_count': row[2]
                    } for row in results
                ]
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []

    def get_user_growth(self, days: int = 30) -> Dict:
        """Get user growth statistics."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Total users
                cursor.execute('SELECT COUNT(*) FROM users')
                total_users = cursor.fetchone()[0]
                
                # New users today
                cursor.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE added_date::date = CURRENT_DATE
                ''')
                new_users_today = cursor.fetchone()[0]
                
                # New users this week
                cursor.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE added_date >= CURRENT_DATE - INTERVAL '7 days'
                ''')
                new_users_week = cursor.fetchone()[0]
                
                # New users this month
                cursor.execute('''
                    SELECT COUNT(*) FROM users 
                    WHERE added_date >= CURRENT_DATE - INTERVAL '30 days'
                ''')
                new_users_month = cursor.fetchone()[0]
                
                # Premium users
                cursor.execute('SELECT COUNT(*) FROM premium_users')
                premium_users = cursor.fetchone()[0]
                
                # Daily growth for chart
                cursor.execute('''
                    SELECT added_date::date as day, COUNT(*) as count
                    FROM users
                    WHERE added_date >= CURRENT_DATE - INTERVAL '%s days'
                    GROUP BY day
                    ORDER BY day
                ''', (days,))
                daily_growth = cursor.fetchall()
                
                return {
                    'total_users': total_users,
                    'new_users_today': new_users_today,
                    'new_users_week': new_users_week,
                    'new_users_month': new_users_month,
                    'premium_users': premium_users,
                    'daily_growth': [{'date': row[0], 'count': row[1]} for row in daily_growth]
                }
        except Exception as e:
            logger.error(f"Error getting user growth: {e}")
            return {}

    def save_admin_message(self, admin_id: int, message_text: str, target_type: str, target_user_id: Optional[int] = None):
        """Save admin message to database."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO admin_messages (admin_id, message_text, target_type, target_user_id)
                    VALUES (%s, %s, %s, %s)
                ''', (admin_id, message_text, target_type, target_user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving admin message: {e}")
            conn.rollback()

    def get_users_to_notify(self, target_type: str, target_user_id: Optional[int] = None) -> List[int]:
        """Get list of user IDs to notify based on target type."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cursor:
                if target_type == 'all':
                    cursor.execute('SELECT user_id FROM users')
                elif target_type == 'free':
                    cursor.execute('''
                        SELECT user_id FROM users 
                        WHERE user_id NOT IN (SELECT user_id FROM premium_users)
                    ''')
                elif target_type == 'premium':
                    cursor.execute('SELECT user_id FROM premium_users')
                elif target_type == 'specific' and target_user_id:
                    return [target_user_id]
                
                results = cursor.fetchall()
                return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Error getting users to notify: {e}")
            return []

    # ... (rest of the existing ArbitrageBot methods remain unchanged) ...

# Global bot instance
bot = ArbitrageBot()

# Admin user ID
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.save_user(user.id, user.username or "")
    
    # Check for affiliate parameter
    if context.args and len(context.args) > 0:
        affiliate_id = context.args[0]
        bot.track_referral(user.id, affiliate_id)
    
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
    
    # Log user activity
    bot.log_user_activity(query.from_user.id)
    
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
    elif query.data == 'admin_messages' and query.from_user.id == ADMIN_USER_ID:
        await show_admin_messages_menu(query)
    elif query.data == 'admin_stats' and query.from_user.id == ADMIN_USER_ID:
        await show_admin_stats(query)
    elif query.data == 'admin_affiliates' and query.from_user.id == ADMIN_USER_ID:
        await show_admin_affiliates(query)
    elif query.data == 'send_to_all' and query.from_user.id == ADMIN_USER_ID:
        await prompt_admin_message(query, 'all')
    elif query.data == 'send_to_free' and query.from_user.id == ADMIN_USER_ID:
        await prompt_admin_message(query, 'free')
    elif query.data == 'send_to_premium' and query.from_user.id == ADMIN_USER_ID:
        await prompt_admin_message(query, 'premium')
    elif query.data == 'send_to_specific' and query.from_user.id == ADMIN_USER_ID:
        await prompt_admin_message(query, 'specific')
    elif query.data.startswith('affiliate_') and query.from_user.id == ADMIN_USER_ID:
        affiliate_id = query.data.replace('affiliate_', '')
        await show_affiliate_details(query, affiliate_id)

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
• /admincheck - Admin arbitrage check
• /createaffiliate <name> - Create new affiliate link
• /affiliatestats - Show affiliate statistics

📋 **Quick Actions:**""".format(
        len(bot.premium_users), 
        len(bot.exchanges), 
        len(bot.trusted_symbols)
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 List Premium Users", callback_data='list_premium')],
        [InlineKeyboardButton("📨 Send Messages", callback_data='admin_messages')],
        [InlineKeyboardButton("📊 Detailed Stats", callback_data='admin_stats')],
        [InlineKeyboardButton("👥 Affiliate System", callback_data='admin_affiliates')],
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_admin_messages_menu(query):
    text = """📨 **Admin Message Center**

Send messages to different user groups:

• All users
• Free users only
• Premium users only
• Specific user by ID/username"""

    keyboard = [
        [InlineKeyboardButton("👥 All Users", callback_data='send_to_all')],
        [InlineKeyboardButton("🆓 Free Users", callback_data='send_to_free')],
        [InlineKeyboardButton("💎 Premium Users", callback_data='send_to_premium')],
        [InlineKeyboardButton("👤 Specific User", callback_data='send_to_specific')],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def prompt_admin_message(query, target_type):
    context.user_data['admin_message_target'] = target_type
    
    if target_type == 'specific':
        await query.edit_message_text(
            "Please reply with the target user's ID or username (@username):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_messages')]])
        )
    else:
        target_name = {
            'all': 'all users',
            'free': 'free users',
            'premium': 'premium users'
        }.get(target_type, 'users')
        
        await query.edit_message_text(
            f"Please type the message you want to send to {target_name}:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_messages')]])
        )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        return
    
    target_type = context.user_data.get('admin_message_target')
    if not target_type:
        return
    
    message_text = update.message.text
    
    if target_type == 'specific':
        # First message is the user identifier
        user_input = message_text.strip()
        
        try:
            if user_input.startswith('@'):
                # Username
                username = user_input[1:]
                user_id = bot.get_user_id_by_username(username)
                if not user_id:
                    await update.message.reply_text(f"User @{username} not found.")
                    return
            else:
                # User ID
                user_id = int(user_input)
            
            context.user_data['admin_message_target_user'] = user_id
            await update.message.reply_text(
                f"Now please type the message you want to send to user {user_input}:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data='admin_messages')]])
            )
            return
        except ValueError:
            await update.message.reply_text("Invalid user ID. Please enter a numeric ID or @username.")
            return
    
    # For other target types or after getting user ID for specific user
    target_user_id = context.user_data.get('admin_message_target_user')
    
    # Save the message
    bot.save_admin_message(update.effective_user.id, message_text, target_type, target_user_id)
    
    # Get users to notify
    user_ids = bot.get_users_to_notify(target_type, target_user_id)
    
    if not user_ids:
        await update.message.reply_text("No users found to notify.")
        return
    
    # Send the message (in practice, you'd want to do this in a background task)
    success_count = 0
    for user_id in user_ids[:10]:  # Limit to 10 for demo
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 Admin Announcement:\n\n{message_text}\n\n— Admin Team"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
    
    await update.message.reply_text(
        f"Message sent to {success_count} users successfully.\n"
        f"(Total target users: {len(user_ids)})"
    )
    
    # Clean up
    if 'admin_message_target' in context.user_data:
        del context.user_data['admin_message_target']
    if 'admin_message_target_user' in context.user_data:
        del context.user_data['admin_message_target_user']

async def show_admin_stats(query):
    # User growth stats
    growth_stats = bot.get_user_growth()
    active_users = bot.get_active_users()
    
    text = """📊 **Detailed Statistics**

👥 **User Growth:**
• Total users: {}
• New today: {}
• New this week: {}
• New this month: {}
• Premium users: {}

🏆 **Most Active Users (7 days):**
""".format(
        growth_stats.get('total_users', 0),
        growth_stats.get('new_users_today', 0),
        growth_stats.get('new_users_week', 0),
        growth_stats.get('new_users_month', 0),
        growth_stats.get('premium_users', 0)
    )
    
    for i, user in enumerate(active_users[:5], 1):
        text += f"{i}. {user['username']} - {user['activity_count']} commands\n"
    
    if len(active_users) > 5:
        text += f"\n... and {len(active_users) - 5} more active users\n"
    
    # Add affiliate stats if available
    affiliates = bot.get_all_affiliates()
    if affiliates:
        text += "\n👥 **Top Affiliates:**\n"
        for i, aff in enumerate(affiliates[:3], 1):
            text += f"{i}. {aff['name']} - {aff['referred_users']} referrals ({aff['premium_conversions']} premium)\n"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data='admin_stats')],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_admin_affiliates(query):
    affiliates = bot.get_all_affiliates()
    
    if not affiliates:
        text = "👥 **Affiliate System**\n\nNo affiliates created yet."
    else:
        text = f"👥 **Affiliate System** ({len(affiliates)} affiliates)\n\n"
        for i, aff in enumerate(affiliates, 1):
            text += f"{i}. {aff['name']}\n"
            text += f"   └ Referrals: {aff['referred_users']} (Premium: {aff['premium_conversions']})\n"
            text += f"   └ Conversion: {aff['conversion_rate']:.1f}%\n"
            text += f"   └ ID: {aff['affiliate_id']}\n\n"
    
    keyboard = []
    
    # Add buttons for each affiliate (max 5)
    for aff in affiliates[:5]:
        keyboard.append([InlineKeyboardButton(
            f"🔍 {aff['name']} ({aff['referred_users']})", 
            callback_data=f'affiliate_{aff['affiliate_id']}'
        )])
    
    keyboard.extend([
        [InlineKeyboardButton("➕ Create New Affiliate", callback_data='create_affiliate')],
        [InlineKeyboardButton("🔙 Admin Panel", callback_data='admin')]
    ])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_affiliate_details(query, affiliate_id):
    stats = bot.get_affiliate_stats(affiliate_id)
    if not stats:
        await query.answer("Affiliate not found!", show_alert=True)
        return
    
    text = f"""🔍 **Affiliate Details: {stats['name']}**

📊 **Statistics:**
• Total Referrals: {stats['referred_users']}
• Activated Licenses: {stats['activated_licenses']}
• Premium Conversions: {stats['premium_conversions']}
• Conversion Rate: {stats['conversion_rate']:.1f}%

🔗 **Affiliate Link:**
https://t.me/your_bot_username?start={affiliate_id}

📝 **Instructions:**
Share this link with your audience. When users click it and start the bot, they'll be tracked as your referrals."""
    
    keyboard = [
        [InlineKeyboardButton("🔙 Affiliate List", callback_data='admin_affiliates')],
        [InlineKeyboardButton("👑 Admin Panel", callback_data='admin')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def create_affiliate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /createaffiliate <name> [user_id]\nExample: /createaffiliate CryptoInfluencer 123456789")
        return
    
    name = ' '.join(context.args[:-1]) if len(context.args) > 1 else context.args[0]
    user_id = int(context.args[-1]) if len(context.args) > 1 and context.args[-1].isdigit() else None
    
    affiliate_id = bot.create_affiliate(name, user_id)
    if affiliate_id:
        await update.message.reply_text(
            f"✅ Affiliate '{name}' created successfully!\n\n"
            f"🔗 Affiliate Link:\n"
            f"https://t.me/your_bot_username?start={affiliate_id}\n\n"
            f"Share this link to track referrals."
        )
    else:
        await update.message.reply_text("❌ Failed to create affiliate.")

async def affiliate_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    affiliates = bot.get_all_affiliates()
    
    if not affiliates:
        await update.message.reply_text("No affiliates created yet.")
        return
    
    text = "👥 **Affiliate Statistics**\n\n"
    for i, aff in enumerate(affiliates, 1):
        text += f"{i}. {aff['name']}\n"
        text += f"   └ Referrals: {aff['referred_users']}\n"
        text += f"   └ Premium: {aff['premium_conversions']}\n"
        text += f"   └ Conversion: {aff['conversion_rate']:.1f}%\n\n"
    
    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Access denied. Admin only command.")
        return
    
    growth_stats = bot.get_user_growth()
    active_users = bot.get_active_users()
    
    text = """📊 **Bot Statistics**

👥 **Users:**
• Total users: {}
• New today: {}
• New this week: {}
• New this month: {}
• Premium users: {}
• Free users: {}

📈 **Data:**
• Exchanges monitored: {}
• Trusted symbols: {}
• Arbitrage records: {}

🏆 **Most Active Users (7 days):**
""".format(
        growth_stats.get('total_users', 0),
        growth_stats.get('new_users_today', 0),
        growth_stats.get('new_users_week', 0),
        growth_stats.get('new_users_month', 0),
        len(bot.premium_users),
        growth_stats.get('total_users', 0) - len(bot.premium_users),
        len(bot.exchanges), 
        len(bot.trusted_symbols),
        "..."
    )
    
    for i, user in enumerate(active_users[:5], 1):
        text += f"{i}. {user['username']} - {user['activity_count']} commands\n"
    
    await update.message.reply_text(text)

# ... (rest of the existing command handlers remain unchanged) ...

async def handle_license_activation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle license key messages"""
    user = update.effective_user
    license_key = update.message.text.strip()
    
    # Debug: License key format check
    logger.info(f"Received license key from user {user.id}: '{license_key}'")
    logger.info(f"License key length: {len(license_key)}")
    
    # License key format check
    if not license_key or len(license_key) < 10:
        logger.info("License key too short, ignoring")
        return
    
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
    
    # Track license activation for affiliate
    bot.track_license_activation(user.id)
    
    await update.message.reply_text(
        "✅ **License Activated Successfully!**\n\n"
        "🎉 Welcome to Premium Membership!\n"
        "📅 Valid for: 30 days\n"
        "💎 All premium features are now active\n\n"
        "Use /start to see your premium status!"
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
    app.add_handler(CommandHandler("price", price_check_command))
    app.add_handler(CommandHandler("createaffiliate", create_affiliate_command))
    app.add_handler(CommandHandler("affiliatestats", affiliate_stats_command))
    
    # Message handlers
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_license_activation
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(ADMIN_USER_ID),
        handle_admin_message
    ))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(button_handler))

    async def cleanup():
        if bot.session and not bot.session.closed:
            await bot.session.close()
        if bot.conn and not bot.conn.closed:
            bot.conn.close()
            logger.info("PostgreSQL database connection closed.")
    
    app.post_stop = cleanup
    
    logger.info("Advanced Arbitrage Bot starting...")
    logger.info(f"Monitoring {len(bot.exchanges)} exchanges")
    logger.info(f"Tracking {len(bot.trusted_symbols)} trusted symbols")
    logger.info(f"Premium users loaded: {len(bot.premium_users)}")
    
    app.run_polling()

if __name__ == '__main__':
    main()
