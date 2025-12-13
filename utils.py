import os
import re
import logging
import asyncio
import time
import math
import pytz
import aiohttp
from datetime import datetime, timezone, timedelta
from info import (
    LOG_CHANNEL, API_ID, API_HASH, BOT_TOKEN, 
    ADMINS, IS_PREMIUM, PRE_DAY_AMOUNT, PICS, 
    UPI_ID, UPI_NAME
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
    U_NAME = None   # Bot Username
    B_NAME = None   # Bot Name
    B_LINK = None   # Bot Link
    B_ID = None     # Bot ID
    BOT = None      # Client Instance
    
    FILES = {}      # Search Results Cache
    SETTINGS = {}   # Group Settings Cache
    
    # 🔥 DYNAMIC CONFIG CACHE (Reduced DB Calls)
    CONFIG = {}     
    
    CANCEL = False 
    CANCEL_BROADCAST = False
    MAINTENANCE = False
    
    BANNED_USERS = []
    BANNED_CHATS = []
    PREMIUM_REMINDERS = {} 
    
    BROADCAST_MSG = None # For Broadcast Command
    BROADCAST_SETTINGS = {}

# ==============================================================================
# ⚙️ GROUP SETTINGS MANAGER
# ==============================================================================
async def get_settings(group_id):
    # Memory Cache Check
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
    """
    Load dynamic settings from DB to Memory on Startup
    """
    conf = await db.get_config()
    temp.CONFIG = conf
    temp.MAINTENANCE = conf.get('is_maintenance', False)

# ==============================================================================
# ⏱️ TIME FORMATTER
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

# ==============================================================================
# 📦 SIZE FORMATTER
# ==============================================================================
def get_size(bytes, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f} {unit}{suffix}"
        bytes /= factor

# ==============================================================================
# 📢 BROADCAST ENGINE
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
        logging.info(f"{user_id} - Removed (Deleted Account).")
        return False, "Deleted"
    except UserIsBlocked:
        logging.info(f"{user_id} - Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error"
    except Exception as e:
        return False, "Error"

async def groups_broadcast_messages(chat_id, message):
    try:
        await message.copy(chat_id=chat_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await groups_broadcast_messages(chat_id, message)
    except Exception as e:
        return False, "Error"

# ==============================================================================
# 👮 ADMIN CHECKER
# ==============================================================================
async def is_check_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

# ==============================================================================
# 🔐 SUBSCRIPTION CHECKER (DYNAMIC)
# ==============================================================================
async def is_subscribed(client, message):
    # Fetch from DB Config first, fallback to ENV
    conf = await db.get_config()
    auth_channel = conf.get('auth_channel')
    
    if not auth_channel:
        return False # No channel set
        
    user_id = message.from_user.id
    
    try:
        user = await client.get_chat_member(int(auth_channel), user_id)
    except UserIsBlocked:
        return False # Bot blocked by user
    except Exception:
        pass # User not in channel (Err raised)
    else:
        if user.status not in [enums.ChatMemberStatus.BANNED, enums.ChatMemberStatus.LEFT]:
            return False # User is present (False means NO BUTTON needed)
    
    # If we reached here, User is NOT subscribed
    try:
        chat = await client.get_chat(int(auth_channel))
        link = chat.invite_link or f"https://t.me/{chat.username}"
    except Exception:
        return False # Bot is not admin in Auth Channel

    buttons = [[InlineKeyboardButton(f"🔥 Join {chat.title}", url=link)]]
    return buttons

# ==============================================================================
# 💎 PREMIUM CHECKER
# ==============================================================================
async def is_premium(user_id, client):
    conf = await db.get_config()
    if not conf.get('is_premium_active', True):
        return True 
    
    if user_id in ADMINS:
        return True
        
    user = await db.get_plan(user_id)
    if user.get('premium'):
        expire_date = user.get('expire')
        if expire_date and isinstance(expire_date, datetime):
            if expire_date.tzinfo is None:
                expire_date = expire_date.replace(tzinfo=timezone.utc)
            
            if datetime.now(timezone.utc) < expire_date:
                return True
            else:
                await db.update_plan(user_id, {'expire': '', 'trial': False, 'plan': '', 'premium': False})
                try: await client.send_message(user_id, "<b>⚠️ Your Premium Plan has Expired!</b>\nUse /plan to renew.")
                except: pass
                return False
        return True 
    return False

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
# 👋 WISHES & GREETINGS
# ==============================================================================
def get_wish():
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    t = now.strftime("%H")
    hour = int(t)
    if 0 <= hour < 12: return "Good Morning ☀️"
    elif 12 <= hour < 17: return "Good Afternoon 🌤"
    elif 17 <= hour < 21: return "Good Evening 🌆"
    else: return "Good Night 🌙"

# ==============================================================================
# 🔗 SHORTLINK & VERIFICATION UTILS
# ==============================================================================
async def get_shortlink(link):
    """
    Converts a link to Shortlink (Monetization)
    """
    conf = await db.get_config()
    if not conf.get('shortlink_enable'): return link
    
    api = conf.get('shortlink_api')
    site = conf.get('shortlink_site')
    
    if not api or not site: return link
        
    url = f"https://{site}/api?api={api}&url={link}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    res = await response.text()
                    if "http" in res: return res
    except Exception as e:
        logger.error(f"Shortlink Error: {e}")
        
    return link

async def check_verification(client, user_id):
    """
    Checks if user has valid verification token
    """
    conf = await db.get_config()
    if not conf.get('is_verify', False): return True
    
    user_status = await db.get_verify_status(user_id)
    if not user_status['is_verified']: return False
    
    # Check Expiry
    verified_time = user_status.get('verified_time') # Timestamp
    duration = conf.get('verify_duration', 86400) # Default 24h
    
    if time.time() - verified_time < duration:
        return True
    else:
        await update_verify_status(user_id, is_verified=False)
        return False

async def get_verify_short_link(link):
    """
    Generates shortlink for verification flow
    """
    conf = await db.get_config()
    api = conf.get('shortlink_api')
    site = conf.get('shortlink_site')
    
    if not api or not site: return link
    
    url = f"https://{site}/api?api={api}&url={link}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    res = await response.text()
                    if "http" in res: return res
    except: pass
    return link

async def update_verify_status(user_id, verify_token="", is_verified=False):
    """
    Updates DB verification status
    """
    now = time.time()
    await db.update_verify_status(user_id, verify_token, is_verified, now)
