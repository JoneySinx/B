import asyncio
import re
import math
import logging
from hydrogram.errors import MessageNotModified
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram import Client, filters, enums
from info import ADMINS, MAX_BTN, QUALITY, DELETE_TIME
from database.users_chats_db import db
from database.ia_filterdb import get_search_results # For new search based on quality/page
from utils import get_size, get_readable_time, temp, get_settings

logger = logging.getLogger(__name__)

# Note: BUTTONS dictionary is usually defined in pm_filter.py and imported here.
# Assuming 'BUTTONS' is correctly imported/accessed from pm_filter.py for session management.
BUTTONS = {} # Placeholder for the imported dictionary

# ==============================================================================
# 📄 NEXT PAGE HANDLER (PAGINATION)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query: CallbackQuery):
    # Ident: 'next', Req: User ID, Key: Session Key, Offset: Next Start Index
    ident, req, key, offset = query.data.split("_")
    
    # 1. Access Check (Optional, but good practice)
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(f"🛑 Hey, Tʜɪs ɪs ɴᴏᴛ ғᴏʀ ʏᴏᴜ!", show_alert=True)
    
    try: offset = int(offset)
    except: offset = 0
    
    search = BUTTONS.get(key)
    if not search:
        await query.answer(f"❌ Sᴇssɪᴏɴ Exᴘɪʀᴇᴅ. Sᴇᴀʀᴄʜ Aɢᴀɪɴ!", show_alert=True)
        return

    # 2. Fetch Results for Next Page
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid')
    files, n_offset, total = await get_search_results(search, offset=offset, mode=mode)
    
    if not files: return # Should not happen

    settings = await get_settings(query.message.chat.id)
    del_time = conf.get('delete_time', DELETE_TIME)
    del_msg = f"\n\n<b>⏳ Aᴜᴛᴏ Dᴇʟᴇᴛᴇ ɪɴ <code>{get_readable_time(del_time)}</code></b>" if settings.get("auto_delete") else ''
    
    # 3. Format Links
    files_link = ''
    for index, file in enumerate(files, start=offset + 1):
        f_name = file['file_name'].replace(" L ", " l ") # Simple name cleaning
        # Link Format: https://t.me/{BOT_USERNAME}?start=file_{CHAT_ID}_{FILE_ID}
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""
    
    # 4. Build Navigation Buttons
    off_set = offset - MAX_BTN if offset > MAX_BTN else None
    
    nav_btns = []
    if off_set is not None: 
        nav_btns.append(InlineKeyboardButton("⏪ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"))
    
    # Current Page number: (offset / MAX_BTN) + 1
    current_page = math.ceil(offset / MAX_BTN) + 1
    total_pages = math.ceil(total / MAX_BTN)
    
    nav_btns.append(InlineKeyboardButton(f"🗓 {current_page}/{total_pages}", callback_data="buttons"))
    
    if n_offset: 
        nav_btns.append(InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{n_offset}"))
    
    btn = []
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    btn.append(nav_btns)
    
    cap = f"<b>✨ <u>Hᴇʀᴇ ɪs ᴡʜᴀᴛ ɪ ғᴏᴜɴᴅ</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i>\n<b>📂 Tᴏᴛᴀʟ:</b> {total}\n{files_link}"
    
    # 5. Edit Message
    try: 
        await query.message.edit_text(
            cap + del_msg, 
            reply_markup=InlineKeyboardMarkup(btn), 
            parse_mode=enums.ParseMode.HTML
        )
    except MessageNotModified: 
        await query.answer("Already on this page.")
        pass

# ==============================================================================
# ⚙️ QUALITY HANDLERS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^quality"))
async def quality(client: Client, query: CallbackQuery):
    _, key, req, offset = query.data.split("#")
    
    if int(req) != query.from_user.id:
        return await query.answer(f"🛑 Not for you!", show_alert=True)
        
    btn = []
    # Dynamic button generation for quality filter options
    for i in range(0, len(QUALITY), 3):
        row = []
        for j in range(3):
            if i + j < len(QUALITY):
                qual = QUALITY[i+j]
                # Calls the new quality search logic
                row.append(InlineKeyboardButton(qual.upper(), callback_data=f"qual_search#{qual}#{key}#{offset}#{req}"))
        btn.append(row)
        
    # Back button goes to the current page (offset)
    btn.append([InlineKeyboardButton("⪻ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    
    await query.message.edit_text(
        "<b>🔽 Sᴇʟᴇᴄᴛ Rᴇsᴏʟᴜᴛɪᴏɴ / Qᴜᴀʟɪᴛʏ:</b>", 
        reply_markup=InlineKeyboardMarkup(btn), 
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_callback_query(filters.regex(r"^qual_search"))
async def quality_search(client: Client, query: CallbackQuery):
    _, qual, key, offset, req = query.data.split("#")
    
    if int(req) != query.from_user.id: return await query.answer(f"🛑 Not for you!", show_alert=True)
    search = BUTTONS.get(key)
    if not search: return await query.answer("❌ Session Expired!", show_alert=True)
    
    await query.answer(f"🔍 Searching for {search} in {qual.upper()}...", show_alert=True)
    
    # 1. Fetch Filtered Results (Need to pass 'qual' to get_search_results)
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid')
    # NOTE: get_search_results needs modification to accept quality/lang filter
    # Assuming the quality filter works by passing 'lang=qual'
    
    files, n_offset, total = await get_search_results(search, lang=qual, mode=mode) 
    
    if not files: return await query.answer(f"❌ No Files Found for {qual}!", show_alert=True)
    
    # 2. Prepare Display
    files_link = ''
    for index, file in enumerate(files, start=1):
        f_name = file['file_name'].replace(" L ", " l ")
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""
        
    # 3. Build Buttons (Go back to quality selector or main list)
    btn = []
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    
    # Link back to the main search result page
    btn.append([InlineKeyboardButton("⪻ Bᴀᴄᴋ Tᴏ Rᴇsᴜʟᴛs", callback_data=f"next_{req}_{key}_{offset}")])
    
    cap = f"<b>✨ <u>Fɪʟᴛᴇʀᴇᴅ Rᴇsᴜʟᴛs</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i> ({qual.upper()})\n<b>📂 Tᴏᴛᴀʟ:</b> {total}\n{files_link}"
    
    await query.message.edit_text(
        cap, 
        reply_markup=InlineKeyboardMarkup(btn), 
        parse_mode=enums.ParseMode.HTML
    )
