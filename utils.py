import logging
import asyncio
import re
import requests
import pytz
import functools
from datetime import datetime, timezone, timedelta
from hydrogram.errors import UserNotParticipant, FloodWait, UserIsBlocked, InputUserDeactivated
from hydrogram.types import InlineKeyboardButton
from hydrogram import enums
from info import LONG_IMDB_DESCRIPTION, ADMINS, IS_PREMIUM, TIME_ZONE, LOG_CHANNEL
from imdb import Cinemagoer
from database.users_chats_db import db
from shortzy import Shortzy

# लॉगिंग सेट करें
logger = logging.getLogger(__name__)
imdb = Cinemagoer() 

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

# --- SUBSCRIPTION & ADMIN CHECKS ---

async def is_subscribed(bot, query):
    btn = []
    if await is_premium(query.from_user.id, bot):
        return btn
        
    stg = await db.get_bot_sttgs()
    if not stg:
        return btn
        
    if stg.get('FORCE_SUB_CHANNELS'):
        for id in stg.get('FORCE_SUB_CHANNELS').split(' '):
            try:
                chat = await bot.get_chat(int(id))
                await bot.get_chat_member(int(id), query.from_user.id)
            except UserNotParticipant:
                btn.append([InlineKeyboardButton(f'Join : {chat.title}', url=chat.invite_link)])
            except Exception as e:
                logger.error(f"Force Sub Error: {e}")
                pass
    
    if stg.get('REQUEST_FORCE_SUB_CHANNELS') and not await db.find_join_req(query.from_user.id):
        try:
            id = int(stg.get('REQUEST_FORCE_SUB_CHANNELS'))
            chat = await bot.get_chat(id)
            await bot.get_chat_member(id, query.from_user.id)
        except UserNotParticipant:
            try:
                url = await bot.create_chat_invite_link(id, creates_join_request=True)
                btn.append([InlineKeyboardButton(f'Request : {chat.title}', url=url.invite_link)])
            except Exception as e:
                logger.error(f"Req Force Sub Error: {e}")
                pass
        except Exception:
            pass
            
    return btn

async def is_check_admin(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
    except:
        return False

# --- IMDB & MEDIA UTILS ---

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

async def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1]) 
        else:
            year = None
        
        func = functools.partial(imdb.search_movie, title.lower(), results=10)
        try: movieid = await asyncio.to_thread(func)
        except Exception as e:
            logger.error(f"IMDb Search Error: {e}")
            return None
        
        if not movieid: return None
        if year:
            filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
            if not filtered: filtered = movieid
        else: filtered = movieid
        
        movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
        if not movieid: movieid = filtered
        if bulk: return movieid
        if not movieid: return None
        movieid = movieid[0].movieID
    else:
        movieid = query
        
    func_get = functools.partial(imdb.get_movie, movieid)
    try: movie = await asyncio.to_thread(func_get)
    except Exception as e:
        logger.error(f"IMDb Get Movie Error: {e}")
        return None

    if movie.get("original air date"): date = movie["original air date"]
    elif movie.get("year"): date = movie.get("year")
    else: date = "N/A"
        
    plot = ""
    if not LONG_IMDB_DESCRIPTION:
        plot = movie.get('plot')
        if plot and len(plot) > 0: plot = plot[0]
    else:
        plot = movie.get('plot outline')
    if plot and len(plot) > 800: plot = plot[0:800] + "..."
        
    return {
        'title': movie.get('title'),
        'votes': movie.get('votes'),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(movie.get("runtimes")),
        "countries": list_to_str(movie.get("countries")),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_str(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer": list_to_str(movie.get("writer")),
        "producer": list_to_str(movie.get("producer")),
        "composer": list_to_str(movie.get("composer")),
        "cinematographer": list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        'release_date': date,
        'year': movie.get('year'),
        'genres': list_to_str(movie.get("genres")),
        'poster': movie.get('full-size cover url'),
        'plot': plot,
        'rating': str(movie.get("rating")),
        'url': f'https://www.imdb.com/title/tt{movieid}'
    }

# --- VERIFICATION & PREMIUM (Fixed Logic) ---

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
        # FIX: Handle Offset-Naive vs Offset-Aware
        expire_date = mp['expire']
        if isinstance(expire_date, datetime):
            if expire_date.tzinfo is None:
                # If DB date has no timezone, treat it as UTC
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
            # If expire date is invalid/empty but premium is True, treat as expired
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
                
                # FIX: Handle Offset-Naive vs Offset-Aware
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
