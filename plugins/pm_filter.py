import asyncio
import re
import math
import logging
import qrcode
import os
import urllib.parse
from time import time as time_now
from hydrogram.errors import ListenerTimeout, MessageNotModified
from datetime import datetime
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, UPI_ID, UPI_NAME,
    ADMINS, MAX_BTN, BIN_CHANNEL, IS_STREAM, DELETE_TIME, 
    FILMS_LINK, LOG_CHANNEL, SUPPORT_GROUP, UPDATES_LINK, QUALITY
)
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from hydrogram import Client, filters, enums
from utils import (
    is_premium, get_size, is_subscribed, is_check_admin, get_wish, 
    get_readable_time, temp, get_settings, save_group_settings
)
from database.users_chats_db import db
from database.ia_filterdb import get_search_results, delete_files, db_count_documents
from plugins.commands import get_grp_stg
from Script import script

logger = logging.getLogger(__name__)

BUTTONS = {}
CAP = {}

# --- 🔥 COMPILED REGEX FOR EXTENSIONS ---
# यह लिस्ट नाम में से mp4, mkv, avi को हटा देगी
EXT_PATTERN = re.compile(r"\b(mkv|mp4|avi|m4v|webm|flv|mov|wmv|3gp|mpg|mpeg)\b", re.IGNORECASE)

# --- 🔍 PM SEARCH HANDLER ---
@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message):
    if message.text.startswith("/"):
        return
        
    if not await is_premium(message.from_user.id, client):
        return

    stg = await db.get_bot_sttgs()
    if not stg: stg = {}
        
    if 'AUTO_FILTER' in stg and not stg.get('AUTO_FILTER'):
        return await message.reply_text('<b>🚫 Auto Filter is Globally Disabled by Admin!</b>')
        
    s = await message.reply(f"<b>🔍 Sᴇᴀʀᴄʜɪɴɢ... Pʟᴇᴀsᴇ Wᴀɪᴛ ✋</b>", quote=True, parse_mode=enums.ParseMode.HTML)
    await auto_filter(client, message, s)

# --- 🏘️ GROUP SEARCH HANDLER ---
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    user_id = message.from_user.id if message.from_user else 0
    
    if not await is_premium(user_id, client):
        return

    stg = await db.get_bot_sttgs()
    if not stg: stg = {'AUTO_FILTER': True}
        
    if stg.get('AUTO_FILTER', True):
        if message.chat.id == SUPPORT_GROUP:
            files, offset, total = await get_search_results(message.text)
            if files:
                btn = [[InlineKeyboardButton("📂 Get Files Here", url=FILMS_LINK)]]
                await message.reply_text(f'<b>✅ Fᴏᴜɴᴅ {total} Rᴇsᴜʟᴛs!</b>', reply_markup=InlineKeyboardMarkup(btn))
            return
            
        if message.text.startswith("/"): return
        
        if '@admin' in message.text.lower() or '@admins' in message.text.lower():
            if await is_check_admin(client, message.chat.id, message.from_user.id): return
            return

        elif re.findall(r'https?://\S+|www\.\S+|t\.me/\S+|@\w+', message.text):
            if await is_check_admin(client, message.chat.id, message.from_user.id): return
            try: await message.delete()
            except: pass
            return await message.reply('<b>⚠️ Lɪɴᴋs ᴀʀᴇ ɴᴏᴛ ᴀʟʟᴏᴡᴇᴅ ʜᴇʀᴇ!</b>')
        
        elif '#request' in message.text.lower():
            if message.from_user.id in ADMINS: return
            await client.send_message(LOG_CHANNEL, f"#Request\nUser: {message.from_user.mention}\nMsg: {message.text}")
            await message.reply_text("<b>✅ Rᴇǫᴜᴇsᴛ Sᴇɴᴛ Sᴜᴄᴄᴇssғᴜʟʟʏ!</b>")
            return  
        else:
            s = await message.reply(f"<b>🔍 Sᴇᴀʀᴄʜɪɴɢ... Pʟᴇᴀsᴇ Wᴀɪᴛ ✋</b>", parse_mode=enums.ParseMode.HTML)
            await auto_filter(client, message, s)
    else:
        k = await message.reply_text('<b>❌ Aᴜᴛᴏ Fɪʟᴛᴇʀ ɪs OFF!</b>')
        await asyncio.sleep(5)
        await k.delete()
        try: await message.delete()
        except: pass

# --- 📄 NEXT PAGE HANDLER ---
@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(f"🛑 Hᴇʏ {query.from_user.first_name}, Tʜɪs ɪs ɴᴏᴛ ғᴏʀ ʏᴏᴜ!", show_alert=True)
    try: offset = int(offset)
    except: offset = 0
    search = BUTTONS.get(key)
    if not search:
        await query.answer(f"❌ Sᴇssɪᴏɴ Exᴘɪʀᴇᴅ. Sᴇᴀʀᴄʜ Aɢᴀɪɴ!", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset)
    try: n_offset = int(n_offset)
    except: n_offset = 0

    if not files: return
    
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⏳ Aᴜᴛᴏ Dᴇʟᴇᴛᴇ ɪɴ <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for index, file in enumerate(files, start=offset+1):
        # 1. Remove Extensions
        f_name = EXT_PATTERN.sub("", file['file_name'])
        # 2. Clean Spaces
        f_name = re.sub(r"\s+", " ", f_name).strip()
        # 3. Title Case & L Fix
        f_name = f_name.title().replace(" L ", " l ")
        
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""

    btn = []
    
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])

    if 0 < offset <= MAX_BTN:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - MAX_BTN
        
    nav_btns = []
    if off_set is not None:
        nav_btns.append(InlineKeyboardButton("⏪ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"))
    
    nav_btns.append(InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"))
    
    if n_offset:
        nav_btns.append(InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{n_offset}"))
        
    btn.append(nav_btns)

    cap = f"<b>✨ <u>Hᴇʀᴇ ɪs ᴡʜᴀᴛ ɪ ғᴏᴜɴᴅ</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i>\n<b>📂 Tᴏᴛᴀʟ:</b> {total}\n{files_link}"
    
    try:
        await query.message.edit_text(cap + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified:
        pass

# --- 🔄 AUTO FILTER LOGIC ---
async def auto_filter(client, msg, s, spoll=False):
    message = msg
    settings = await get_settings(message.chat.id)
    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    files, offset, total_results = await get_search_results(search)
    
    if not files:
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(search)}"
        btn = [[InlineKeyboardButton("🔍 Cʜᴇᴄᴋ Sᴘᴇʟʟɪɴɢ ᴏɴ Gᴏᴏɢʟᴇ", url=google_search_url)]]
        await s.edit(
            f'<b>❌ Nᴏ Rᴇsᴜʟᴛs Fᴏᴜɴᴅ Fᴏʀ:</b> <code>{search}</code>\n\n'
            f'<i>💡 Please check your spelling on Google and try again.</i>',
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=enums.ParseMode.HTML
        )
        return

    req = message.from_user.id if message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search
    
    files_link = ''
    for index, file in enumerate(files, start=1):
        # 1. Remove Extensions
        f_name = EXT_PATTERN.sub("", file['file_name'])
        # 2. Clean Spaces
        f_name = re.sub(r"\s+", " ", f_name).strip()
        # 3. Title Case & L Fix
        f_name = f_name.title().replace(" L ", " l ")
        
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""
    
    btn = []
    
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0")
    ])

    if offset != "":
        btn.append([
            InlineKeyboardButton(f"🗓 1/{math.ceil(int(total_results) / MAX_BTN)}", callback_data="buttons"),
            InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{offset}")
        ])

    del_msg = f"\n\n<b>⏳ Aᴜᴛᴏ Dᴇʟᴇᴛᴇ ɪɴ <code>{get_readable_time(DELETE_TIME)}</code></b>" if settings["auto_delete"] else ''
    cap = f"<b>✨ <u>Hᴇʀᴇ ɪs ᴡʜᴀᴛ ɪ ғᴏᴜɴᴅ</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i>\n<b>📂 Tᴏᴛᴀʟ:</b> {total_results}\n{files_link}"

    k = await s.edit_text(cap + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    
    if settings["auto_delete"]:
        await asyncio.sleep(DELETE_TIME)
        try: await k.delete()
        except: pass
        try: await message.delete()
        except: pass
        
        btn_data = f"next_{req}_{key}_{offset if offset else 0}"
        btn = [[InlineKeyboardButton("♻️ Gᴇᴛ Fɪʟᴇs Aɢᴀɪɴ", callback_data=btn_data)]]
        
        gone_msg = await message.reply("<b>🗑️ Fɪʟᴇs Hᴀᴠᴇ Bᴇᴇɴ Dᴇʟᴇᴛᴇᴅ!</b>\n\n<i>Click the button below to retrieve them again.</i>", reply_markup=InlineKeyboardMarkup(btn))
        
        await asyncio.sleep(43200) # 12 Hours
        try: await gone_msg.delete()
        except: pass

# --- 🎥 QUALITY HANDLERS ---
@Client.on_callback_query(filters.regex(r"^quality"))
async def quality(client: Client, query: CallbackQuery):
    _, key, req, offset = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(f"🛑 Hᴇʏ {query.from_user.first_name}, Tʜɪs ɪs ɴᴏᴛ ғᴏʀ ʏᴏᴜ!", show_alert=True)
    
    btn = []
    for i in range(0, len(QUALITY), 3):
        row = []
        for j in range(3):
            if i + j < len(QUALITY):
                qual = QUALITY[i+j]
                row.append(InlineKeyboardButton(qual.upper(), callback_data=f"qual_search#{qual}#{key}#{offset}#{req}"))
        btn.append(row)
        
    btn.append([InlineKeyboardButton("⪻ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text("<b>🔽 Sᴇʟᴇᴄᴛ Rᴇsᴏʟᴜᴛɪᴏɴ / Qᴜᴀʟɪᴛʏ:</b>", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^qual_search"))
async def quality_search(client: Client, query: CallbackQuery):
    _, qual, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(f"🛑 Hᴇʏ {query.from_user.first_name}, Tʜɪs ɪs ɴᴏᴛ ғᴏʀ ʏᴏᴜ!", show_alert=True)
    
    search = BUTTONS.get(key)
    if not search:
        await query.answer("❌ Sᴇssɪᴏɴ Exᴘɪʀᴇᴅ. Sᴇᴀʀᴄʜ Aɢᴀɪɴ!", show_alert=True)
        return
        
    files, n_offset, total = await get_search_results(search, lang=qual)
    
    if not files:
        await query.answer(f"❌ Nᴏ Fɪʟᴇs Fᴏᴜɴᴅ ғᴏʀ {qual}!", show_alert=True)
        return

    files_link = ''
    for index, file in enumerate(files, start=1):
        # 1. Remove Extensions
        f_name = EXT_PATTERN.sub("", file['file_name'])
        # 2. Clean Spaces
        f_name = re.sub(r"\s+", " ", f_name).strip()
        # 3. Title Case & L Fix
        f_name = f_name.title().replace(" L ", " l ")
        
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""

    btn = []
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    
    btn.append([InlineKeyboardButton("⪻ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    
    cap = f"<b>✨ <u>Fɪʟᴛᴇʀᴇᴅ Rᴇsᴜʟᴛs</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i> ({qual.upper()})\n<b>📂 Tᴏᴛᴀʟ:</b> {total}\n{files_link}"
    
    await query.message.edit_text(cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

# --- 🎛️ MAIN CALLBACK HANDLER ---
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if not query.message:
        return await query.answer("⚠️ Message not found (too old).", show_alert=True)

    if query.data.startswith("close_data"):
        await query.message.delete()
        try: await query.message.reply_to_message.delete()
        except: pass
        
        if "#" in query.data:
            try:
                warn_id = int(query.data.split("#")[1])
                await client.delete_messages(chat_id=query.message.chat.id, message_ids=warn_id)
            except: pass

    elif query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")

    elif query.data.startswith("get_del_file"):
        ident, group_id, file_id = query.data.split("#")
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{group_id}_{file_id}")

    elif query.data.startswith("stream"):
        file_id = query.data.split('#', 1)[1]
        msg = await client.send_cached_media(chat_id=BIN_CHANNEL, file_id=file_id)
        from info import URL as SITE_URL
        base_url = SITE_URL[:-1] if SITE_URL.endswith('/') else SITE_URL
        watch = f"{base_url}/watch/{msg.id}"
        download = f"{base_url}/download/{msg.id}"
        btn=[[
            InlineKeyboardButton("🎬 Wᴀᴛᴄʜ Oɴʟɪɴᴇ", url=watch),
            InlineKeyboardButton("⚡ Fᴀsᴛ Dᴏᴡɴʟᴏᴀᴅ", url=download)
        ],[
            InlineKeyboardButton('❌ Cʟᴏsᴇ', callback_data='close_data')
        ]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    elif query.data == 'activate_plan':
        q = await query.message.edit("<b>📅 Hᴏᴡ ᴍᴀɴʏ ᴅᴀʏs ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʙᴜʏ Pʀᴇᴍɪᴜᴍ?</b>\n\n<i>🔢 Send the number of days (e.g., 30, 365)</i>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            days = int(msg.text)
        except ListenerTimeout:
            await q.delete()
            return await query.message.reply("<b>⏳ Tɪᴍᴇ Oᴜᴛ! Pʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.</b>")
        except ValueError:
            await q.delete()
            return await query.message.reply("<b>❌ Iɴᴠᴀʟɪᴅ Iɴᴘᴜᴛ! Pʟᴇᴀsᴇ sᴇɴᴅ ᴏɴʟʏ ɴᴜᴍʙᴇʀs.</b>")
        except Exception:
            await q.delete()
            return
            
        transaction_note = f'{days} Days Premium for {query.from_user.id}'
        amount = days * PRE_DAY_AMOUNT
        upi_link = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR&tn={transaction_note}"
        
        qr = qrcode.make(upi_link)
        qr_path = f"upi_qr_{query.from_user.id}.png"
        qr.save(qr_path)
        await q.delete()
        
        caption = (f"<b>💳 <u>Pᴀʏᴍᴇɴᴛ Gᴀᴛᴇᴡᴀʏ</u></b>\n\n"
                   f"<b>🗓 Pʟᴀɴ:</b> {days} Days\n"
                   f"<b>💰 Aᴍᴏᴜɴᴛ:</b> ₹{amount}\n"
                   f"<b>🆔 UPI ID:</b> <code>{UPI_ID}</code>\n\n"
                   f"<i>📲 Scan QR to pay & send screenshot here.</i>")
        try:
            await query.message.reply_photo(photo=qr_path, caption=caption)
        except:
            await query.message.reply("❌ Error generating QR.")
        finally:
            if os.path.exists(qr_path): os.remove(qr_path)
                
        try:
            receipt = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=600)
            if receipt.photo or receipt.document:
                btn = [[InlineKeyboardButton(f"✅ Confirm Payment ({days} Days)", callback_data=f"confirm_pay#{query.from_user.id}#{days}")]]
                await receipt.copy(
                    chat_id=RECEIPT_SEND_USERNAME, 
                    caption=f"<b>💰 Nᴇᴡ Pᴀʏᴍᴇɴᴛ Rᴇᴄᴇɪᴠᴇᴅ!</b>\n\n👤 <b>Usᴇʀ:</b> {query.from_user.mention}\n🆔 <b>ID:</b> <code>{query.from_user.id}</code>\n🗓 <b>Rᴇǫᴜᴇsᴛ:</b> {days} Days",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                await query.message.reply("<b>✅ Rᴇᴄᴇɪᴘᴛ Sᴇɴᴛ! Pʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ Aᴅᴍɪɴ Aᴘᴘʀᴏᴠᴀʟ.</b>")
            else:
                await query.message.reply("<b>❌ Iɴᴠᴀʟɪᴅ Rᴇᴄᴇɪᴘᴛ! Tʀᴀɴsᴀᴄᴛɪᴏɴ Fᴀɪʟᴇᴅ.</b>")
        except ListenerTimeout:
            await query.message.reply(f"<b>⏳ Sᴇssɪᴏɴ Exᴘɪʀᴇᴅ!</b>\nSend screenshot manually to {RECEIPT_SEND_USERNAME}")

    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton('👨‍🚒 Help', callback_data='help'),
            InlineKeyboardButton('📚 Status 📊', callback_data='stats')
        ]]
        try:
            await query.message.edit_text(script.START_TXT.format(query.from_user.mention, get_wish()), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif query.data == "help":
        buttons = [[
            InlineKeyboardButton('🙋🏻‍♀️ User', callback_data='user_command'),
            InlineKeyboardButton('🦹 Admin', callback_data='admin_command')
        ],[
            InlineKeyboardButton('🏄 Back', callback_data='start')
        ]]
        try:
            await query.message.edit_text(script.HELP_TXT.format(query.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except MessageNotModified:
            pass

    elif query.data == "user_command":
        buttons = [[InlineKeyboardButton('🏄 Back', callback_data='help')]]
        await query.message.edit_text(script.USER_COMMAND_TXT, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        
    elif query.data == "admin_command":
        if query.from_user.id not in ADMINS:
            return await query.answer("🛑 ADMINS Only!", show_alert=True)
        buttons = [[InlineKeyboardButton('🏄 Back', callback_data='help')]]
        await query.message.edit_text(script.ADMIN_COMMAND_TXT, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

    elif query.data == "stats":
        if query.from_user.id not in ADMINS:
            return await query.answer("🛑 ADMINS Only!", show_alert=True)
        files = await db_count_documents()
        users = await db.total_users_count()
        chats = await db.total_chat_count()
        prm = await db.get_premium_count()
        used_bytes, free_bytes = await db.get_db_size()
        used = get_size(used_bytes)
        free = get_size(free_bytes)
        uptime = get_readable_time(time_now() - temp.START_TIME)
        buttons = [[InlineKeyboardButton('🏄 Back', callback_data='start')]]
        await query.message.edit_text(script.STATUS_TXT.format(files, users, chats, prm, used, free, uptime), reply_markup=InlineKeyboardMarkup(buttons))

    elif query.data.startswith("bool_setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        userid = query.from_user.id
        if not await is_check_admin(client, int(grp_id), userid):
            await query.answer("🛑 You are not Admin!", show_alert=True)
            return
        await save_group_settings(int(grp_id), set_type, status != "True")
        btn = await get_grp_stg(int(grp_id))
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
    
    elif query.data == "open_group_settings":
        userid = query.from_user.id
        if not await is_check_admin(client, query.message.chat.id, userid): return
        btn = await get_grp_stg(query.message.chat.id)
        await query.message.edit(text=f"Settings for <b>{query.message.chat.title}</b>", reply_markup=InlineKeyboardMarkup(btn))

    elif query.data.startswith("checksub"):
        ident, mc = query.data.split("#")
        btn = await is_subscribed(client, query)
        if btn:
            await query.answer(f"🛑 Hᴇʏ {query.from_user.first_name},\nPʟᴇᴀsᴇ Jᴏɪɴ Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Fɪʀsᴛ!", show_alert=True)
            btn.append([InlineKeyboardButton("🔁 Try Again 🔁", callback_data=f"checksub#{mc}")])
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
            return
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={mc}")
        await query.message.delete()
    
    elif query.data == "delete_all":
        await query.message.edit("<b>🗑️ Dᴇʟᴇᴛɪɴɢ Aʟʟ Fɪʟᴇs...</b>\n<i>This may take a while.</i>")
        total = await delete_files("") 
        await query.message.edit(f"<b>✅ Dᴇʟᴇᴛᴇᴅ {total} Fɪʟᴇs ғʀᴏᴍ Dᴀᴛᴀʙᴀsᴇ.</b>")

    elif query.data.startswith("delete_"):
        _, query_ = query.data.split("_", 1)
        await query.message.edit(f"<b>🗑️ Dᴇʟᴇᴛɪɴɢ Fɪʟᴇs Mᴀᴛᴄʜɪɴɢ:</b> <code>{query_}</code>...")
        total = await delete_files(query_)
        await query.message.edit(f"<b>✅ Dᴇʟᴇᴛᴇᴅ {total} Fɪʟᴇs Mᴀᴛᴄʜɪɴɢ '{query_}'</b>")
