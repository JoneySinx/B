import os
import re
import logging
import asyncio
import time
import math
import pytz
import base64
import aiohttp
from datetime import datetime, timezone, timedelta
from info import (
    LOG_CHANNEL, API_ID, API_HASH, BOT_TOKEN, 
    ADMINS, IS_PREMIUM, PRE_DAY_AMOUNT, PICS, 
    UPI_ID, UPI_NAME, IS_VERIFY, VERIFY_EXPIRE,
    AUTH_CHANNEL
)
from hydrogram import enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from database.users_chats_db import db

logger = logging.getLogger(__name__)

# ==============================================================================
# 🧠 TEMP STORAGE (MEMORY CACHE)
# ==============================================================================
class temp(object):
    START_TIME = 0
    U_NAME = None
    B_NAME = None
    B_LINK = None
    B_ID = None
    BOT = None
    FILES = {}      
    SETTINGS = {}   
    CONFIG = {}     
    CANCEL = False 
    CANCEL_BROADCAST = False
    MAINTENANCE = False
    BANNED_USERS = []
    BANNED_CHATS = []
    PREMIUM_REMINDERS = {} 
    BROADCAST_MSG = None 
    BROADCAST_SETTINGS = {}

# ==============================================================================
# ⚙️ GROUP SETTINGS MANAGER
# ==============================================================================
async def get_settings(group_id):
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS[group_id] = settings
    return settings

async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current[key] = value
    temp.SETTINGS[group_id] = current
    await db.update_settings(group_id, current)

# ==============================================================================
# 🛠️ GLOBAL BOT CONFIG LOADER
# ==============================================================================
async def load_temp_config():
    conf = await db.get_config()
    temp.CONFIG = conf
    temp.MAINTENANCE = conf.get('is_maintenance', False)

# ==============================================================================
# ⏱️ TIME & SIZE FORMATTERS
# ==============================================================================
def get_readable_time(seconds: int) -> str:
    count = 0
    ping_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        ping_time += time_list.pop() + ", "
    time_list.reverse()
    ping_time += ":".join(time_list)
    return ping_time

def get_size(bytes, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f} {unit}{suffix}"
        bytes /= factor

# ==============================================================================
# 🔐 ENCODING / DECODING (DEEP LINKING)
# ==============================================================================
async def decode(base64_string):
    try:
        base64_bytes = base64_string.encode("ascii")
        string_bytes = base64.b64decode(base64_bytes) 
        string = string_bytes.decode("ascii")
        return string
    except:
        return base64_string

async def encode(string):
    try:
        string_bytes = string.encode("ascii")
        base64_bytes = base64.b64encode(string_bytes)
        base64_string = base64_bytes.decode("ascii")
        return base64_string
    except:
        return string

# ==============================================================================
# 🔐 VERIFICATION SYSTEM
# ==============================================================================
async def get_verify_status(user_id):
    """
    Check if user is verified.
    Returns: True (Verified/Disabled) | False (Need Verify)
    """
    if not IS_VERIFY:
        return True
        
    user = await db.get_user(user_id)
    if not user:
        return False
        
    verify_status = user.get('verify_status', {})
    expire_date = verify_status.get('expire', 0)
    
    if expire_date > time.time():
        return True
    
    return False

async def update_verify_status(user_id, verify_token="", is_verified=False):
    """Grant verification to user."""
    expire_time = time.time() + VERIFY_EXPIRE
    await db.update_verify_status(user_id, expire_time)
    return True

async def get_shortlink(link, api=None, url=None):
    """Generate Shortlink using API."""
    if not api or not url:
        return link
        
    try:
        async with aiohttp.ClientSession() as session:
            api_url = f"https://{url}/api?api={api}&url={link}"
            async with session.get(api_url) as response:
                data = await response.json()
                if "shortenedUrl" in data:
                    return data["shortenedUrl"]
    except Exception as e:
        logger.error(f"Shortlink Failed: {e}")
    return link

# ==============================================================================
# 💎 PREMIUM CHECKER
# ==============================================================================
async def is_premium(user_id, client=None):
    """Check if user has premium plan."""
    if not IS_PREMIUM:
        return False 
        
    user = await db.get_user(user_id)
    if not user: return False
    
    return user.get('status', {}).get('premium', False)

# ==============================================================================
# 📢 BROADCAST UTILS
# ==============================================================================
async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error"
    except Exception:
        return False, "Error"

# ==============================================================================
# 👮 ADMIN & SUBSCRIPTION (FORCE SUB)
# ==============================================================================
async def is_check_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

async def is_subscribed(client, message):
    # Fetch from DB Config first, fallback to ENV
    conf = await db.get_config()
    auth_channel = conf.get('auth_channel') or AUTH_CHANNEL
    
    if not auth_channel:
        return False 
        
    user_id = message.from_user.id
    try:
        user = await client.get_chat_member(int(auth_channel), user_id)
    except UserIsBlocked:
        return False
    except Exception:
        pass 
    else:
        if user.status not in [enums.ChatMemberStatus.BANNED, enums.ChatMemberStatus.LEFT]:
            return False # User IS subscribed (No need to show button)
    
    # User needs to join
    try:
        chat = await client.get_chat(int(auth_channel))
        link = chat.invite_link or f"https://t.me/{chat.username}"
    except Exception:
        return False 

    buttons = [[InlineKeyboardButton(f"🔥 Join {chat.title}", url=link)]]
    return buttons

# ==============================================================================
# 🖼️ IMAGE UPLOADER (GRAPH.ORG)
# ==============================================================================
async def upload_image(path):
    try:
        async with aiohttp.ClientSession() as session:
            with open(path, 'rb') as f:
                async with session.post('https://graph.org/upload', data={'file': f}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return f"https://graph.org{data[0]['src']}"
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        return None

# ==============================================================================
# 👋 GREETINGS
# ==============================================================================
def get_wish():
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    t = int(now.strftime("%H"))
    if 0 <= t < 12: return "Good Morning ☀️"
    elif 12 <= t < 17: return "Good Afternoon 🌤"
    elif 17 <= t < 21: return "Good Evening 🌆"
    else: return "Good Night 🌙"
