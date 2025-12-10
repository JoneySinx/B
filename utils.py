import os
import re
import logging
import asyncio
import time
import math
from datetime import datetime
from pytz import timezone
from info import (
    LOG_CHANNEL, API_ID, API_HASH, BOT_TOKEN, 
    ADMINS, IS_PREMIUM, PRE_DAY_AMOUNT, PICS, 
    UPI_ID, UPI_NAME, AUTH_CHANNEL, DB_CHANNEL
)
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from database.users_chats_db import db

logger = logging.getLogger(__name__)

# --- TEMP STORAGE ---
class temp(object):
    START_TIME = 0
    U_NAME = None
    B_NAME = None
    B_LINK = None
    B_ID = None
    BOT = None # Bot Instance for Web
    FILES = {} # For storing search results
    CANCEL = False # For indexing cancellation
    MAINTENANCE = False # Future use

# --- TIME FORMATTER ---
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

# --- SIZE FORMATTER ---
def get_size(bytes, suffix="B"):
    factor = 1024
    for unit in ["", "K", "M", "G", "T", "P"]:
        if bytes < factor:
            return f"{bytes:.2f} {unit}{suffix}"
        bytes /= factor

# --- BROADCAST FUNCTIONS (ADDED FIX) ---
async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - Removed from Database, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        logging.info(f"{user_id} - Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception as e:
        return False, "Error"

async def groups_broadcast_messages(group_id, message):
    try:
        await message.copy(chat_id=group_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await groups_broadcast_messages(group_id, message)
    except Exception as e:
        await db.delete_chat(int(group_id))
        logging.info(f"{group_id} - {e}")
        return False, "Error"

# --- ADMIN CHECKER ---
async def is_check_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

# --- SUBSCRIPTION CHECKER ---
async def is_subscribed(client, message):
    if not AUTH_CHANNEL:
        return False
    try:
        user = await client.get_chat_member(AUTH_CHANNEL, message.from_user.id)
    except Exception:
        pass
    else:
        if user.status != enums.ChatMemberStatus.BANNED:
            return False
    
    # Check Dynamic F-Sub (if set in DB)
    stg = await db.get_bot_sttgs()
    if stg and stg.get('FORCE_SUB_CHANNELS'):
        channels = stg['FORCE_SUB_CHANNELS'].split()
        links = []
        for channel in channels:
            try:
                chat = await client.get_chat(int(channel))
                link = chat.invite_link or f"https://t.me/{chat.username}"
                links.append([InlineKeyboardButton(f"Join {chat.title}", url=link)])
            except:
                pass
        return links
    return False

# --- PREMIUM CHECKER ---
async def is_premium(user_id, client):
    if not IS_PREMIUM:
        return True 
    
    if user_id in ADMINS:
        return True
        
    user = await db.get_plan(user_id)
    if user.get('premium'):
        expire_date = user.get('expire')
        if expire_date and isinstance(expire_date, datetime):
            if datetime.now(timezone.utc) < expire_date:
                return True
            else:
                await db.update_plan(user_id, {'expire': '', 'trial': False, 'plan': '', 'premium': False})
                try: await client.send_message(user_id, "<b>Your Premium Plan has Expired!</b>\nUse /plan to renew.")
                except: pass
                return False
        return True 
    return False

# --- IMAGE UPLOADER ---
import requests
def upload_image(path):
    try:
        return None 
    except:
        return None

# --- WISHES ---
def get_wish():
    now = datetime.now(timezone("Asia/Kolkata"))
    t = now.strftime("%H")
    hour = int(t)
    if 0 <= hour < 12:
        return "Good Morning ☀️"
    elif 12 <= hour < 17:
        return "Good Afternoon 🌤"
    elif 17 <= hour < 21:
        return "Good Evening 🌆"
    else:
        return "Good Night 🌙"

# --- SHORTLINK (Dummy - Removed) ---
async def get_shortlink(url, api, link):
    return link 

# --- VERIFY STATUS ---
async def get_verify_status(user_id):
    verify = await db.get_verify_status(user_id)
    return verify

async def update_verify_status(user_id, verify_token="", is_verified=False, link="", expire_time=0):
    await db.update_verify_status(user_id, verify_token, is_verified, link, expire_time)
