import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Set, Optional
import aiohttp
from aiohttp import TCPConnector
import psycopg2
from urllib.parse import urlparse
import time
from threading import Lock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error # Import error for TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from uuid import uuid4 # New import for unique affiliate codes
import random # New import for unique affiliate codes

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

# Admin User ID (from environment variable)
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
if not ADMIN_USER_ID:
    logger.error("ADMIN_USER_ID environment variable not set. Admin features will not work.")
    ADMIN_USER_ID = "0" # Default to a non-existent ID

# Database URL (from environment variable)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL environment variable not set. Database features will not work.")

class ArbitrageBot:
    def __init__(self):
        # Major cryptocurrency exchanges with their APIs
        self.exchanges = {
            'binance': 'https://api.binance.com/api/v3/ticker/24hr',
            'kucoin': 'https://api.kucoin.com/api/v1/market/allTickers',
            'gate': 'https://api.gateio.ws/api/v4/spot/tickers',
            'bybit': 'https://api.bybit.com/v2/public/tickers',
            'okx': 'https://www.okx.com/api/v5/market/tickers?instType=SPOT',
            'huobi': 'https://api.huobi.pro/market/tickers',
            'kraken': 'https://api.kraken.com/0/public/Ticker',
            'coinbase': 'https://api.coinbase.com/v2/exchange-rates?currency=USDT', # Requires specific handling
            'bitget': 'https://api.bitget.com/api/v2/spot/market/tickers',
            'mexc': 'https://api.mexc.com/api/v3/ticker/24hr',
            'bitmart': 'https://api-cloud.bitmart.com/spot/v1/ticker',
            'binance_us': 'https://api.binance.us/api/v3/ticker/24hr',
            'coinex': 'https://api.coinex.com/v1/market/ticker/all',
            'lbank': 'https://api.lbank.com/v2/currency/ticker.do', # Requires handling for multiple symbols
            'digifinex': 'https://openapi.digifinex.com/v3/ticker',
            'bitfinex': 'https://api-pub.bitfinex.com/v2/tickers?symbols=ALL', # Requires specific handling
            'ascendex': 'https://ascendex.com/api/pro/v1/spot/ticker',
            'cryptocom': 'https://api.crypto.com/exchange/v1/public/get-ticker',
            'bithumb': 'https://api.bithumb.com/public/ticker/ALL_KRW', # KRW pairs
            'phemex': 'https://api.phemex.com/v1/market/tickers',
            'bingx': 'https://api.bingx.com/api/v1/market/tickers',
            'whitebit': 'https://api.whitebit.com/api/v2/public/ticker',
            'upbit': 'https://api.upbit.com/v1/tickers?markets=ALL', # KRW pairs
            'bitstamp': 'https://www.bitstamp.net/api/v2/tickers/',
            'xtcom': 'https://api.xt.com/data/api/v1/ticker/all',
            'woo': 'https://api.woo.org/v1/public/info',
            'dydx': 'https://api.dydx.exchange/v3/markets',
            'gateio_futures': 'https://api.gateio.ws/api/v4/futures/usdt/tickers',
            'bybit_futures': 'https://api.bybit.com/derivatives/v3/public/tickers',
            'okx_futures': 'https://www.okx.com/api/v5/market/tickers?instType=SWAP',
        }
        self.ticker_data: Dict[str, Dict[str, float]] = {} # {exchange: {symbol: price}}
        self.volume_data: Dict[str, Dict[str, float]] = {} # {exchange: {symbol: volume}}
        self.last_fetched_time = 0
        self.data_lock = Lock()
        self.session: Optional[aiohttp.ClientSession] = None

        self.trusted_symbols = {
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT',
            'SHIBUSDT', 'AVAXUSDT', 'DOTUSDT', 'TRXUSDT', 'LINKUSDT', 'MATICUSDT', 'LTCUSDT',
            'BCHUSDT', 'NEARUSDT', 'APTUSDT', 'ETCUSDT', 'XLMUSDT', 'ATOMUSDT', 'UNIUSDT',
            'XMRUSDT', 'ALGOUSDT', 'EOSUSDT', 'FILUSDT', 'VETUSDT', 'THETAUSDT', 'AXSUSDT',
            'SANDUSDT', 'GRTUSDT', 'EGLDUSDT', 'FTMUSDT', 'ZECUSDT', 'IOTAUSDT', 'CHZUSDT',
            'MANAUSDT', 'ENJUSDT', 'CRVUSDT', 'COMPUSDT', 'AAVEUSDT', 'MKRUSDT', 'SNXUSDT',
            'YFIUSDT', 'UMAUSDT', 'SUSHIUSDT', 'RENUSDT', 'OMGUSDT', 'BATUSDT', 'KSMUSDT',
            'DOTUSDT', 'ICPUSDT', 'OPUSDT', 'ARBCHUSDT', 'SUIUSDT', 'SEIUSDT', 'TIAUSDT',
            'BONKUSDT', 'WIFUSDT', 'FLOKIUSDT'
        }

        self.suspicious_keywords = {'shib', 'pepe', 'doge', 'floki', 'bonk', 'wif', 'elon', 'moon', 'safemoon', 'baby', 'cat', 'inu', 'pump'}

        self.premium_users: Dict[int, datetime] = {}
        self.used_license_keys: Set[str] = set()

        # New: Affiliate related data
        self.affiliates: Dict[str, Dict[str, str]] = {} # link_code -> {name, affiliate_id}

        self.conn = None
        self.cursor = None
        self._init_db()

    def _init_db(self):
        try:
            parsed_url = urlparse(DATABASE_URL)
            self.conn = psycopg2.connect(
                database=parsed_url.path[1:],
                user=parsed_url.username,
                password=parsed_url.password,
                host=parsed_url.hostname,
                port=parsed_url.port
            )
            self.cursor = self.conn.cursor()

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    last_activity TIMESTAMP DEFAULT NOW(),
                    last_check_time TIMESTAMP
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS premium_users (
                    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
                    username VARCHAR(255),
                    expiry_date TIMESTAMP
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS license_keys (
                    license_key VARCHAR(255) PRIMARY KEY,
                    used_at TIMESTAMP DEFAULT NOW()
                );
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS arbitrage_data (
                    id SERIAL PRIMARY KEY,
                    buy_exchange VARCHAR(255),
                    sell_exchange VARCHAR(255),
                    symbol VARCHAR(50),
                    buy_price NUMERIC,
                    sell_price NUMERIC,
                    profit_percentage NUMERIC,
                    volume_usd NUMERIC,
                    timestamp TIMESTAMP DEFAULT NOW()
                );
            """)

            # Ensure all users have last_activity column
            self.cursor.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP DEFAULT NOW();
            """)
            # Ensure all users have last_check_time column
            self.cursor.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS last_check_time TIMESTAMP;
            """)
            # Ensure affiliates table exists
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS affiliates (
                    affiliate_id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    link_code VARCHAR(255) UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            # Ensure users table has referred_by and referred_at columns
            self.cursor.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by VARCHAR(255) REFERENCES affiliates(link_code);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_at TIMESTAMP;
            """)
            # Ensure affiliate_activations table exists
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS affiliate_activations (
                    activation_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(user_id),
                    affiliate_link_code VARCHAR(255) NOT NULL REFERENCES affiliates(link_code),
                    activation_date TIMESTAMP DEFAULT NOW()
                );
            """)
            self.conn.commit()

            # Load premium users
            self.cursor.execute("SELECT user_id, expiry_date FROM premium_users")
            for user_id, expiry_date in self.cursor.fetchall():
                self.premium_users[user_id] = expiry_date
            logger.info(f"Loaded {len(self.premium_users)} premium users.")

            # Load used license keys
            self.cursor.execute("SELECT license_key FROM license_keys")
            for (license_key,) in self.cursor.fetchall():
                self.used_license_keys.add(license_key)
            logger.info(f"Loaded {len(self.used_license_keys)} used license keys.")

            # Load affiliates
            self.cursor.execute("SELECT link_code, name, affiliate_id FROM affiliates")
            for link_code, name, affiliate_id in self.cursor.fetchall():
                self.affiliates[link_code] = {"name": name, "affiliate_id": affiliate_id}
            logger.info(f"Loaded {len(self.affiliates)} affiliates.")

        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            # Optionally exit or retry if DB is critical

    def save_user(self, user_id: int, username: str, referred_by: Optional[str] = None):
        try:
            self.cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
            if not self.cursor.fetchone():
                if referred_by:
                    self.cursor.execute(
                        "INSERT INTO users (user_id, username, last_activity, referred_by, referred_at) VALUES (%s, %s, NOW(), %s, NOW())",
                        (user_id, username, referred_by)
                    )
                    logger.info(f"New user {username} ({user_id}) referred by {referred_by} saved to DB.")
                else:
                    self.cursor.execute(
                        "INSERT INTO users (user_id, username, last_activity) VALUES (%s, %s, NOW())",
                        (user_id, username)
                    )
                    logger.info(f"New user {username} ({user_id}) saved to DB.")
            else:
                # Always update last_activity on interaction
                self.cursor.execute(
                    "UPDATE users SET username = %s, last_activity = NOW() WHERE user_id = %s",
                    (username, user_id)
                )
                logger.debug(f"User {username} ({user_id}) activity updated.")
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving user {username} ({user_id}) to DB: {e}")

    def add_used_license_key(self, license_key: str):
        try:
            if license_key not in self.used_license_keys:
                self.used_license_keys.add(license_key)
                self.cursor.execute("INSERT INTO license_keys (license_key) VALUES (%s)", (license_key,))
                self.conn.commit()
                logger.info(f"License key {license_key} added to used keys.")
            else:
                logger.warning(f"Attempted to add already used license key: {license_key}")
        except Exception as e:
            logger.error(f"Error adding used license key {license_key}: {e}")

    def remove_used_license_key(self, license_key: str):
        try:
            if license_key in self.used_license_keys:
                self.used_license_keys.remove(license_key)
                self.cursor.execute("DELETE FROM license_keys WHERE license_key = %s", (license_key,))
                self.conn.commit()
                logger.info(f"License key {license_key} removed from used keys.")
            else:
                logger.warning(f"Attempted to remove non-existent license key: {license_key}")
        except Exception as e:
            logger.error(f"Error removing used license key {license_key}: {e}")

    def is_premium(self, user_id: int) -> bool:
        expiry_date = self.premium_users.get(user_id)
        if expiry_date and expiry_date > datetime.now():
            return True
        return False

    def set_user_premium(self, user_id: int, username: str, expiry_date: datetime):
        try:
            self.premium_users[user_id] = expiry_date
            self.cursor.execute(
                "INSERT INTO premium_users (user_id, username, expiry_date) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, expiry_date = EXCLUDED.expiry_date",
                (user_id, username, expiry_date)
            )
            # Check if referred and record affiliate activation
            self.cursor.execute("SELECT referred_by FROM users WHERE user_id = %s", (user_id,))
            result = self.cursor.fetchone()
            if result and result[0]:
                referred_by_code = result[0]
                self.cursor.execute(
                    "INSERT INTO affiliate_activations (user_id, affiliate_link_code, activation_date) VALUES (%s, %s, NOW())",
                    (user_id, referred_by_code)
                )
                logger.info(f"Recorded premium activation for user {user_id} from affiliate {referred_by_code}.")
            self.conn.commit()
            logger.info(f"User {username} ({user_id}) premium status set until {expiry_date}.")
        except Exception as e:
            logger.error(f"Error setting premium status for user {user_id}: {e}")

    def remove_user_premium(self, user_id: int):
        try:
            if user_id in self.premium_users:
                del self.premium_users[user_id]
            self.cursor.execute("DELETE FROM premium_users WHERE user_id = %s", (user_id,))
            self.conn.commit()
            logger.info(f"User {user_id} premium status removed.")
        except Exception as e:
            logger.error(f"Error removing premium status for user {user_id}: {e}")

    def save_arbitrage_opportunity(self, buy_exchange: str, sell_exchange: str, symbol: str, buy_price: float, sell_price: float, profit_percentage: float, volume_usd: float):
        try:
            self.cursor.execute(
                "INSERT INTO arbitrage_data (buy_exchange, sell_exchange, symbol, buy_price, sell_price, profit_percentage, volume_usd) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (buy_exchange, sell_exchange, symbol, buy_price, sell_price, profit_percentage, volume_usd)
            )
            self.conn.commit()
            logger.debug(f"Arbitrage opportunity for {symbol} saved.")
        except Exception as e:
            logger.error(f"Error saving arbitrage opportunity to DB: {e}")

    async def get_exchange_data(self, session: aiohttp.ClientSession, exchange_name: str, api_url: str) -> Dict:
        try:
            async with session.get(api_url, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.warning(f"Failed to fetch data from {exchange_name}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error for {exchange_name}: {e}")
            return {}

    def normalize_symbol(self, symbol: str) -> str:
        """Normalizes a cryptocurrency symbol to a consistent format (e.g., BTCUSDT)."""
        symbol = symbol.replace('/', '').replace('-', '').replace('_', '').upper()
        if symbol.endswith('USDT') or symbol.endswith('BUSD'): # Ensure common stablecoins are base
             return symbol
        # Attempt to reorder if it seems like base/quote is reversed and USDT is in it
        if 'USDT' in symbol and not symbol.endswith('USDT'):
            if symbol.startswith('USDT'):
                return symbol[4:] + 'USDT' # e.g. USDTBTC -> BTCUSDT
            # More complex cases for partial matches
            for base in ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE']:
                if base in symbol and 'USDT' in symbol:
                    if symbol.startswith(base) and len(symbol) > len(base) + 4: # e.g. BTCUSDT (already good)
                        pass
                    elif symbol.endswith(base) and len(symbol) > len(base) + 4: # e.g. USDTBTC
                        return symbol.replace(base, '') + base # USDTBTC -> BTCUSDT
        return symbol

    async def fetch_all_tickers(self):
        logger.info("Fetching ticker data from all exchanges...")
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(connector=TCPConnector(limit=50)) # Limit concurrent connections

        tasks = []
        for exchange, url in self.exchanges.items():
            tasks.append(self.get_exchange_data(self.session, exchange, url))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        new_ticker_data: Dict[str, Dict[str, float]] = {}
        new_volume_data: Dict[str, Dict[str, float]] = {}

        for i, exchange_name in enumerate(self.exchanges.keys()):
            data = results[i]
            if isinstance(data, Exception):
                logger.warning(f"Skipping {exchange_name} due to fetch error: {data}")
                continue

            exchange_tickers: Dict[str, float] = {}
            exchange_volumes: Dict[str, float] = {}

            if exchange_name == 'binance' or exchange_name == 'binance_us' or exchange_name == 'mexc':
                for ticker in data:
                    symbol = self.normalize_symbol(ticker.get('symbol', ''))
                    if 'lastPrice' in ticker and 'quoteVolume' in ticker:
                        try:
                            price = float(ticker['lastPrice'])
                            volume = float(ticker['quoteVolume'])
                            exchange_tickers[symbol] = price
                            exchange_volumes[symbol] = volume
                        except ValueError:
                            continue
            elif exchange_name == 'kucoin':
                if 'data' in data and 'ticker' in data['data']:
                    for ticker in data['data']['ticker']:
                        symbol = self.normalize_symbol(ticker.get('symbol', ''))
                        if 'last' in ticker and 'volValue' in ticker:
                            try:
                                price = float(ticker['last'])
                                volume = float(ticker['volValue'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'gate':
                for ticker in data:
                    symbol = self.normalize_symbol(ticker.get('currency_pair', ''))
                    if 'last' in ticker and 'quote_volume' in ticker:
                        try:
                            price = float(ticker['last'])
                            volume = float(ticker['quote_volume'])
                            exchange_tickers[symbol] = price
                            exchange_volumes[symbol] = volume
                        except ValueError:
                            continue
            elif exchange_name == 'bybit' or exchange_name == 'bybit_futures':
                if 'result' in data and 'list' in data['result']: # For V5 (Unified)
                    for ticker in data['result']['list']:
                        symbol = self.normalize_symbol(ticker.get('symbol', ''))
                        if 'lastPrice' in ticker and 'volume24h' in ticker: # For V5
                            try:
                                price = float(ticker['lastPrice'])
                                volume = float(ticker['volume24h'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
                elif 'result' in data and 'kline' in data['result']: # For V2
                    for ticker in data['result']:
                        symbol = self.normalize_symbol(ticker.get('symbol', ''))
                        if 'last_price' in ticker and 'volume_24h' in ticker:
                            try:
                                price = float(ticker['last_price'])
                                volume = float(ticker['volume_24h'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'okx' or exchange_name == 'okx_futures':
                if 'data' in data:
                    for ticker in data['data']:
                        symbol = self.normalize_symbol(ticker.get('instId', ''))
                        if 'last' in ticker and 'volCcy24h' in ticker:
                            try:
                                price = float(ticker['last'])
                                volume = float(ticker['volCcy24h'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'huobi':
                if 'data' in data:
                    for symbol_key, ticker in data['data'].items():
                        symbol = self.normalize_symbol(symbol_key)
                        if 'close' in ticker and 'amount' in ticker:
                            try:
                                price = float(ticker['close'])
                                volume = float(ticker['amount'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'kraken':
                for pair, ticker in data.get('result', {}).items():
                    # Kraken symbols are like XBTUSDT, not BTCUSDT
                    symbol = self.normalize_symbol(pair.replace('XBT', 'BTC').replace('XDG', 'DOGE'))
                    if 'c' in ticker and 'v' in ticker: # c = last trade closed, v = 24h volume
                        try:
                            price = float(ticker['c'][0])
                            volume = float(ticker['v'][1]) # v[0] is today, v[1] is last 24h
                            exchange_tickers[symbol] = price
                            exchange_volumes[symbol] = volume
                        except ValueError:
                            continue
            elif exchange_name == 'coinbase':
                # Coinbase's API is different, it gives rates for a base currency against others.
                # We need to query for each symbol separately or infer.
                # For simplicity, we'll assume USDT is the target and fetch BTC, ETH, etc. against USDT
                # This part is simplified and might not cover all pairs.
                if 'data' in data and 'rates' in data['data']:
                    usdt_rate = float(data['data']['rates'].get('USDT', 1))
                    if usdt_rate == 0:
                        continue
                    for currency, rate in data['data']['rates'].items():
                        if currency == 'USDT': continue
                        symbol = self.normalize_symbol(currency + 'USDT')
                        try:
                            # Rates are base/quote, so USDT/BTC rate would be 1/BTC price in USDT
                            price = 1 / float(rate) * usdt_rate # price of currency in USDT
                            # Coinbase doesn't provide 24h volume easily from this endpoint
                            exchange_tickers[symbol] = price
                            exchange_volumes[symbol] = 1 # Placeholder volume
                        except ValueError:
                            continue
            elif exchange_name == 'bitget':
                if 'data' in data:
                    for ticker in data['data']:
                        symbol = self.normalize_symbol(ticker.get('symbol', ''))
                        if 'lastPr' in ticker and 'quoteVolume' in ticker:
                            try:
                                price = float(ticker['lastPr'])
                                volume = float(ticker['quoteVolume'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'bitmart':
                if 'data' in data and 'tickers' in data['data']:
                    for ticker in data['data']['tickers']:
                        symbol = self.normalize_symbol(ticker.get('symbol', ''))
                        if 'last_price' in ticker and 'volume' in ticker:
                            try:
                                price = float(ticker['last_price'])
                                volume = float(ticker['volume'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'coinex':
                if 'data' in data and 'ticker' in data['data']:
                    for symbol_raw, ticker in data['data']['ticker'].items():
                        symbol = self.normalize_symbol(symbol_raw)
                        if 'last' in ticker and 'vol' in ticker:
                            try:
                                price = float(ticker['last'])
                                volume = float(ticker['vol'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'lbank':
                if 'data' in data and 'ticker' in data['data']:
                    for ticker_item in data['data']['ticker']:
                        symbol = self.normalize_symbol(ticker_item.get('symbol', '').replace('_', ''))
                        if 'latest' in ticker_item and 'vol' in ticker_item:
                            try:
                                price = float(ticker_item['latest'])
                                volume = float(ticker_item['vol'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'digifinex':
                if 'ticker' in data:
                    for ticker_item in data['ticker']:
                        symbol = self.normalize_symbol(ticker_item.get('symbol', '').replace('_', ''))
                        if 'last' in ticker_item and 'vol_24h' in ticker_item:
                            try:
                                price = float(ticker_item['last'])
                                volume = float(ticker_item['vol_24h'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'bitfinex':
                for ticker_item in data:
                    if len(ticker_item) >= 8 and isinstance(ticker_item[0], str): # Check if it's a valid ticker
                        symbol = self.normalize_symbol(ticker_item[0].replace('t', '')) # Remove 't' prefix
                        if len(ticker_item) > 7:
                            try:
                                price = float(ticker_item[7]) # Last price
                                volume = float(ticker_item[8]) # 24h volume
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except (ValueError, IndexError):
                                continue
            elif exchange_name == 'ascendex':
                if 'data' in data:
                    for ticker in data['data']:
                        symbol = self.normalize_symbol(ticker.get('symbol', ''))
                        if 'close' in ticker and 'volume' in ticker:
                            try:
                                price = float(ticker['close'])
                                volume = float(ticker['volume'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'cryptocom':
                if 'result' in data and 'data' in data['result']:
                    for ticker in data['result']['data']:
                        symbol = self.normalize_symbol(ticker.get('i', ''))
                        if 'a' in ticker and 'v' in ticker: # a is bid, b is ask, a is often last price
                            try:
                                price = float(ticker['a']) # Using ask as last price, or can use 'l' for last
                                volume = float(ticker['v'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'bithumb':
                if 'data' in data:
                    for key, value in data['data'].items():
                        if key == 'date': continue # Skip date field
                        symbol = self.normalize_symbol(key + 'KRW') # Assume KRW base
                        if 'closing_price' in value and 'acc_trade_value_24H' in value:
                            try:
                                price = float(value['closing_price'])
                                volume = float(value['acc_trade_value_24H'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'phemex':
                if 'data' in data and 'tickers' in data['data']:
                    for ticker_item in data['data']['tickers']:
                        symbol = self.normalize_symbol(ticker_item.get('symbol', ''))
                        if 'last_ep' in ticker_item and 'volume_ev' in ticker_item: # last_ep is last price in USD
                            try:
                                price = float(ticker_item['last_ep']) * 10**(-8) # Phemex returns price * 1e8
                                volume = float(ticker_item['volume_ev']) * 10**(-8) # Volume also needs adjustment
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'bingx':
                if 'data' in data and 'tickers' in data['data']:
                    for ticker_item in data['data']['tickers']:
                        symbol = self.normalize_symbol(ticker_item.get('symbol', ''))
                        if 'lastPrice' in ticker_item and 'volume' in ticker_item:
                            try:
                                price = float(ticker_item['lastPrice'])
                                volume = float(ticker_item['volume'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'whitebit':
                for symbol_raw, ticker_item in data.items():
                    symbol = self.normalize_symbol(symbol_raw)
                    if 'last_price' in ticker_item and 'quote_volume_24h' in ticker_item:
                        try:
                            price = float(ticker_item['last_price'])
                            volume = float(ticker_item['quote_volume_24h'])
                            exchange_tickers[symbol] = price
                            exchange_volumes[symbol] = volume
                        except ValueError:
                            continue
            elif exchange_name == 'upbit':
                # Upbit returns a list of tickers, each with market_code
                for ticker_item in data:
                    # Upbit markets are like KRW-BTC, normalize to BTCKRW
                    market = ticker_item.get('market', '')
                    if '-' in market:
                        base, quote = market.split('-')
                        symbol = self.normalize_symbol(quote + base) # e.g., KRW-BTC -> BTCKRW
                    else:
                        symbol = self.normalize_symbol(market)

                    if 'trade_price' in ticker_item and 'acc_trade_price_24h' in ticker_item:
                        try:
                            price = float(ticker_item['trade_price'])
                            volume = float(ticker_item['acc_trade_price_24h'])
                            exchange_tickers[symbol] = price
                            exchange_volumes[symbol] = volume
                        except ValueError:
                            continue
            elif exchange_name == 'bitstamp':
                if isinstance(data, list):
                    for ticker_item in data:
                        symbol_raw = ticker_item.get('pair', '') # e.g., btcusd
                        if symbol_raw:
                            symbol = self.normalize_symbol(symbol_raw + 'T') # Assuming USDT equivalent if USD
                            if 'last' in ticker_item and 'volume' in ticker_item:
                                try:
                                    price = float(ticker_item['last'])
                                    volume = float(ticker_item['volume'])
                                    exchange_tickers[symbol] = price
                                    exchange_volumes[symbol] = volume
                                except ValueError:
                                    continue
            elif exchange_name == 'xtcom':
                if 'data' in data:
                    for ticker_item in data['data']:
                        symbol = self.normalize_symbol(ticker_item.get('s', ''))
                        if 'c' in ticker_item and 'v' in ticker_item: # c = close price, v = volume
                            try:
                                price = float(ticker_item['c'])
                                volume = float(ticker_item['v'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'woo':
                if 'success' in data and data['success'] and 'data' in data:
                    for symbol_raw, ticker_item in data['data'].items():
                        symbol = self.normalize_symbol(symbol_raw)
                        if 'price' in ticker_item and 'volume' in ticker_item:
                            try:
                                price = float(ticker_item['price'])
                                volume = float(ticker_item['volume'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue
            elif exchange_name == 'dydx':
                if 'markets' in data:
                    for market_name, market_data in data['markets'].items():
                        symbol = self.normalize_symbol(market_name.replace('-', '')) # e.g. BTC-USDT to BTCUSDT
                        if 'oraclePrice' in market_data and 'volume24H' in market_data:
                            try:
                                price = float(market_data['oraclePrice'])
                                volume = float(market_data['volume24H'])
                                exchange_tickers[symbol] = price
                                exchange_volumes[symbol] = volume
                            except ValueError:
                                continue

            new_ticker_data[exchange_name] = exchange_tickers
            new_volume_data[exchange_name] = exchange_volumes

        with self.data_lock:
            self.ticker_data = new_ticker_data
            self.volume_data = new_volume_data
            self.last_fetched_time = time.time()
        logger.info(f"Finished fetching ticker data. Data for {len(self.ticker_data)} exchanges updated.")


    async def refresh_data_periodically(self):
        while True:
            await self.fetch_all_tickers()
            await asyncio.sleep(30) # Refresh every 30 seconds

    def _is_suspicious_symbol(self, symbol: str) -> bool:
        """Checks if a symbol contains keywords often associated with suspicious or volatile coins."""
        lower_symbol = symbol.lower()
        return any(keyword in lower_symbol for keyword in self.suspicious_keywords)

    def _validate_arbitrage_opportunity(self, symbol: str, buy_price: float, sell_price: float,
                                        buy_exchange: str, sell_exchange: str, volume_usd: float,
                                        is_admin_check: bool = False) -> Tuple[bool, str]:
        """Applies security filters to an arbitrage opportunity."""
        if buy_price <= 0 or sell_price <= 0:
            return False, "Invalid price (zero or negative)."

        profit_percentage = ((sell_price - buy_price) / buy_price) * 100

        # Filter 1: Minimum Volume Threshold
        MIN_VOLUME_USD = 100000 # Minimum 24h trading volume in USD
        if volume_usd < MIN_VOLUME_USD:
            return False, f"Low 24h volume (${volume_usd:,.0f} < ${MIN_VOLUME_USD:,.0f})."

        # Filter 2: Maximum Profit Threshold
        MAX_PROFIT_PERCENTAGE_USER = 20.0
        MAX_PROFIT_PERCENTAGE_ADMIN = 40.0
        profit_limit = MAX_PROFIT_PERCENTAGE_ADMIN if is_admin_check else MAX_PROFIT_PERCENTAGE_USER

        if profit_percentage > profit_limit:
            return False, f"Profit too high ({profit_percentage:.2f}% > {profit_limit:.2f}%)."
        if profit_percentage < 0.1: # Minimum profitable arbitrage
            return False, "Profit too low (<0.1%)."

        # Filter 3: Trusted Symbols Check (stricter for non-trusted)
        if symbol not in self.trusted_symbols:
            # For non-trusted symbols, apply additional checks
            # Example: require higher volume or presence on more major exchanges
            if volume_usd < 500000: # Higher volume for untrusted
                 return False, f"Untrusted symbol with insufficient volume (${volume_usd:,.0f})."
            # Optional: Check if present on at least 3 major exchanges
            # This would require counting exchanges holding this symbol
            # For now, volume is a good proxy.

        # Filter 4: Suspicious Symbol Keywords (e.g., meme coins)
        if self._is_suspicious_symbol(symbol):
            # For suspicious symbols, require even higher volume and more exchanges
            if volume_usd < 1000000: # Even higher volume for suspicious coins
                return False, f"Suspicious symbol with insufficient volume (${volume_usd:,.0f})."
            # Optional: Further checks, e.g., if it's on any 'major' tier 1 exchange.

        # Filter 5: Price Ratio Reasonableness (e.g., avoid huge discrepancies indicating bad data)
        # If sell_price is more than X times buy_price, it might be bad data.
        if buy_price > 0 and (sell_price / buy_price) > 1.30: # 30% difference maximum ratio
            return False, "Unrealistic price difference (ratio > 1.30)."
        if sell_price > 0 and (buy_price / sell_price) > 1.30: # Check both ways in case of calculation error
            return False, "Unrealistic price difference (inverse ratio > 1.30)."

        return True, "Valid"


bot = ArbitrageBot()

# --- Utility Functions ---
def get_user_id_from_input(input_str: str) -> Optional[int]:
    """Tries to parse user ID from string (either direct ID or by username)."""
    try:
        user_id = int(input_str)
        return user_id
    except ValueError:
        # Not a direct ID, try to find by username
        bot.cursor.execute("SELECT user_id FROM users WHERE username = %s", (input_str.replace('@', ''),))
        result = bot.cursor.fetchone()
        if result:
            return result[0]
    return None

def update_user_last_check_time(user_id: int):
    try:
        bot.cursor.execute(
            "UPDATE users SET last_check_time = NOW() WHERE user_id = %s",
            (user_id,)
        )
        bot.conn.commit()
    except Exception as e:
        logger.error(f"Error updating last_check_time for user {user_id}: {e}")

# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"

    # Handle deep linking for affiliate referrals
    referred_by = None
    if context.args and len(context.args) > 0:
        start_payload = context.args[0]
        if start_payload.startswith("aff_"):
            referred_by = start_payload[4:] # Remove "aff_" prefix
            if referred_by not in bot.affiliates:
                logger.warning(f"Invalid affiliate link_code received: {referred_by}")
                referred_by = None # Invalidate if not a known affiliate

    bot.save_user(user_id, username, referred_by)

    is_premium = bot.is_premium(user_id)
    status_text = "💎 Premium Kullanıcı" if is_premium else "🆓 Ücretsiz Kullanıcı"
    expiry_text = ""
    if is_premium and bot.premium_users.get(user_id):
        expiry_text = f" (Sona Erme Tarihi: {bot.premium_users[user_id].strftime('%d.%m.%Y %H:%M')})"

    keyboard = [
        [InlineKeyboardButton("🔍 Arbitraj Ara", callback_data="check_arbitrage")],
        [InlineKeyboardButton("📊 Güvenilir Coinler", callback_data="trusted_coins")],
        [InlineKeyboardButton("💎 Premium Bilgi", callback_data="premium_info"),
         InlineKeyboardButton("🔑 Lisans Aktifleştir", callback_data="activate_license")],
        [InlineKeyboardButton("ℹ️ Yardım", callback_data="help")],
    ]
    if str(user_id) == ADMIN_USER_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Paneli", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Merhaba {username}!\n\nBotumuzla kripto para arbitraj fırsatlarını keşfedin.\n"
        f"Hesap Durumunuz: {status_text}{expiry_text}\n\n"
        "Aşağıdaki seçeneklerden birini seçin:",
        reply_markup=reply_markup
    )


async def find_arbitrage_opportunities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    update_user_last_check_time(user_id) # Update last check time

    await context.bot.send_message(chat_id=user_id, text="Arbitraj fırsatları aranıyor... Lütfen bekleyin.")

    is_premium = bot.is_premium(user_id)
    is_admin = (str(user_id) == ADMIN_USER_ID)
    max_opportunities = 3 if not is_premium else 10 # Limit for free users
    profit_threshold_filter = 2.0 if not is_premium else 0.1 # Minimum profit %
    max_profit_display_user = 2.0 # Max profit shown to free users to encourage premium
    max_profit_display_admin = 40.0 # Admin can see higher anomalies
    max_profit_for_display = max_profit_display_admin if is_admin else max_profit_display_user

    if time.time() - bot.last_fetched_time > 30: # Data older than 30 seconds
        await context.bot.send_message(chat_id=user_id, text="Piyasa verileri güncelleniyor, bu biraz zaman alabilir.")
        await bot.fetch_all_tickers()

    with bot.data_lock:
        current_ticker_data = bot.ticker_data
        current_volume_data = bot.volume_data

    if not current_ticker_data:
        await context.bot.send_message(chat_id=user_id, text="Şu anda piyasa verileri mevcut değil. Lütfen daha sonra tekrar deneyin.")
        return

    opportunities_found = []
    common_symbols = set()
    for exchange_tickers in current_ticker_data.values():
        common_symbols.update(exchange_tickers.keys())

    for symbol in common_symbols:
        buy_exchange, buy_price = None, float('inf')
        sell_exchange, sell_price = None, 0.0
        buy_volume, sell_volume = 0.0, 0.0

        for exchange, tickers in current_ticker_data.items():
            if symbol in tickers:
                price = tickers[symbol]
                volume = current_volume_data.get(exchange, {}).get(symbol, 0.0)

                # Find lowest buy (ask) price
                if price < buy_price:
                    buy_price = price
                    buy_exchange = exchange
                    buy_volume = volume

                # Find highest sell (bid) price
                if price > sell_price:
                    sell_price = price
                    sell_exchange = exchange
                    sell_volume = volume

        if buy_exchange and sell_exchange and buy_exchange != sell_exchange and buy_price > 0:
            profit_percentage = ((sell_price - buy_price) / buy_price) * 100

            # Determine which volume to use for validation (typically the smaller of the two for practical arb)
            volume_usd = min(buy_volume, sell_volume)

            is_valid, reason = bot._validate_arbitrage_opportunity(
                symbol, buy_price, sell_price, buy_exchange, sell_exchange, volume_usd, is_admin_check=is_admin
            )

            if is_valid and profit_percentage >= profit_threshold_filter:
                opportunities_found.append({
                    "symbol": symbol,
                    "buy_exchange": buy_exchange,
                    "buy_price": buy_price,
                    "sell_exchange": sell_exchange,
                    "sell_price": sell_price,
                    "profit_percentage": profit_percentage,
                    "volume_usd": volume_usd
                })
                bot.save_arbitrage_opportunity(
                    buy_exchange, sell_exchange, symbol, buy_price, sell_price, profit_percentage, volume_usd
                )
            elif is_admin and not is_valid: # Admin sees why something was filtered
                logger.info(f"Admin check: Filtered {symbol} ({buy_exchange}-{sell_exchange}) - Reason: {reason}")


    opportunities_found.sort(key=lambda x: x['profit_percentage'], reverse=True)

    if not opportunities_found:
        await context.bot.send_message(chat_id=user_id, text="Üzgünüm, şu anda kayda değer arbitraj fırsatı bulunamadı.")
    else:
        message = "🚨 **Bulunan Arbitraj Fırsatları:** 🚨\n\n"
        for i, opp in enumerate(opportunities_found[:max_opportunities]):
            if not is_premium and opp['profit_percentage'] > max_profit_for_display:
                profit_display = f"{max_profit_for_display:.2f}%+" # Censor for free users
            else:
                profit_display = f"{opp['profit_percentage']:.2f}%"

            message += (
                f"**{opp['symbol']}**\n"
                f"📈 Kar: `{profit_display}`\n"
                f"🟢 Al: `{opp['buy_price']:.8f}` ({opp['buy_exchange'].upper()})\n"
                f"🔴 Sat: `{opp['sell_price']:.8f}` ({opp['sell_exchange'].upper()})\n"
                f"💰 24s Hacim: `${opp['volume_usd']:.0f}`\n"
                f"------------------------------------\n"
            )
        message += "\n*24s Hacim bilgisi, fırsatın gerçekleşebilirliğini gösterir."
        if not is_premium:
            message += "\n\n**Daha fazla ve yüksek karlı fırsatları görmek için Premium'a yükseltin!** 💎"
        await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')

async def send_trusted_coins_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    trusted_coins_text = "📊 **Güvenilir Coinler Listesi:** 📊\n\n"
    sorted_trusted = sorted(list(bot.trusted_symbols))
    for coin in sorted_trusted:
        trusted_coins_text += f"- `{coin}`\n"
    trusted_coins_text += "\nBu coinler, botumuzun güvenlik filtreleri tarafından doğrulanmış yüksek hacimli ve güvenilir varlıklardır."
    await update.callback_query.edit_message_text(trusted_coins_text, parse_mode='Markdown')

async def send_premium_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    premium_info_text = (
        "💎 **Premium Üyelik Avantajları:** 💎\n\n"
        "- Sınırsız arbitraj fırsatı gösterimi\n"
        "- Yüksek karlı fırsatlara tam erişim\n"
        "- Tüm coinler için gelişmiş güvenlik analizleri\n"
        "- `/price` komutu ile anlık fiyat sorgulama\n"
        "- Öncelikli destek\n\n"
        f"Şimdi Premium olun: [Buradan satın alın]({GUMROAD_LINK})\n"
        f"Destek için: {SUPPORT_USERNAME}"
    )
    await update.callback_query.edit_message_text(premium_info_text, parse_mode='Markdown', disable_web_page_preview=True)

async def send_help_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "ℹ️ **Yardım ve Kullanım Kılavuzu** ℹ️\n\n"
        "**🔍 Arbitraj Ara:** Anlık kripto para arbitraj fırsatlarını tarar ve size sunar.\n"
        "**📊 Güvenilir Coinler:** Güvenlik filtrelerimizden geçmiş, yüksek hacimli coinlerin listesini gösterir.\n"
        "**💎 Premium Bilgi:** Premium üyeliğin avantajları hakkında bilgi verir.\n"
        "**🔑 Lisans Aktifleştir:** Gumroad'dan aldığınız lisans anahtarını girerek premium üyeliğinizi başlatın.\n\n"
        "**Premium Komutlar:**\n"
        "- `/price <SEMBOL>`: Belirttiğiniz kripto paranın tüm borsalardaki güncel fiyatını ve güvenlik analizini gösterir. Örn: `/price BTCUSDT`\n\n"
        "Herhangi bir sorunuz olursa lütfen destek ekibimizle iletişime geçin: "
        f"{SUPPORT_USERNAME}"
    )
    await update.callback_query.edit_message_text(help_text, parse_mode='Markdown', disable_web_page_preview=True)

async def handle_license_activation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"

    if context.user_data.get('awaiting_license'):
        license_key = update.message.text.strip()
        context.user_data['awaiting_license'] = False # Reset state

        if license_key in bot.used_license_keys:
            await update.message.reply_text("Bu lisans anahtarı daha önce kullanılmış. Lütfen farklı bir anahtar deneyin veya destek ile iletişime geçin.")
            return

        await update.message.reply_text("Lisans anahtarınız doğrulanıyor... Lütfen bekleyin.")

        try:
            async with aiohttp.ClientSession() as session:
                gumroad_url = f"https://api.gumroad.com/v2/licenses/verify"
                payload = {
                    "product_id": GUMROAD_PRODUCT_ID,
                    "license_key": license_key,
                    "access_token": GUMROAD_ACCESS_TOKEN
                }
                async with session.post(gumroad_url, data=payload) as response:
                    gumroad_data = await response.json()

                    if gumroad_data.get("success") and gumroad_data["purchase"]["product_id"] == GUMROAD_PRODUCT_ID:
                        # Assuming a standard 30-day premium for simplicity, or get from Gumroad if available
                        expiry_date = datetime.now() + timedelta(days=30) # Example: 30 days premium
                        bot.set_user_premium(user_id, username, expiry_date)
                        bot.add_used_license_key(license_key)
                        await update.message.reply_text(
                            f"🎉 Tebrikler! Premium üyeliğiniz {expiry_date.strftime('%d.%m.%Y %H:%M')} tarihine kadar aktifleştirildi.\n"
                            "Artık tüm premium özelliklere erişebilirsiniz!"
                        )
                    else:
                        await update.message.reply_text(
                            "Geçersiz lisans anahtarı veya anahtar bu ürün için değil. Lütfen kontrol edin."
                        )
        except Exception as e:
            logger.error(f"Gumroad API error: {e}")
            await update.message.reply_text("Lisans doğrulama sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin.")
    else:
        # If not awaiting license, just ignore or pass to other handlers
        pass

async def price_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not bot.is_premium(user_id) and str(user_id) != ADMIN_USER_ID:
        await update.message.reply_text("Bu özellik sadece Premium kullanıcılar içindir. `/premium` yazarak daha fazla bilgi alın.")
        return

    if not context.args:
        await update.message.reply_text("Lütfen bir kripto para sembolü girin. Örn: `/price BTCUSDT`")
        return

    symbol_input = context.args[0].upper()
    normalized_symbol = bot.normalize_symbol(symbol_input)

    await context.bot.send_message(chat_id=user_id, text=f"'{normalized_symbol}' için fiyatlar aranıyor...")

    if time.time() - bot.last_fetched_time > 30: # Data older than 30 seconds
        await context.bot.send_message(chat_id=user_id, text="Piyasa verileri güncelleniyor, bu biraz zaman alabilir.")
        await bot.fetch_all_tickers()

    with bot.data_lock:
        current_ticker_data = bot.ticker_data
        current_volume_data = bot.volume_data

    prices_found = []
    total_volume = 0.0

    for exchange, tickers in current_ticker_data.items():
        if normalized_symbol in tickers:
            price = tickers[normalized_symbol]
            volume = current_volume_data.get(exchange, {}).get(normalized_symbol, 0.0)
            prices_found.append({"exchange": exchange, "price": price, "volume": volume})
            total_volume += volume

    if not prices_found:
        await context.bot.send_message(chat_id=user_id, text=f"'{normalized_symbol}' için hiçbir borsada fiyat bulunamadı.")
        return

    prices_found.sort(key=lambda x: x['price'])

    message = f"📈 **{normalized_symbol} Anlık Fiyatlar** 📈\n\n"
    for item in prices_found:
        message += f"- {item['exchange'].upper()}: `{item['price']:.8f}` (Hacim: ${item['volume']:.0f})\n"

    is_trusted = "✅ Güvenilir Sembol" if normalized_symbol in bot.trusted_symbols else "⚠️ Güvenilir Olmayan Sembol"
    is_suspicious = "🚨 Şüpheli Anahtar Kelime İçeriyor" if bot._is_suspicious_symbol(normalized_symbol) else ""
    volume_analysis = f"Total 24s Hacim: `${total_volume:,.0f}`"

    message += (
        f"\n-- Analiz --\n"
        f"{is_trusted}\n"
        f"{is_suspicious}\n"
        f"{volume_analysis}"
    )

    await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')

# --- Admin Commands ---

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != int(ADMIN_USER_ID):
        await query.edit_message_text("Bu özelliği kullanmaya yetkiniz yok.")
        return

    keyboard = [
        [InlineKeyboardButton("Premium Ekle", callback_data="admin_add_premium")],
        [InlineKeyboardButton("Premium Kaldır", callback_data="admin_remove_premium")],
        [InlineKeyboardButton("Premium Kullanıcıları Listele", callback_data="admin_list_premium")],
        [InlineKeyboardButton("İstatistikleri Görüntüle", callback_data="admin_view_stats")],
        [InlineKeyboardButton("Mesaj Yayınla", callback_data="admin_broadcast_prompt")], # New
        [InlineKeyboardButton("Affiliate Link Oluştur", callback_data="admin_generate_affiliate_link")], # New
        [InlineKeyboardButton("Affiliate Listele", callback_data="admin_list_affiliates")], # New
        [InlineKeyboardButton("Ana Menüye Dön", callback_data="back_to_main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Admin Paneline Hoş Geldiniz:", reply_markup=reply_markup)

async def add_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    # If called from message handler, context.args might be empty or combined.
    # We expect `user_id_or_username [days]`
    if context.user_data.get('admin_action') == 'add_premium':
        message_parts = update.message.text.split()
        target_str = message_parts[0]
        days_str = message_parts[1] if len(message_parts) > 1 else '30' # Default 30 days
        context.user_data.pop('admin_action', None) # Clear state
    elif context.args and len(context.args) > 0:
        target_str = context.args[0]
        days_str = context.args[1] if len(context.args) > 1 else '30'
    else:
        await update.message.reply_text("Kullanım: `/addpremium <kullanıcı_id_veya_kullanıcı_adı> [gün]`\nÖrn: `/addpremium 123456789 30` veya `/addpremium my_user`")
        return

    target_id = get_user_id_from_input(target_str)
    if not target_id:
        await update.message.reply_text(f"Kullanıcı '{target_str}' bulunamadı.")
        return

    try:
        days = int(days_str)
        if days <= 0:
            await update.message.reply_text("Gün sayısı pozitif bir sayı olmalıdır.")
            return
        expiry_date = datetime.now() + timedelta(days=days)
        
        # Get username from DB if ID was provided directly
        bot.cursor.execute("SELECT username FROM users WHERE user_id = %s", (target_id,))
        user_data = bot.cursor.fetchone()
        target_username = user_data[0] if user_data else f"user_{target_id}"

        bot.set_user_premium(target_id, target_username, expiry_date)
        await update.message.reply_text(f"Kullanıcı {target_username} ({target_id}) premium olarak {days} gün boyunca ayarlandı. Sona erme: {expiry_date.strftime('%d.%m.%Y %H:%M')}")
    except ValueError:
        await update.message.reply_text("Geçersiz gün sayısı belirtildi.")
    except Exception as e:
        logger.error(f"Error adding premium: {e}")
        await update.message.reply_text("Premium eklenirken bir hata oluştu.")

async def remove_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    # If called from message handler, context.args might be empty or combined.
    if context.user_data.get('admin_action') == 'remove_premium':
        target_str = update.message.text.strip()
        context.user_data.pop('admin_action', None) # Clear state
    elif context.args and len(context.args) > 0:
        target_str = context.args[0]
    else:
        await update.message.reply_text("Kullanım: `/removepremium <kullanıcı_id_veya_kullanıcı_adı>`\nÖrn: `/removepremium 123456789` veya `/removepremium my_user`")
        return

    target_id = get_user_id_from_input(target_str)
    if not target_id:
        await update.message.reply_text(f"Kullanıcı '{target_str}' bulunamadı.")
        return

    if bot.is_premium(target_id):
        bot.remove_user_premium(target_id)
        await update.message.reply_text(f"Kullanıcı {target_str} ({target_id}) premium üyeliği kaldırıldı.")
    else:
        await update.message.reply_text(f"Kullanıcı {target_str} ({target_id}) premium değil.")


async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    try:
        bot.cursor.execute("SELECT user_id, username, expiry_date FROM premium_users ORDER BY expiry_date DESC")
        premium_users = bot.cursor.fetchall()

        if not premium_users:
            await update.message.reply_text("Şu anda premium kullanıcı bulunmamaktadır.")
            return

        message_text = "💎 **Premium Kullanıcılar** 💎\n\n"
        for user_id, username, expiry_date in premium_users:
            status = "Aktif" if expiry_date > datetime.now() else "Süresi Doldu"
            message_text += (
                f"- @{username or 'N/A'} (ID: `{user_id}`)\n"
                f"  Durum: {status} - Sona Erme: {expiry_date.strftime('%d.%m.%Y %H:%M')}\n\n"
            )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error listing premium users: {e}")
        await update.message.reply_text("Premium kullanıcılar listelenirken bir hata oluştu.")

# --- Admin Broadcast Messaging ---
async def admin_broadcast_message_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    keyboard = [
        [InlineKeyboardButton("Tüm Kullanıcılar", callback_data="broadcast_all")],
        [InlineKeyboardButton("Ücretsiz Kullanıcılar", callback_data="broadcast_free")],
        [InlineKeyboardButton("Premium Kullanıcılar", callback_data="broadcast_premium")],
        [InlineKeyboardButton("Belirli Bir Kullanıcı (kullanıcı adı ile)", callback_data="broadcast_specific")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Yayın için hedef kitleyi seçin:", reply_markup=reply_markup)

async def handle_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != int(ADMIN_USER_ID):
        await query.edit_message_text("Bu fonksiyonu kullanmaya yetkiniz yok.")
        return

    audience_type = query.data.split('_')[1] # e.g., 'all', 'free', 'premium', 'specific'
    context.user_data['broadcast_audience'] = audience_type

    if audience_type == "specific":
        await query.edit_message_text("Lütfen kullanıcı adını (@ olmadan) ve ardından mesajınızı yazın.\n\nÖrnek: `bir_kullanici_adi Bu benim mesajım.`")
    else:
        await query.edit_message_text(f"Lütfen {audience_type} kullanıcılara göndermek istediğiniz mesajı yazın.")

async def handle_admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        return # Ignore messages from non-admins

    audience_type = context.user_data.get('broadcast_audience')
    message_text = update.message.text

    if not audience_type:
        # This message is not part of a broadcast flow initiated by admin_broadcast_message_prompt
        return

    sent_count = 0
    failed_count = 0
    target_user_id = None
    target_username = None

    if audience_type == "all":
        bot.cursor.execute("SELECT user_id FROM users")
        user_ids = [row[0] for row in bot.cursor.fetchall()]
    elif audience_type == "free":
        bot.cursor.execute("SELECT u.user_id FROM users u LEFT JOIN premium_users p ON u.user_id = p.user_id WHERE p.user_id IS NULL")
        user_ids = [row[0] for row in bot.cursor.fetchall()]
    elif audience_type == "premium":
        bot.cursor.execute("SELECT user_id FROM premium_users")
        user_ids = [row[0] for row in bot.cursor.fetchall()]
    elif audience_type == "specific":
        parts = message_text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("Geçersiz format. Lütfen kullanıcı adı ve mesajı sağlayın.")
            context.user_data.pop('broadcast_audience', None)
            return
        target_username = parts[0].strip()
        message_text = parts[1].strip()

        bot.cursor.execute("SELECT user_id FROM users WHERE username = %s", (target_username,))
        result = bot.cursor.fetchone()
        if not result:
            await update.message.reply_text(f"Kullanıcı @{target_username} bulunamadı.")
            context.user_data.pop('broadcast_audience', None)
            return
        user_ids = [result[0]]
        target_user_id = result[0]
    else:
        await update.message.reply_text("Geçersiz yayın hedef kitlesi türü.")
        context.user_data.pop('broadcast_audience', None)
        return

    await update.message.reply_text(f"{len(user_ids)} kullanıcıya mesaj gönderiliyor...")

    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
            await asyncio.sleep(0.05) # Small delay to avoid hitting Telegram API limits
        except error.TelegramError as e:
            failed_count += 1
            logger.warning(f"Kullanıcı {user_id} (kullanıcı adı: {target_username if user_id == target_user_id else 'N/A'}) mesaj gönderilemedi: {e}")
            if "bot was blocked by the user" in str(e):
                logger.info(f"Kullanıcı {user_id} botu engelledi.")
        except Exception as e:
            failed_count += 1
            logger.error(f"Kullanıcı {user_id} mesaj gönderilirken beklenmedik hata oluştu: {e}")

    await update.message.reply_text(
        f"{audience_type} kullanıcılara yayın tamamlandı.\n"
        f"Gönderilen: {sent_count}\n"
        f"Başarısız: {failed_count}"
    )
    context.user_data.pop('broadcast_audience', None) # Clear the state

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    try:
        # Total users
        bot.cursor.execute("SELECT COUNT(*) FROM users")
        total_users = bot.cursor.fetchone()[0]

        # Premium users
        bot.cursor.execute("SELECT COUNT(*) FROM premium_users WHERE expiry_date > NOW()")
        active_premium_users = bot.cursor.fetchone()[0]

        # Inactive premium users (expired)
        bot.cursor.execute("SELECT COUNT(*) FROM premium_users WHERE expiry_date <= NOW()")
        expired_premium_users = bot.cursor.fetchone()[0]

        # Total arbitrage records
        bot.cursor.execute("SELECT COUNT(*) FROM arbitrage_data")
        total_arbitrage_records = bot.cursor.fetchone()[0]

        # Most active users (e.g., last 24 hours) - by any interaction
        bot.cursor.execute("""
            SELECT username, last_activity
            FROM users
            WHERE last_activity > NOW() - INTERVAL '24 hours'
            ORDER BY last_activity DESC
            LIMIT 10
        """)
        recent_active_users = bot.cursor.fetchall()

        # Most active users by arbitrage checks (last 24 hours)
        bot.cursor.execute("""
            SELECT username, last_check_time
            FROM users
            WHERE last_check_time IS NOT NULL AND last_check_time > NOW() - INTERVAL '24 hours'
            ORDER BY last_check_time DESC
            LIMIT 10
        """)
        recent_check_users = bot.cursor.fetchall()

        # Affiliate stats summary
        bot.cursor.execute("""
            SELECT
                a.name,
                a.link_code,
                COUNT(DISTINCT u.user_id) AS total_referred_users,
                COUNT(DISTINCT aa.user_id) AS total_premium_activations
            FROM affiliates a
            LEFT JOIN users u ON a.link_code = u.referred_by
            LEFT JOIN affiliate_activations aa ON a.link_code = aa.affiliate_link_code
            GROUP BY a.name, a.link_code
            ORDER BY total_premium_activations DESC, total_referred_users DESC;
        """)
        affiliate_stats = bot.cursor.fetchall()

        stats_message = (
            f"📊 **Bot İstatistikleri** 📊\n\n"
            f"👥 Toplam Kullanıcı: `{total_users}`\n"
            f"💎 Aktif Premium Kullanıcı: `{active_premium_users}`\n"
            f"⏳ Süresi Dolan Premium Kullanıcı: `{expired_premium_users}`\n"
            f"🔄 Toplam Arbitraj Kaydı: `{total_arbitrage_records}`\n"
            f"🌐 İzlenen Borsalar: `{len(bot.exchanges)}`\n"
            f"💰 Güvenilir Semboller: `{len(bot.trusted_symbols)}`\n\n"
        )

        if recent_active_users:
            stats_message += "🌟 **Son 24 Saatte En Aktif Kullanıcılar (Herhangi Bir Etkileşim)** 🌟\n"
            for username, last_activity in recent_active_users:
                stats_message += f"- @{username or 'N/A'} (Son aktivite: {last_activity.strftime('%Y-%m-%d %H:%M')})\n"
            stats_message += "\n"

        if recent_check_users:
            stats_message += "📈 **Son 24 Saatte Arbitraj Kontrolünde Aktif Olanlar** 📈\n"
            for username, last_check_time in recent_check_users:
                stats_message += f"- @{username or 'N/A'} (Son kontrol: {last_check_time.strftime('%Y-%m-%d %H:%M')})\n"
            stats_message += "\n"

        if affiliate_stats:
            stats_message += "🔗 **Affiliate Programı İstatistikleri** 🔗\n"
            for name, link_code, referred_users, premium_activations in affiliate_stats:
                stats_message += (
                    f"**{name}** (`{link_code}`)\n"
                    f"  - Yönlendirilen Kullanıcı: `{referred_users}`\n"
                    f"  - Premium Aktivasyonları: `{premium_activations}`\n"
                )
            stats_message += "\n"

        await update.message.reply_text(stats_message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Bot istatistikleri alınırken hata oluştu: {e}")
        await update.message.reply_text("İstatistikler alınırken bir hata oluştu.")


async def admin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if str(user_id) != ADMIN_USER_ID:
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    await context.bot.send_message(chat_id=user_id, text="Admin modunda arbitraj fırsatları aranıyor (daha yüksek kar eşiği ile)...")

    # This is a special admin-only check.
    # We'll use a higher profit threshold and exclude Huobi due to specific issues if any.
    is_admin = True
    profit_threshold_filter = 0.1 # Admins always see all valid ones, even low profit
    max_opportunities = 20 # Admins can see more
    
    if time.time() - bot.last_fetched_time > 30: # Data older than 30 seconds
        await context.bot.send_message(chat_id=user_id, text="Piyasa verileri güncelleniyor, bu biraz zaman alabilir.")
        await bot.fetch_all_tickers()

    with bot.data_lock:
        current_ticker_data = bot.ticker_data
        current_volume_data = bot.volume_data

    if not current_ticker_data:
        await context.bot.send_message(chat_id=user_id, text="Şu anda piyasa verileri mevcut değil. Lütfen daha sonra tekrar deneyin.")
        return

    opportunities_found = []
    common_symbols = set()
    for exchange_tickers in current_ticker_data.values():
        common_symbols.update(exchange_tickers.keys())

    for symbol in common_symbols:
        buy_exchange, buy_price = None, float('inf')
        sell_exchange, sell_price = None, 0.0
        buy_volume, sell_volume = 0.0, 0.0

        for exchange, tickers in current_ticker_data.items():
            if symbol in tickers and exchange != 'huobi': # Exclude Huobi for this admin check
                price = tickers[symbol]
                volume = current_volume_data.get(exchange, {}).get(symbol, 0.0)

                if price < buy_price:
                    buy_price = price
                    buy_exchange = exchange
                    buy_volume = volume

                if price > sell_price:
                    sell_price = price
                    sell_exchange = exchange
                    sell_volume = volume

        if buy_exchange and sell_exchange and buy_exchange != sell_exchange and buy_price > 0:
            profit_percentage = ((sell_price - buy_price) / buy_price) * 100

            volume_usd = min(buy_volume, sell_volume)

            is_valid, reason = bot._validate_arbitrage_opportunity(
                symbol, buy_price, sell_price, buy_exchange, sell_exchange, volume_usd, is_admin_check=is_admin
            )

            if is_valid and profit_percentage >= profit_threshold_filter:
                opportunities_found.append({
                    "symbol": symbol,
                    "buy_exchange": buy_exchange,
                    "buy_price": buy_price,
                    "sell_exchange": sell_exchange,
                    "sell_price": sell_price,
                    "profit_percentage": profit_percentage,
                    "volume_usd": volume_usd
                })
                # No need to save to DB for admin_check unless explicitly desired, as it's a diagnostic tool
            elif not is_valid:
                logger.info(f"Admin check: Filtered {symbol} ({buy_exchange}-{sell_exchange}) - Reason: {reason}")


    opportunities_found.sort(key=lambda x: x['profit_percentage'], reverse=True)

    if not opportunities_found:
        await context.bot.send_message(chat_id=user_id, text="Üzgünüm, admin kontrolünde kayda değer arbitraj fırsatı bulunamadı (Huobi hariç).")
    else:
        message = "🚨 **Admin Arbitraj Fırsatları (Yüksek Eşik)** 🚨\n\n"
        for i, opp in enumerate(opportunities_found[:max_opportunities]):
            message += (
                f"**{opp['symbol']}**\n"
                f"📈 Kar: `{opp['profit_percentage']:.2f}%`\n"
                f"🟢 Al: `{opp['buy_price']:.8f}` ({opp['buy_exchange'].upper()})\n"
                f"🔴 Sat: `{opp['sell_price']:.8f}` ({opp['sell_exchange'].upper()})\n"
                f"💰 24s Hacim: `${opp['volume_usd']:.0f}`\n"
                f"------------------------------------\n"
            )
        message += "\n*Bu fırsatlar admin panelinden yüksek kar eşiği ve Huobi hariç olarak listelenmiştir."
        await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')

# --- Affiliate Management ---
async def generate_affiliate_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Kullanım: `/generate_affiliate_link <influencer_adı> [özel_kod]`\n"
                                        "Örnek: `/generate_affiliate_link AyşeYılmaz`\n"
                                        "Örnek: `/generate_affiliate_link CanDemir can_promo`")
        return

    influencer_name = context.args[0]
    custom_code = context.args[1] if len(context.args) > 1 else None

    if custom_code:
        link_code = custom_code.lower().replace(" ", "_")
    else:
        link_code = f"{influencer_name.lower().replace(' ', '_')}_{str(uuid4())[:8]}" # Generate unique code

    try:
        # Ensure link_code is unique
        bot.cursor.execute("SELECT 1 FROM affiliates WHERE link_code = %s", (link_code,))
        if bot.cursor.fetchone():
            await update.message.reply_text(f"Affiliate link kodu `{link_code}` zaten mevcut. Lütfen farklı bir özel kod deneyin veya yeniden oluşturun.")
            return

        bot.cursor.execute(
            "INSERT INTO affiliates (name, link_code) VALUES (%s, %s) RETURNING affiliate_id",
            (influencer_name, link_code)
        )
        affiliate_id = bot.cursor.fetchone()[0]
        bot.conn.commit()

        bot.affiliates[link_code] = {"name": influencer_name, "affiliate_id": affiliate_id}

        affiliate_link = f"https://t.me/{context.bot.username}?start=aff_{link_code}"
        await update.message.reply_text(
            f"**{influencer_name}** için Affiliate linki oluşturuldu:\n"
            f"Kod: `{link_code}`\n"
            f"Link: `{affiliate_link}`",
            parse_mode='Markdown'
        )
        logger.info(f"{influencer_name} için affiliate linki oluşturuldu, kod: {link_code}")

    except Exception as e:
        logger.error(f"Affiliate link oluşturulurken hata oluştu: {e}")
        await update.message.reply_text("Affiliate link oluşturulurken bir hata oluştu.")

async def list_affiliates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        await update.message.reply_text("Bu komutu kullanmaya yetkiniz yok.")
        return

    try:
        bot.cursor.execute("SELECT name, link_code, created_at FROM affiliates ORDER BY created_at DESC")
        affiliates_list = bot.cursor.fetchall()

        if not affiliates_list:
            await update.message.reply_text("Hiç affiliate linki bulunamadı.")
            return

        message_text = "🔗 **Mevcut Affiliate Linkleri** 🔗\n\n"
        for name, link_code, created_at in affiliates_list:
            message_text += (
                f"**{name}** (`{link_code}`)\n"
                f"  - Oluşturulma: {created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"  - Link: `https://t.me/{context.bot.username}?start=aff_{link_code}`\n\n"
            )
        await update.message.reply_text(message_text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Affiliate'ler listelenirken hata oluştu: {e}")
        await update.message.reply_text("Affiliate linkleri listelenirken bir hata oluştu.")

# --- General Message and Callback Handlers ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "check_arbitrage":
        await find_arbitrage_opportunities(update, context)
    elif query.data == "trusted_coins":
        await send_trusted_coins_list(update, context)
    elif query.data == "premium_info":
        await send_premium_info(update, context)
    elif query.data == "activate_license":
        await query.edit_message_text("Lütfen premium üyeliği aktifleştirmek için Gumroad lisans anahtarınızı yanıtlayın.")
        context.user_data['awaiting_license'] = True
    elif query.data == "help":
        await send_help_info(update, context)
    elif query.data == "admin_panel":
        await admin_panel_callback(update, context)
    elif query.data == "admin_add_premium":
        await query.edit_message_text("Lütfen kullanıcının ID'sini veya kullanıcı adını (örn: `123456789` veya `benim_kullanıcı_adı`) ve isteğe bağlı olarak gün sayısını (örn: `30`) yanıtlayın.\nÖrnek: `123456789 30` veya `benim_kullanıcı_adı`")
        context.user_data['admin_action'] = 'add_premium'
    elif query.data == "admin_remove_premium":
        await query.edit_message_text("Lütfen kullanıcının ID'sini veya kullanıcı adını (örn: `123456789` veya `benim_kullanıcı_adı`) yanıtlayın.")
        context.user_data['admin_action'] = 'remove_premium'
    elif query.data == "admin_list_premium":
        await list_premium_command(update, context)
    elif query.data == "admin_view_stats":
        await stats_command(update, context)
    elif query.data == "admin_broadcast_prompt": # New
        await admin_broadcast_message_prompt(update, context)
    elif query.data in ["broadcast_all", "broadcast_free", "broadcast_premium", "broadcast_specific"]: # New
        await handle_broadcast_callback(update, context)
    elif query.data == "admin_generate_affiliate_link": # New
        await query.edit_message_text("Lütfen influencer'ın adını ve isteğe bağlı bir özel kodu yanıtlayın.\nKullanım: `AyşeYılmaz` veya `CanDemir can_promo`")
        context.user_data['admin_action'] = 'generate_affiliate_link_prompt' # Await message
    elif query.data == "admin_list_affiliates": # New
        await list_affiliates_command(update, context)
    elif query.data == "back_to_main_menu":
        await start_command(update, context) # Or a dedicated main menu function
    else:
        await query.edit_message_text("Bilinmeyen komut.")

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(ADMIN_USER_ID):
        return # Ignore messages from non-admins

    action = context.user_data.get('admin_action')
    message_text = update.message.text

    if action == 'add_premium':
        await add_premium_command(update, context)
    elif action == 'remove_premium':
        await remove_premium_command(update, context)
    elif action == 'generate_affiliate_link_prompt': # New
        context.args = message_text.split() # Simulate args for generate_affiliate_link_command
        await generate_affiliate_link_command(update, context)
        context.user_data.pop('admin_action', None) # Clear the state
    else:
        # This message is not part of a known admin action flow
        pass

def main() -> None:
    """Start the bot."""
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_panel_callback))
    application.add_handler(CommandHandler("addpremium", add_premium_command))
    application.add_handler(CommandHandler("removepremium", remove_premium_command))
    application.add_handler(CommandHandler("listpremium", list_premium_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("admincheck", admin_check_command))
    application.add_handler(CommandHandler("price", price_check_command))
    application.add_handler(CommandHandler("generate_affiliate_link", generate_affiliate_link_command)) # New command
    application.add_handler(CommandHandler("list_affiliates", list_affiliates_command)) # New command
    application.add_handler(CommandHandler("broadcast", admin_broadcast_message_prompt)) # New command

    # Message handlers (order matters: specific flows first, then general)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(int(ADMIN_USER_ID)) & filters.ContextUpdate(
            lambda context: context.user_data.get('broadcast_audience') in ["all", "free", "premium", "specific"]
        ),
        handle_admin_broadcast_message
    )) # New: Handle broadcast messages
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(int(ADMIN_USER_ID)) & filters.ContextUpdate(
            lambda context: context.user_data.get('admin_action') in ['add_premium', 'remove_premium', 'generate_affiliate_link_prompt']
        ),
        handle_admin_actions
    )) # Existing: Handle general admin replies
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_license_activation)) # Existing: General message handler for license activation

    # Callback handlers
    application.add_handler(CallbackQueryHandler(button_handler))

    async def cleanup():
        if bot.session and not bot.session.closed:
            await bot.session.close()
        if bot.conn and not bot.conn.closed:
            bot.conn.close()
            logger.info("PostgreSQL database connection closed.")

    application.post_stop = cleanup

    application.run_polling()
    logger.info("Gelişmiş Arbitraj Botu başarıyla başlatıldı.")


if __name__ == '__main__':
    main()
