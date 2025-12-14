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
# 🚨 MOST IMPORTANT VARIABLES (CREDENTIALS)
# ==============================================================================

# 1. Telegram API & Token
API_ID = int(environ.get('API_ID', '0'))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', '')

# 2. Database (Primary & Backup)
DATABASE_URI = environ.get('DATA_DATABASE_URL', "") or environ.get('DATABASE_URI', "")
BACKUP_DATABASE_URI = environ.get('BACKUP_DATABASE_URI', "") # Optional
DATABASE_NAME = environ.get('DATABASE_NAME', "FastFinder")
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'Files')

# 3. Admins & Owner
try:
    ADMINS = [int(x) for x in environ.get('ADMINS', '').split()]
except ValueError:
    logger.error('❌ ADMINS list is missing! Exiting...')
    exit(1)

# 4. Critical Channels
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '0'))
BIN_CHANNEL = int(environ.get("BIN_CHANNEL", "0"))

# 5. Server URL
URL = environ.get("URL", "")
PORT = int(environ.get('PORT', '8080'))
if not URL: logger.error('❌ URL (Server Link) is missing!')
elif not URL.endswith("/"): URL += "/"

# Safety Check
if API_ID == 0 or not API_HASH or not BOT_TOKEN or not DATABASE_URI:
    logger.error('❌ CRITICAL ERROR: API_ID, API_HASH, BOT_TOKEN, or DATABASE_URI is missing!')
    exit(1)

# ==============================================================================
# 🎮 DYNAMIC FEATURES (MANAGED VIA ADMIN PANEL)
# ==============================================================================
# नोट: ये सब Default False हैं ताकि आप इन्हें Admin Panel से कंट्रोल कर सकें।
# अगर आपको ENV से Force On करना है, तो Config में True सेट करें।

# 1. Verification & Shortlinks (Ads)
IS_VERIFY = is_enabled('IS_VERIFY', False)
SHORTLINK = is_enabled('SHORTLINK', False)
SHORTLINK_URL = environ.get("SHORTLINK_URL", "")
SHORTLINK_API = environ.get("SHORTLINK_API", "")
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "")
VERIFY_EXPIRE = int(environ.get("VERIFY_EXPIRE", 86400)) # 24 Hours

# 2. Premium & Payments
IS_PREMIUM = is_enabled('IS_PREMIUM', False) # Default False, Enable via DB/Env
PRE_DAY_AMOUNT = int(environ.get('PRE_DAY_AMOUNT', '10'))
UPI_ID = environ.get("UPI_ID", "")
UPI_NAME = environ.get("UPI_NAME", "FastFinder Payment")
RECEIPT_SEND_USERNAME = environ.get("RECEIPT_SEND_USERNAME", "")
PAYMENT_QR = environ.get("PAYMENT_QR", "") 

# 3. Security & Stream
PROTECT_CONTENT = is_enabled('PROTECT_CONTENT', False) # Forwards Restricted?
AUTO_DELETE = is_enabled('AUTO_DELETE', False) # Auto delete file from group?
IS_STREAM = is_enabled('IS_STREAM', True) # Stream Link (Keep True mostly)
DISABLE_CLONE = is_enabled('DISABLE_CLONE', False) # Allow users to clone?

# ==============================================================================
# ⚙️ ADVANCED CHANNELS & SETTINGS
# ==============================================================================

# Channels
AUTH_CHANNEL = int(environ.get('AUTH_CHANNEL', '0')) # Force Sub
DB_CHANNEL = int(environ.get('DB_CHANNEL', '0')) # Legacy
SUPPORT_GROUP = [int(x) for x in environ.get('SUPPORT_GROUP', '').split() if x.lstrip('-').isdigit()]

# Timers
TIME_ZONE = environ.get('TIME_ZONE', 'Asia/Kolkata')
DELETE_TIME = int(environ.get('DELETE_TIME', 300))
PM_FILE_DELETE_TIME = int(environ.get('PM_FILE_DELETE_TIME', 43200))
CACHE_TIME = int(environ.get('CACHE_TIME', 300))

# Search Behavior
MAX_BTN = int(environ.get('MAX_BTN', 10)) 
USE_CAPTION_FILTER = is_enabled('USE_CAPTION_FILTER', True)
SPELL_CHECK = is_enabled("SPELL_CHECK", True)
LINK_MODE = is_enabled("LINK_MODE", True)
DUAL_SAVE_MODE = is_enabled('DUAL_SAVE_MODE', True)

# Indexing
INDEX_CHANNELS = [int(x) for x in environ.get('INDEX_CHANNELS', '').split() if x.lstrip('-').isdigit()]

# ==============================================================================
# 🎨 LINKS & COSMETICS
# ==============================================================================

SUPPORT_LINK = environ.get('SUPPORT_LINK', 'https://t.me/YourSupport')
UPDATES_LINK = environ.get('UPDATES_LINK', 'https://t.me/YourUpdates')
FILMS_LINK = environ.get('FILMS_LINK', 'https://t.me/YourChannel')
TUTORIAL = environ.get("TUTORIAL", "https://t.me/")

PICS = environ.get('PICS', 'https://graph.org/file/5a676b7337373f0083906.jpg').split()
REACTIONS = environ.get('REACTIONS', '👍 ❤️ 🔥 🥰 👏 ⚡ 🤩').split()
STICKERS = environ.get('STICKERS', 'CAACAgIAAxkBAAEN4ctnu1NdZUe21tiqF1CjLCZW8rJ28QACmQwAAj9UAUrPkwx5a8EilDYE').split()

# Languages
LANGUAGES = [l.lower() for l in environ.get('LANGUAGES', 'hindi english telugu tamil kannada malayalam marathi').split()]
QUALITY = [q.lower() for q in environ.get('QUALITY', '360p 480p 720p 1080p 1440p 2160p 4k').split()]

# Legacy / Unused (Kept for compatibility)
IMDB = is_enabled('IMDB', False)
LONG_IMDB_DESCRIPTION = is_enabled('LONG_IMDB_DESCRIPTION', False)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", script.IMDB_TEMPLATE)
FILE_CAPTION = environ.get("FILE_CAPTION", script.FILE_CAPTION)
WELCOME_TEXT = environ.get("WELCOME_TEXT", script.WELCOME_TEXT)
