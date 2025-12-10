import re
import os
from os import environ
from Script import script
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def is_enabled(data, default):
    val = environ.get(data, str(default))
    if val.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif val.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

def is_valid_ip(ip):
    ip_pattern = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    return re.match(ip_pattern, ip) is not None

# --- REQUIRED VARIABLES ---

API_ID = environ.get('API_ID', '')
if not API_ID.isdigit():
    logger.error('API_ID is missing or invalid, exiting now')
    exit(1)
API_ID = int(API_ID)

API_HASH = environ.get('API_HASH', '')
if len(API_HASH) == 0:
    logger.error('API_HASH is missing, exiting now')
    exit(1)

BOT_TOKEN = environ.get('BOT_TOKEN', '')
if len(BOT_TOKEN) == 0:
    logger.error('BOT_TOKEN is missing, exiting now')
    exit(1)

try:
    BOT_ID = int(BOT_TOKEN.split(":")[0])
except ValueError:
    logger.error('BOT_TOKEN is invalid, exiting now')
    exit(1)

# Single Database URL (Files + Data merged)
DATA_DATABASE_URL = environ.get('DATA_DATABASE_URL', "")
if not DATA_DATABASE_URL.startswith('mongodb'):
    logger.error('DATA_DATABASE_URL is missing or invalid, exiting now')
    exit(1)

ADMINS_STR = environ.get('ADMINS', '')
if len(ADMINS_STR) == 0:
    logger.error('ADMINS is missing, exiting now')
    exit(1)
try:
    ADMINS = [int(admins) for admins in ADMINS_STR.split()]
except ValueError:
    logger.error('ADMINS must contain only integer IDs, exiting now')
    exit(1)

LOG_CHANNEL_STR = environ.get('LOG_CHANNEL', '')
if not LOG_CHANNEL_STR.lstrip('-').isdigit():
    logger.error('LOG_CHANNEL is missing, exiting now')
    exit(1)
LOG_CHANNEL = int(LOG_CHANNEL_STR)

BIN_CHANNEL_STR = environ.get("BIN_CHANNEL", "")
if not BIN_CHANNEL_STR.lstrip('-').isdigit():
    logger.error('BIN_CHANNEL is missing, exiting now')
    exit(1)
BIN_CHANNEL = int(BIN_CHANNEL_STR)

URL = environ.get("URL", "")
if len(URL) == 0:
    logger.error('URL is missing, exiting now')
    exit(1)
else:
    if URL.startswith(('https://', 'http://')):
        if not URL.endswith("/"):
            URL += '/'
    elif is_valid_ip(URL):
        URL = f'http://{URL}/'
    else:
        logger.error('URL is not valid, exiting now')
        exit(1)

# --- OPTIONAL VARIABLES (Fixed: No Error if Missing) ---

SUPPORT_GROUP_STR = environ.get('SUPPORT_GROUP', '')
SUPPORT_GROUP = int(SUPPORT_GROUP_STR) if SUPPORT_GROUP_STR.lstrip('-').isdigit() else None

AUTH_CHANNEL_STR = environ.get('AUTH_CHANNEL', '')
AUTH_CHANNEL = int(AUTH_CHANNEL_STR) if AUTH_CHANNEL_STR.lstrip('-').isdigit() else None

DB_CHANNEL_STR = environ.get('DB_CHANNEL', '')
DB_CHANNEL = int(DB_CHANNEL_STR) if DB_CHANNEL_STR.lstrip('-').isdigit() else None

PORT = int(environ.get('PORT', '8080'))
DATABASE_NAME = environ.get('DATABASE_NAME', "Cluster0")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files')

# Index Channels (Env Variable - Static)
INDEX_CHANNELS = [int(ch) if ch.lstrip('-').isdigit() else ch for ch in environ.get('INDEX_CHANNELS', '').split()]

SUPPORT_LINK = environ.get('SUPPORT_LINK', 'https://t.me/YourXCloud')
UPDATES_LINK = environ.get('UPDATES_LINK', 'https://t.me/YourXFiles')
FILMS_LINK = environ.get('FILMS_LINK', 'https://t.me/YourX')
TUTORIAL = environ.get("TUTORIAL", "https://t.me/YourX")
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "https://t.me/YourX")

PICS = environ.get('PICS', 'https://i.postimg.cc/8C15CQ5y/1.png https://i.postimg.cc/gcNtrv0m/2.png').split()

TIME_ZONE = environ.get('TIME_ZONE', 'Asia/Kolkata')
DELETE_TIME = int(environ.get('DELETE_TIME', 300)) # 5 Minutes Default
PM_FILE_DELETE_TIME = int(environ.get('PM_FILE_DELETE_TIME', 43200)) # 12 Hours Default
CACHE_TIME = int(environ.get('CACHE_TIME', 300))
MAX_BTN = int(environ.get('MAX_BTN', 10)) # Fixed to 10
VERIFY_EXPIRE = int(environ.get('VERIFY_EXPIRE', 86400))

# --- FEATURES (Toggles) ---
IS_STREAM = is_enabled('IS_STREAM', True)
PROTECT_CONTENT = is_enabled('PROTECT_CONTENT', True)
USE_CAPTION_FILTER = is_enabled('USE_CAPTION_FILTER', True)
IS_VERIFY = is_enabled('IS_VERIFY', True)
AUTO_DELETE = is_enabled('AUTO_DELETE', False)
WELCOME = is_enabled('WELCOME', False)
SPELL_CHECK = is_enabled("SPELL_CHECK", True)
LINK_MODE = is_enabled("LINK_MODE", True)

# --- QUALITY & LANGUAGE ---
LANGUAGES = [lang.lower() for lang in environ.get('LANGUAGES', 'hindi english telugu tamil kannada malayalam marathi punjabi').split()]
QUALITY = [quality.lower() for quality in environ.get('QUALITY', '360p 480p 720p 1080p 1440p 2160p').split()]

# --- DISABLED/REMOVED FEATURES (Kept Variables to prevent Import Errors) ---
IMDB = is_enabled('IMDB', False) 
SHORTLINK = is_enabled('SHORTLINK', False)
SHORTLINK_URL = environ.get("SHORTLINK_URL", "")
SHORTLINK_API = environ.get("SHORTLINK_API", "")
LONG_IMDB_DESCRIPTION = is_enabled("LONG_IMDB_DESCRIPTION", False)

# --- TEMPLATES ---
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", script.IMDB_TEMPLATE)
FILE_CAPTION = environ.get("FILE_CAPTION", script.FILE_CAPTION)
WELCOME_TEXT = environ.get("WELCOME_TEXT", script.WELCOME_TEXT)

# --- COSMETICS ---
REACTIONS = [reactions for reactions in environ.get('REACTIONS', '🤝 😇 🤗 😍 👍 🎅 😐 🥰 🤩 😱 🤣 😘 👏 😛 😈 🎉 ⚡️ 🫡 🤓 😎 🏆 🔥 🤭 🌚 🆒 👻 😁').split()]
STICKERS = [sticker for sticker in environ.get('STICKERS', 'CAACAgIAAxkBAAEN4ctnu1NdZUe21tiqF1CjLCZW8rJ28QACmQwAAj9UAUrPkwx5a8EilDYE').split()]

# --- PREMIUM SYSTEM ---
IS_PREMIUM = is_enabled('IS_PREMIUM', True)
PRE_DAY_AMOUNT = int(environ.get('PRE_DAY_AMOUNT', '10'))
UPI_ID = environ.get("UPI_ID", "YourX@SBI")
UPI_NAME = environ.get("UPI_NAME", "VIP")
RECEIPT_SEND_USERNAME = environ.get("RECEIPT_SEND_USERNAME", "@YourX")

if len(UPI_ID) == 0 or len(UPI_NAME) == 0:
    IS_PREMIUM = False
