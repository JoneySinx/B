import logging
import asyncio
import re
import requests
import pytz
from datetime import datetime, timezone, timedelta
from hydrogram.errors import UserNotParticipant, FloodWait, UserIsBlocked, InputUserDeactivated
from hydrogram.types import InlineKeyboardButton
from hydrogram import enums
from info import ADMINS, IS_PREMIUM, TIME_ZONE
from database.users_chats_db import db
from shortzy import Shortzy

# लॉगिंग सेट करें
logger = logging.getLogger(__name__)

class temp(object):
    START_TIME = 0
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    CANCEL = False
    U_NAME = None
    B_NAME = None
    SETTINGS = {}
    VERIFICATIONS = {}
    FILES = {}
    USERS_CANCEL = False
    GROUPS_CANCEL = False
    BOT = None
    PREMIUM = {}

# --- SUBSCRIPTION CHECKS (Request Feature Removed) ---

async def is_subscribed(bot, query):
    btn = []
    # प्रीमियम यूजर्स के लिए चेक स्किप करें
    if await is_premium(query.from_user.id, bot):
        return btn
        
    stg = await db.get_bot_sttgs()
    if not stg:
        return btn
        
    # सिर्फ Force Subscribe Check रखें (Request हटा दिया गया है)
    if stg.get('FORCE_SUB_CHANNELS'):
        for id in stg.get('FORCE_SUB_CHANNELS').split(' '):
            try:
                chat = await bot.get_chat(int(id))
                await bot.get_chat_member(int(id), query.from_user.id)
            except UserNotParticipant:
                btn.append(
                    [InlineKeyboardButton(f'Join : {chat.title}', url=chat.invite_link)]
                )
            except Exception as e:
                logger.error(f"Force Sub Error: {e}")
                pass
            
    return btn

async def is_check_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

# --- MEDIA UTILS ---

def upload_image(file_path):
    try:
        with open(file_path, 'rb') as f:
            files = {'files[]': f}
            response = requests.post("https://uguu.se/upload", files=files)
        if response.status_code == 200:
            data = response.json()
            return data['files'][0]['url'].replace('\\/', '/')
    except Exception as e:
        logger.error(f"Upload Image Error: {e}")
    return None

# --- VERIFICATION & PREMIUM ---

async def get_verify_status(user_id):
    verify = temp.VERIFICATIONS.get(user_id)
    if not verify:
        verify = await db.get_verify_status(user_id)
        temp.VERIFICATIONS[user_id] = verify
    return verify

async def update_verify_status(user_id, verify_token="", is_verified=False, link="", expire_time=0):
    current = await get_verify_status(user_id)
    current['verify_token'] = verify_token
    current['is_verified'] = is_verified
    current['link'] = link
    current['expire_time'] = expire_time
    temp.VERIFICATIONS[user_id] = current
    await db.update_verify_status(user_id, current)

async def is_premium(user_id, bot):
    if not IS_PREMIUM:
        return True
    if user_id in ADMINS:
        return True
    mp = await db.get_plan(user_id)
    if mp['premium']:
        # Fix: Offset-Aware Datetime Check
        expire_date = mp['expire']
        if isinstance(expire_date, datetime):
            if expire_date.tzinfo is None:
                expire_date = expire_date.replace(tzinfo=timezone.utc)
                
            if expire_date < datetime.now(timezone.utc):
                try: await bot.send_message(user_id, f"Your premium {mp['plan']} plan is expired, use /plan to activate again")
                except: pass
                
                mp['expire'] = ''
                mp['plan'] = ''
                mp['premium'] = False
                await db.update_plan(user_id, mp)
                return False
            return True
        else:
            mp['premium'] = False
            await db.update_plan(user_id, mp)
            return False
    else:
        return False

async def check_premium(bot):
    while True:
        await asyncio.sleep(1200)
        try:
            async for p in await db.get_premium_users():
                if not p['status']['premium']:
                    continue
                mp = p['status']
                
                expire_date = mp['expire']
                if isinstance(expire_date, datetime):
                    if expire_date.tzinfo is None:
                        expire_date = expire_date.replace(tzinfo=timezone.utc)

                    if expire_date < datetime.now(timezone.utc):
                        try: await bot.send_message(p['id'], f"Your premium {mp['plan']} plan is expired, use /plan to activate again")
                        except: pass
                        mp['expire'] = ''
                        mp['plan'] = ''
                        mp['premium'] = False
                        await db.update_plan(p['id'], mp)
        except Exception as e:
            logger.error(f"Check Premium Error: {e}")

# --- BROADCASTING ---

async def broadcast_messages(user_id, message, pin):
    try:
        m = await message.copy(chat_id=user_id)
        if pin:
            try: await m.pin(both_sides=True)
            except: pass
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message, pin)
    except (UserIsBlocked, InputUserDeactivated):
        await db.delete_user(int(user_id))
        return "Error"
    except Exception:
        return "Error"

async def groups_broadcast_messages(chat_id, message, pin):
    try:
        k = await message.copy(chat_id=chat_id)
        if pin:
            try: await k.pin()
            except: pass
        return "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await groups_broadcast_messages(chat_id, message, pin)
    except Exception:
        return "Error"

# --- SETTINGS & HELPERS ---

async def get_settings(group_id):
    settings = temp.SETTINGS.get(group_id)
    if not settings:
        settings = await db.get_settings(group_id)
        temp.SETTINGS.update({group_id: settings})
    return settings
    
async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current.update({key: value})
    temp.SETTINGS.update({group_id: current})
    await db.update_settings(group_id, current)

def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def list_to_str(k):
    if not k: return "N/A"
    elif len(k) == 1: return str(k[0])
    else: return ', '.join(f'{elem}' for elem in k)
    
async def get_shortlink(url, api, link):
    try:
        shortzy = Shortzy(api_key=api, base_site=url)
        link = await shortzy.convert(link)
        return link
    except Exception as e:
        logger.error(f"Shortlink Error: {e}")
        return link

def get_readable_time(seconds):
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result if result else '0s'

def get_wish():
    time = datetime.now(pytz.timezone(TIME_ZONE))
    now = time.strftime("%H")
    if now < "12": return "ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ 🌞"
    elif now < "18": return "ɢᴏᴏᴅ ᴀꜰᴛᴇʀɴᴏᴏɴ 🌗"
    else: return "ɢᴏᴏᴅ ᴇᴠᴇɴɪɴɢ 🌘"
    
def get_seconds(time_string):
    match = re.match(r'(\d+)([a-zA-Z]+)', time_string)
    if not match: return 0
    value = int(match.group(1))
    unit = match.group(2).lower()
    unit_multipliers = {'s': 1, 'min': 60, 'h': 3600, 'hour': 3600, 'd': 86400, 'day': 86400, 'month': 86400 * 30, 'year': 86400 * 365}
    return value * unit_multipliers.get(unit, 0)
