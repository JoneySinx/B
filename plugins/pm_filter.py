import asyncio
import re
import math
import logging
import qrcode
import os
import random
import string
import urllib.parse
from time import time as time_now
from hydrogram.errors import MessageNotModified
from datetime import datetime
from info import ADMINS, MAX_BTN, IS_STREAM, DELETE_TIME, UPDATES_LINK
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram import Client, filters, enums
from utils import (
    is_premium, get_size, get_readable_time, temp, get_settings, 
    check_verification, get_verify_short_link, update_verify_status, is_subscribed
)
from database.users_chats_db import db
from database.ia_filterdb import get_search_results
from Script import script

logger = logging.getLogger(__name__)

# NOTE: BUTTONS dictionary is used to store the search session data across callbacks.
BUTTONS = {}
EXT_PATTERN = re.compile(r"\b(mkv|mp4|avi|m4v|webm|flv|mov|wmv|3gp|mpg|mpeg)\b", re.IGNORECASE)

# --- 🛠️ HELPER: GENERATE TOKEN ---
def get_random_token(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- 🔍 PM SEARCH HANDLER ---
@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message):
    if message.text.startswith("/"): return
    
    conf = await db.get_config()
    user_id = message.from_user.id
    
    # 1. 🚨 PANIC / MAINTENANCE CHECK
    if conf.get('is_maintenance') and user_id not in ADMINS:
        return await message.reply(f"<b>🚧 BOT UNDER MAINTENANCE 🚧</b>")

    # 2. 🤖 BOT MODE CHECK (PM Search Toggle)
    if not conf.get('pm_search', True) and user_id not in ADMINS:
        return await message.reply_text('<b>🚫 PM Search is Disabled!</b> Join Group to search.')

    # 3. 🔐 VERIFICATION SYSTEM (If Not Premium)
    is_prem = await is_premium(user_id, client)
    
    if not is_prem and conf.get('is_verify', False):
        is_verified = await check_verification(client, user_id)
        if not is_verified:
            token = get_random_token()
            await update_verify_status(user_id, verify_token=token, is_verified=False)
            
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
            short_link = await get_verify_short_link(verify_url)
            
            hours = int(conf.get('verify_duration', 86400) / 3600)
            btn = [[InlineKeyboardButton("✅ Verify Access (Click Here)", url=short_link)]]
            return await message.reply(
                f"<b>🔐 Access Denied!</b>\n\n"
                f"<i>Verify yourself to search files.</i>\n"
                f"<b>⏳ Validity:</b> {hours} Hours",
                reply_markup=InlineKeyboardMarkup(btn)
            )

    s = await message.reply(f"<b>🔍 Sᴇᴀʀᴄʜɪɴɢ... Pʟᴇᴀsᴇ Wᴀɪᴛ ✋</b>", quote=True, parse_mode=enums.ParseMode.HTML)
    await auto_filter(client, message, s)

# --- 🏘️ GROUP SEARCH HANDLER ---
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    if message.text.startswith("/"): return
    
    user_id = message.from_user.id if message.from_user else 0
    conf = await db.get_config()
    
    # Only process search if the user is premium OR if auto-filter is globally ON (as per old logic)
    if not await is_premium(user_id, client): return
    
    settings = await db.get_settings(message.chat.id)
    
    if settings.get('auto_filter', conf.get('global_auto_filter', True)):
        s = await message.reply(f"<b>🔍 Sᴇᴀʀᴄʜɪɴɢ... Pʟᴇᴀsᴇ Wᴀɪᴛ ✋</b>", parse_mode=enums.ParseMode.HTML)
        await auto_filter(client, message, s)
    # If filter is OFF, bot stays silent.

# --- 📄 AUTO FILTER CORE LOGIC ---
async def auto_filter(client, msg, s):
    message = msg
    settings = await db.get_settings(message.chat.id)
    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    conf = await db.get_config()
    
    # 1. Determine Search Mode (hybrid/primary/backup/fuzzy)
    mode = conf.get('search_mode', 'hybrid')
    
    # 2. Get Search Results
    files, offset, total_results = await get_search_results(search, mode=mode)
    
    # 3. Handle No Results / Spell Check
    if not files:
        # Note: Advanced Spell Check logic (changing search query) would go here
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(search)}"
        btn = [[InlineKeyboardButton("🔍 Cʜᴇᴄᴋ Sᴘᴇʟʟɪɴɢ ᴏɴ Gᴏᴏɢʟᴇ", url=google_search_url)]]
        await s.edit(f'<b>❌ Nᴏ Rᴇsᴜʟᴛs Fᴏᴜɴᴅ Fᴏʀ:</b> <code>{search}</code>\n\n<i>💡 Please check your spelling.</i>', reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
        return
        
    req = message.from_user.id if message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search
    
    # 4. Format Display Links
    files_link = ''
    for index, file in enumerate(files, start=1):
        f_name = EXT_PATTERN.sub("", file['file_name']).strip().title().replace(" L ", " l ")
        # Link Format: https://t.me/{BOT_USERNAME}?start=file_{CHAT_ID}_{FILE_ID}
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""
        
    btn = []
    
    # 5. Send All & Quality Buttons
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0") # Calls search_callbacks.py
    ])
    
    # 6. Pagination Buttons
    if offset != "":
        btn.append([
            InlineKeyboardButton(f"🗓 1/{math.ceil(int(total_results) / MAX_BTN)}", callback_data="buttons"),
            InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{offset}") # Calls search_callbacks.py
        ])
    
    # 7. Final Caption and Auto Delete Timer
    del_time = conf.get('delete_time', DELETE_TIME)
    del_msg = f"\n\n<b>⏳ Aᴜᴛᴏ Dᴇʟᴇᴛᴇ ɪɴ <code>{get_readable_time(del_time)}</code></b>" if settings.get("auto_delete") else ''
    
    cap = f"<b>✨ <u>Hᴇʀᴇ ɪs ᴡʜᴀᴛ ɪ ғᴏᴜɴᴅ</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i>\n<b>📂 Tᴏᴛᴀʟ:</b> {total_results}\n{files_link}"
    
    k = await s.edit_text(cap + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    
    # 8. Auto Delete Execution
    if settings.get("auto_delete"):
        # This is where the delete task should be spawned
        async def delete_search_message(msg_to_delete):
            await asyncio.sleep(del_time)
            try:
                await msg_to_delete.delete()
                # You might want to send a "Search Expired" message here
            except Exception as e:
                logger.error(f"Error deleting search msg: {e}")
                
        asyncio.create_task(delete_search_message(k))
