import re
import os
import logging
from os import environ
from Script import script

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- HELPER FUNCTIONS ---
def is_enabled(data, default):
    val = environ.get(data, str(default))
    return val.lower() in ["true", "yes", "1", "enable", "y"]

def is_valid_ip(ip):
    ip_pattern = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    return re.match(ip_pattern, ip) is not None

# ==============================================================================
# 🔐 REQUIRED CONFIGURATION (MANDATORY)
# ==============================================================================

API_ID = int(environ.get('API_ID', '0'))
if API_ID == 0:
    logger.error('❌ API_ID is missing! Exiting...')
    exit(1)

API_HASH = environ.get('API_HASH', '')
if not API_HASH:
    logger.error('❌ API_HASH is missing! Exiting...')
    exit(1)

BOT_TOKEN = environ.get('BOT_TOKEN', '')
if not BOT_TOKEN:
    logger.error('❌ BOT_TOKEN is missing! Exiting...')
    exit(1)

try:
    BOT_ID = int(BOT_TOKEN.split(":")[0])
except ValueError:
    logger.error('❌ Invalid BOT_TOKEN structure! Exiting...')
    exit(1)

# Database URL
DATA_DATABASE_URL = environ.get('DATA_DATABASE_URL', "")
if not DATA_DATABASE_URL.startswith('mongodb'):
    logger.error('❌ DATA_DATABASE_URL (MongoDB) is missing or invalid!')
    exit(1)

DATABASE_NAME = environ.get('DATABASE_NAME', "FastFinder")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files')

# Admins
try:
    ADMINS = [int(x) for x in environ.get('ADMINS', '').split()]
    if not ADMINS: raise ValueError
except ValueError:
    logger.error('❌ ADMINS list is missing or invalid! Exiting...')
    exit(1)

# Channels
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '0'))
if LOG_CHANNEL == 0:
    logger.error('❌ LOG_CHANNEL ID is missing!')
    exit(1)

BIN_CHANNEL = int(environ.get("BIN_CHANNEL", "0"))
if BIN_CHANNEL == 0:
    logger.error('❌ BIN_CHANNEL ID is missing!')
    exit(1)

# Web URL
URL = environ.get("URL", "")
if not URL:
    logger.error('❌ URL (Server Link) is missing!')
    exit(1)
else:
    if not URL.endswith("/"): URL += "/"

PORT = int(environ.get('PORT', '8080'))

# ==============================================================================
# 💎 PREMIUM SYSTEM
# ==============================================================================

IS_PREMIUM = is_enabled('IS_PREMIUM', True)
PRE_DAY_AMOUNT = int(environ.get('PRE_DAY_AMOUNT', '10'))
UPI_ID = environ.get("UPI_ID", "")
UPI_NAME = environ.get("UPI_NAME", "FastFinder Payment")
RECEIPT_SEND_USERNAME = environ.get("RECEIPT_SEND_USERNAME", "")

# Safety Check for Premium
if IS_PREMIUM and (not UPI_ID or not RECEIPT_SEND_USERNAME):
    logger.warning("⚠️ Premium Mode is ON but UPI_ID or RECEIPT_SEND_USERNAME is missing! Premium features may fail.")
    IS_PREMIUM = False

# ==============================================================================
# ⚙️ SETTINGS & TOGGLES
# ==============================================================================

# Time Settings
TIME_ZONE = environ.get('TIME_ZONE', 'Asia/Kolkata')
DELETE_TIME = int(environ.get('DELETE_TIME', 300)) # 5 Minutes
PM_FILE_DELETE_TIME = int(environ.get('PM_FILE_DELETE_TIME', 43200)) # 12 Hours
CACHE_TIME = int(environ.get('CACHE_TIME', 300))

# Search & Results
MAX_BTN = int(environ.get('MAX_BTN', 10)) 
USE_CAPTION_FILTER = is_enabled('USE_CAPTION_FILTER', True)
SPELL_CHECK = is_enabled("SPELL_CHECK", True)
LINK_MODE = is_enabled("LINK_MODE", True)

# Features
IS_STREAM = is_enabled('IS_STREAM', True)
PROTECT_CONTENT = is_enabled('PROTECT_CONTENT', True)
AUTO_DELETE = is_enabled('AUTO_DELETE', False) # Default OFF for groups
WELCOME = is_enabled('WELCOME', False)

# Indexing
INDEX_CHANNELS = [int(x) for x in environ.get('INDEX_CHANNELS', '').split() if x.lstrip('-').isdigit()]

# Links & Media
SUPPORT_LINK = environ.get('SUPPORT_LINK', 'https://t.me/YourSupport')
UPDATES_LINK = environ.get('UPDATES_LINK', 'https://t.me/YourUpdates')
FILMS_LINK = environ.get('FILMS_LINK', 'https://t.me/YourChannel')
TUTORIAL = environ.get("TUTORIAL", "https://t.me/")

PICS = environ.get('PICS', 'https://graph.org/file/5a676b7337373f0083906.jpg').split()

# Cosmetics
REACTIONS = environ.get('REACTIONS', '👍 ❤️ 🔥 🥰 👏 ⚡ 🤩').split()
STICKERS = environ.get('STICKERS', 'CAACAgIAAxkBAAEN4ctnu1NdZUe21tiqF1CjLCZW8rJ28QACmQwAAj9UAUrPkwx5a8EilDYE').split()

# Languages & Quality (For Tags)
LANGUAGES = [l.lower() for l in environ.get('LANGUAGES', 'hindi english telugu tamil kannada malayalam marathi').split()]
QUALITY = [q.lower() for q in environ.get('QUALITY', '360p 480p 720p 1080p 1440p 2160p 4k').split()]

# ==============================================================================
# 🗑️ LEGACY / DISABLED FEATURES (Placeholders to prevent errors)
# ==============================================================================

# These are kept for backward compatibility with Database structure but are forcefully disabled.
IMDB = False
SHORTLINK = False
SHORTLINK_URL = ""
SHORTLINK_API = ""
IS_VERIFY = False
VERIFY_TUTORIAL = ""
VERIFY_EXPIRE = 0
LONG_IMDB_DESCRIPTION = False

# Templates (Imported from Script to keep logic central)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", script.IMDB_TEMPLATE)
FILE_CAPTION = environ.get("FILE_CAPTION", script.FILE_CAPTION)
WELCOME_TEXT = environ.get("WELCOME_TEXT", script.WELCOME_TEXT)

# Optional IDs
SUPPORT_GROUP = int(environ.get('SUPPORT_GROUP', '0'))
AUTH_CHANNEL = int(environ.get('AUTH_CHANNEL', '0'))
DB_CHANNEL = int(environ.get('DB_CHANNEL', '0'))
