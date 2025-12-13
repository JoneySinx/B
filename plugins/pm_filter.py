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
from hydrogram.errors import ListenerTimeout, MessageNotModified
from datetime import datetime
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, UPI_ID, UPI_NAME,
    ADMINS, MAX_BTN, BIN_CHANNEL, IS_STREAM, DELETE_TIME, 
    FILMS_LINK, LOG_CHANNEL, SUPPORT_GROUP, UPDATES_LINK, QUALITY
)
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from hydrogram import Client, filters, enums
from utils import (
    is_premium, get_size, is_subscribed, is_check_admin, get_wish, 
    get_readable_time, temp, get_settings, save_group_settings, upload_image,
    check_verification, get_verify_short_link, update_verify_status
)
from database.users_chats_db import db
from database.ia_filterdb import get_search_results, delete_files, db_count_documents
from plugins.commands import get_grp_stg
from Script import script

logger = logging.getLogger(__name__)

BUTTONS = {}
CAP = {}
EXT_PATTERN = re.compile(r"\b(mkv|mp4|avi|m4v|webm|flv|mov|wmv|3gp|mpg|mpeg)\b", re.IGNORECASE)

# --- 🛠️ HELPER: GENERATE TOKEN ---
def get_random_token(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- 🔍 PM SEARCH HANDLER ---
@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message):
    if message.text.startswith("/"): return
    
    conf = await db.get_config()
    
    # 1. 🚨 PANIC / MAINTENANCE CHECK (Dynamic Reason)
    if conf.get('is_maintenance') and message.from_user.id not in ADMINS:
        reason = conf.get('maintenance_reason', "Updating Server... Please Wait.")
        return await message.reply(f"<b>🚧 BOT UNDER MAINTENANCE 🚧</b>\n\n<i>Reason: {reason}</i>")

    # 2. 💎 PREMIUM USER CHECK (Skip Verify)
    is_prem = await is_premium(message.from_user.id, client)
    
    # 3. 🔐 VERIFICATION SYSTEM (If Not Premium)
    if not is_prem and conf.get('is_verify', False):
        is_verified = await check_verification(client, message.from_user.id)
        if not is_verified:
            token = get_random_token()
            await update_verify_status(message.from_user.id, verify_token=token, is_verified=False)
            
            # Generate Link
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
            short_link = await get_verify_short_link(verify_url)
            
            hours = int(conf.get('verify_duration', 86400) / 3600)
            btn = [[InlineKeyboardButton("✅ Verify Access (Click Here)", url=short_link)]]
            return await message.reply(
                f"<b>🔐 Access Denied!</b>\n\n"
                f"<i>You need to verify yourself to search files.</i>\n"
                f"<i>This helps us keep the bot free!</i>\n\n"
                f"<b>⏳ Validity:</b> {hours} Hours",
                reply_markup=InlineKeyboardMarkup(btn)
            )

    # 4. GLOBAL FILTER CHECK
    stg = await db.get_bot_sttgs()
    if not stg: stg = {}
    if 'AUTO_FILTER' in stg and not stg.get('AUTO_FILTER'):
        return await message.reply_text('<b>🚫 Auto Filter is Globally Disabled!</b>')
        
    s = await message.reply(f"<b>🔍 Sᴇᴀʀᴄʜɪɴɢ... Pʟᴇᴀsᴇ Wᴀɪᴛ ✋</b>", quote=True, parse_mode=enums.ParseMode.HTML)
    await auto_filter(client, message, s)

# --- 🏘️ GROUP SEARCH HANDLER ---
@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    try:
        current_chat_id = int(message.chat.id)
        if isinstance(SUPPORT_GROUP, list): config_support_id = int(SUPPORT_GROUP[0])
        elif SUPPORT_GROUP: config_support_id = int(SUPPORT_GROUP)
        else: config_support_id = 0
        
        if config_support_id != 0 and current_chat_id == config_support_id:
            if re.findall(r'https?://\S+|www\.\S+|t\.me/\S+', message.text):
                async def delete_link():
                    await asyncio.sleep(300)
                    try: await message.delete()
                    except: pass
                asyncio.create_task(delete_link())
            return 
    except: pass

    user_id = message.from_user.id if message.from_user else 0
    if not await is_premium(user_id, client): return

    stg = await db.get_bot_sttgs()
    if not stg: stg = {'AUTO_FILTER': True}
        
    if stg.get('AUTO_FILTER', True):
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
        try: await k.delete(); await message.delete()
        except: pass

# --- 📄 AUTO FILTER & PAGINATION ---
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
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid')
    files, n_offset, total = await get_search_results(search, offset=offset, mode=mode)
    try: n_offset = int(n_offset)
    except: n_offset = 0
    if not files: return
    settings = await get_settings(query.message.chat.id)
    
    # 🔥 DYNAMIC DELETE TIME
    del_time = conf.get('delete_time', DELETE_TIME)
    del_msg = f"\n\n<b>⏳ Aᴜᴛᴏ Dᴇʟᴇᴛᴇ ɪɴ <code>{get_readable_time(del_time)}</code></b>" if settings["auto_delete"] else ''
    
    files_link = ''
    for index, file in enumerate(files, start=offset+1):
        f_name = EXT_PATTERN.sub("", file['file_name']).strip().title().replace(" L ", " l ")
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""
    btn = []
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    if 0 < offset <= MAX_BTN: off_set = 0
    elif offset == 0: off_set = None
    else: off_set = offset - MAX_BTN
    nav_btns = []
    if off_set is not None: nav_btns.append(InlineKeyboardButton("⏪ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{off_set}"))
    nav_btns.append(InlineKeyboardButton(f"🗓 {math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"))
    if n_offset: nav_btns.append(InlineKeyboardButton("Nᴇxᴛ ⏩", callback_data=f"next_{req}_{key}_{n_offset}"))
    btn.append(nav_btns)
    cap = f"<b>✨ <u>Hᴇʀᴇ ɪs ᴡʜᴀᴛ ɪ ғᴏᴜɴᴅ</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i>\n<b>📂 Tᴏᴛᴀʟ:</b> {total}\n{files_link}"
    try: await query.message.edit_text(cap + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    except MessageNotModified: pass

async def auto_filter(client, msg, s, spoll=False):
    message = msg
    settings = await get_settings(message.chat.id)
    search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid')
    files, offset, total_results = await get_search_results(search, mode=mode)
    if not files:
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(search)}"
        btn = [[InlineKeyboardButton("🔍 Cʜᴇᴄᴋ Sᴘᴇʟʟɪɴɢ ᴏɴ Gᴏᴏɢʟᴇ", url=google_search_url)]]
        await s.edit(f'<b>❌ Nᴏ Rᴇsᴜʟᴛs Fᴏᴜɴᴅ Fᴏʀ:</b> <code>{search}</code>\n\n<i>💡 Please check your spelling.</i>', reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
        return
    req = message.from_user.id if message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search
    files_link = ''
    for index, file in enumerate(files, start=1):
        f_name = EXT_PATTERN.sub("", file['file_name']).strip().title().replace(" L ", " l ")
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
    
    # 🔥 DYNAMIC DELETE TIME
    del_time = conf.get('delete_time', DELETE_TIME)
    del_msg = f"\n\n<b>⏳ Aᴜᴛᴏ Dᴇʟᴇᴛᴇ ɪɴ <code>{get_readable_time(del_time)}</code></b>" if settings["auto_delete"] else ''
    
    cap = f"<b>✨ <u>Hᴇʀᴇ ɪs ᴡʜᴀᴛ ɪ ғᴏᴜɴᴅ</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i>\n<b>📂 Tᴏᴛᴀʟ:</b> {total_results}\n{files_link}"
    k = await s.edit_text(cap + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
    
    if settings["auto_delete"]:
        await asyncio.sleep(del_time)
        try: await k.delete(); await message.delete()
        except: pass
        btn_data = f"next_{req}_{key}_{offset if offset else 0}"
        btn = [[InlineKeyboardButton("♻️ Gᴇᴛ Fɪʟᴇs Aɢᴀɪɴ", callback_data=btn_data)]]
        gone_msg = await message.reply("<b>🗑️ Fɪʟᴇs Dᴇʟᴇᴛᴇᴅ!</b>", reply_markup=InlineKeyboardMarkup(btn))
        await asyncio.sleep(43200)
        try: await gone_msg.delete()
        except: pass

@Client.on_callback_query(filters.regex(r"^quality"))
async def quality(client: Client, query: CallbackQuery):
    _, key, req, offset = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(f"🛑 Not for you!", show_alert=True)
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
    if int(req) != query.from_user.id: return await query.answer(f"🛑 Not for you!", show_alert=True)
    search = BUTTONS.get(key)
    if not search: return await query.answer("❌ Session Expired!", show_alert=True)
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid')
    files, n_offset, total = await get_search_results(search, lang=qual, mode=mode)
    if not files: return await query.answer(f"❌ No Files Found for {qual}!", show_alert=True)
    files_link = ''
    for index, file in enumerate(files, start=1):
        f_name = EXT_PATTERN.sub("", file['file_name']).strip().title().replace(" L ", " l ")
        files_link += f"""\n\n<b>{index}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {f_name}</a></b>"""
    btn = []
    btn.insert(0, [
        InlineKeyboardButton("♻️ Sᴇɴᴅ Aʟʟ", url=f"https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}"),
        InlineKeyboardButton("⚙️ Qᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")
    ])
    btn.append([InlineKeyboardButton("⪻ Bᴀᴄᴋ", callback_data=f"next_{req}_{key}_{offset}")])
    cap = f"<b>✨ <u>Fɪʟᴛᴇʀᴇᴅ Rᴇsᴜʟᴛs</u></b>\n\n<b>🔍 Qᴜᴇʀʏ:</b> <i>{search}</i> ({qual.upper()})\n<b>📂 Tᴏᴛᴀʟ:</b> {total}\n{files_link}"
    await query.message.edit_text(cap, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

# ==============================================================================
# 🎛️ GOD MODE ADMIN PANEL (MAIN HANDLER)
# ==============================================================================
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    if not query.message:
        return await query.answer("⚠️ Message not found.", show_alert=True)

    # 🛠️ ADMIN ENTRY
    if query.data.startswith("admin_"):
        if query.from_user.id not in ADMINS:
            return await query.answer("🚫 Access Denied!", show_alert=True)

        # 1. MAIN DATABASE MENU
        if query.data == "admin_db_menu":
            conf = await db.get_config()
            curr = conf.get('search_mode', 'hybrid').upper()
            btn = [[InlineKeyboardButton(f"{'✅' if curr=='PRIMARY' else ''} Primary", callback_data="set_db_mode#primary"), InlineKeyboardButton(f"{'✅' if curr=='BACKUP' else ''} Backup", callback_data="set_db_mode#backup")], [InlineKeyboardButton(f"{'✅' if curr=='HYBRID' else ''} Hybrid", callback_data="set_db_mode#hybrid")], [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]]
            await query.message.edit(f"<b>🗄️ Database Manager</b>\n\nMode: <b>{curr}</b>", reply_markup=InlineKeyboardMarkup(btn))

        # 2. CHANNEL & CONTENT MENU
        elif query.data == "admin_channel_menu":
            conf = await db.get_config()
            auth = conf.get('auth_channel', 'None')
            log = conf.get('req_channel', 'None')
            btn = [
                [InlineKeyboardButton("📢 Auth Channel", callback_data="set_channel#auth"), InlineKeyboardButton("📝 Log Channel", callback_data="set_channel#log")], 
                [InlineKeyboardButton("📝 Global Caption", callback_data="set_global_caption"), InlineKeyboardButton("👋 Global Welcome", callback_data="set_global_welcome")], 
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit(f"<b>📺 Channel & Content Config</b>\n\n<b>🔐 Auth Channel:</b> `{auth}`\n<b>📜 Log Channel:</b> `{log}`", reply_markup=InlineKeyboardMarkup(btn))

        # 3. PAYMENT SETTINGS
        elif query.data == "admin_payment_menu":
            conf = await db.get_config()
            upi = conf.get('upi_id', UPI_ID)
            amt = conf.get('pay_amount', PRE_DAY_AMOUNT)
            rec_user = conf.get('receipt_user', RECEIPT_SEND_USERNAME)
            
            btn = [
                [InlineKeyboardButton("✏️ Set UPI", callback_data="set_pay#upi"), InlineKeyboardButton("💰 Set Amount", callback_data="set_pay#amt")],
                [InlineKeyboardButton("📩 Set Receipt User", callback_data="set_pay#receipt"), InlineKeyboardButton("🖼️ Set QR Code", callback_data="set_pay#qr")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit(f"<b>💰 Payment Settings</b>\n\n<b>UPI:</b> `{upi}`\n<b>Amount:</b> ₹{amt}/day\n<b>Receipt User:</b> `{rec_user}`", reply_markup=InlineKeyboardMarkup(btn))

        # 4. IMAGE MANAGER
        elif query.data == "admin_image_menu":
            btn = [
                [InlineKeyboardButton("🖼️ Set Start Pics", callback_data="set_images#start")],
                [InlineKeyboardButton("👋 Set Welcome Pic", callback_data="set_images#welcome")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit("<b>🖼️ Image Manager</b>\n\nSet custom images for Start and Welcome.", reply_markup=InlineKeyboardMarkup(btn))

        # 5. BOT & SYSTEM SETTINGS
        elif query.data == "admin_bot_settings":
            conf = await db.get_config()
            maint = "🔴" if conf.get('is_maintenance') else "🟢"
            prem = "🟢" if conf.get('is_premium_active', True) else "🔴"
            prot = "🟢" if conf.get('is_protect_content', True) else "🔴"
            del_time = conf.get('delete_time', DELETE_TIME)
            
            btn = [
                [InlineKeyboardButton(f"Maintenance: {maint}", callback_data="toggle_bot#maint")],
                [InlineKeyboardButton(f"Premium Mode: {prem}", callback_data="toggle_bot#prem"), InlineKeyboardButton(f"Content Protect: {prot}", callback_data="toggle_bot#prot")],
                [InlineKeyboardButton(f"⏳ Auto-Delete: {get_readable_time(del_time)}", callback_data="set_del_time")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit("<b>🛡️ General Bot Settings</b>\n\nToggle core features and timers.", reply_markup=InlineKeyboardMarkup(btn))

        # 6. VERIFICATION (ADS) MENU
        elif query.data == "admin_verify_menu":
            conf = await db.get_config()
            status = "🟢 ON" if conf.get('is_verify') else "🔴 OFF"
            dur = int(conf.get('verify_duration', 86400)) / 3600
            
            btn = [
                [InlineKeyboardButton(f"Verify Status: {status}", callback_data="toggle_verify")],
                [InlineKeyboardButton("⏱️ Set Validity Time", callback_data="set_verify_time")],
                [InlineKeyboardButton("🔗 Shortner Settings", callback_data="admin_shortner_menu")], 
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit(f"<b>🔐 Verification (Ads) System</b>\n\n<b>Status:</b> {status}\n<b>Validity:</b> {dur} Hours\n\n<i>Force users to complete shortlink.</i>", reply_markup=InlineKeyboardMarkup(btn))

        # 7. TEMPLATE (MOOD) MANAGER
        elif query.data == "admin_template_menu":
            btn = [
                [InlineKeyboardButton("📝 Edit Start Msg", callback_data="set_tpl#start_msg")],
                [InlineKeyboardButton("📝 Edit Help Msg", callback_data="set_tpl#help_msg")],
                [InlineKeyboardButton("📝 Edit Maintenance Reason", callback_data="set_tpl#maintenance_reason")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit("<b>🎭 Template Manager</b>\n\nChange bot messages dynamically.", reply_markup=InlineKeyboardMarkup(btn))

        # 8. PANIC MODE
        elif query.data == "admin_panic_mode":
            btn = [[InlineKeyboardButton("🚨 ENABLE LOCKDOWN 🚨", callback_data="panic_confirm")], [InlineKeyboardButton("🔙 Cancel", callback_data="back_to_admin")]]
            await query.message.edit("<b>⚠️ PANIC MODE</b>\n\nStop bot for EVERYONE except Admins.", reply_markup=InlineKeyboardMarkup(btn))

        # 9. SHORTNER & CLONE (Legacy)
        elif query.data == "admin_shortner_menu":
            conf = await db.get_config()
            status = "🟢" if conf.get('shortlink_enable') else "🔴"
            btn = [[InlineKeyboardButton(f"Status: {status}", callback_data="toggle_shortner")], [InlineKeyboardButton("Set API", callback_data="set_short#api"), InlineKeyboardButton("Set Site", callback_data="set_short#site")], [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]]
            await query.message.edit("<b>🔗 Shortlink Settings</b>", reply_markup=InlineKeyboardMarkup(btn))

        elif query.data == "admin_clone_menu":
             conf = await db.get_config()
             status = "🟢" if not conf.get('disable_clone') else "🔴"
             btn = [[InlineKeyboardButton(f"Clone Maker: {status}", callback_data="toggle_clone_status")], [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]]
             await query.message.edit("<b>🤖 Clone Manager</b>", reply_markup=InlineKeyboardMarkup(btn))

    # --- ACTIONS & SETTERS ---
    elif query.data == "back_to_admin":
        await cb_handler(client, type('obj', (object,), {'data': 'admin_settings', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

    # 🔥 TEMPLATE SETTER
    elif query.data.startswith("set_tpl#"):
        key = query.data.split("#")[1]
        await query.message.edit(f"<b>📝 Send New {key.upper()}:</b>\n\nVariables: `{{mention}}`, `{{id}}`\n<i>HTML Supported.</i>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=300)
            text = msg.text or msg.caption
            if text:
                await db.update_config(f"tpl_{key}" if key != 'maintenance_reason' else 'maintenance_reason', text)
                await query.message.edit("<b>✅ Template Updated!</b>")
            else: await query.message.edit("<b>❌ Text required!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    # 🔥 VERIFY ACTIONS
    elif query.data == "toggle_verify":
        conf = await db.get_config()
        await db.update_config('is_verify', not conf.get('is_verify'))
        await cb_handler(client, type('obj', (object,), {'data': 'admin_verify_menu', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

    elif query.data == "set_verify_time":
        await query.message.edit("<b>⏱️ Send Validity Duration in HOURS:</b>\n(e.g., `24` for 1 day)")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            hours = int(msg.text)
            await db.update_config('verify_duration', hours * 3600)
            await query.message.edit(f"<b>✅ Duration Set:</b> {hours} Hours")
        except: await query.message.edit("<b>❌ Invalid Input!</b>")

    # 🔥 PANIC CONFIRM
    elif query.data == "panic_confirm":
        await db.update_config('is_maintenance', True)
        await query.message.edit("<b>🚨 BOT IS NOW IN LOCKDOWN MODE! 🚨</b>")

    # 🔥 PAYMENT SETTERS
    elif query.data.startswith("set_pay#"):
        target = query.data.split("#")[1]
        prompts = {'upi': 'Send UPI ID', 'amt': 'Send Amount', 'qr': 'Send QR Photo', 'receipt': 'Send Receipt Username (@user)'}
        await query.message.edit(f"<b>💰 {prompts[target]}:</b>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            if target == 'qr':
                if msg.photo:
                    path = await msg.download()
                    url = await upload_image(path)
                    os.remove(path)
                    if url:
                        await db.update_config('payment_qr', url)
                        await query.message.edit("<b>✅ QR Updated!</b>")
                else: await query.message.edit("<b>❌ Send a Photo!</b>")
            else:
                val = int(msg.text) if target == 'amt' else msg.text
                keys = {'amt': 'pay_amount', 'upi': 'upi_id', 'receipt': 'receipt_user'}
                await db.update_config(keys[target], val)
                await query.message.edit(f"<b>✅ Updated!</b> {val}")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    # 🔥 IMAGE SETTERS
    elif query.data.startswith("set_images#"):
        target = query.data.split("#")[1]
        await query.message.edit(f"<b>🖼️ Send New {target.title()} Image:</b>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            if msg.photo:
                path = await msg.download()
                url = await upload_image(path)
                os.remove(path)
                if url:
                    key = 'start_pics' if target == 'start' else 'welcome_pic'
                    val = [url] if target == 'start' else url
                    await db.update_config(key, val)
                    await query.message.edit("<b>✅ Image Updated!</b>")
            else: await query.message.edit("<b>❌ Send a Photo!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    # 🔥 GLOBAL SETTINGS (Bot Toggles)
    elif query.data.startswith("toggle_bot#"):
        target = query.data.split("#")[1]
        keys = {'maint': 'is_maintenance', 'prem': 'is_premium_active', 'prot': 'is_protect_content'}
        conf = await db.get_config()
        curr = conf.get(keys[target], False if target=='maint' else True)
        await db.update_config(keys[target], not curr)
        await cb_handler(client, type('obj', (object,), {'data': 'admin_bot_settings', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

    elif query.data == "set_del_time":
        await query.message.edit("<b>⏳ Send Auto-Delete Time (Seconds):</b>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            t = int(msg.text)
            await db.update_config('delete_time', t)
            await query.message.edit(f"<b>✅ Time Updated:</b> {get_readable_time(t)}")
        except: await query.message.edit("<b>❌ Invalid Number!</b>")

    # --- EXISTING HANDLERS ---
    elif query.data.startswith("set_db_mode#"):
        mode = query.data.split("#")[1]
        await db.update_config('search_mode', mode)
        await query.answer(f"✅ Mode: {mode.upper()}", show_alert=True)
        await cb_handler(client, type('obj', (object,), {'data': 'admin_db_menu', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

    elif query.data.startswith("set_channel#"):
        target = query.data.split("#")[1]
        await query.message.edit(f"<b>📝 Send {target.upper()} Channel ID:</b>\n\nFormat: `-100xxxx`")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            chat_id = int(msg.text)
            await db.update_config(f"{target}_channel" if target == 'auth' else 'req_channel', chat_id)
            await query.message.edit("<b>✅ Channel Set!</b>")
        except: await query.message.edit("<b>❌ Invalid!</b>")

    elif query.data == "set_global_caption":
        await query.message.edit("<b>📝 Send Global Caption:</b>\n\nVars: `{file_name}`, `{file_size}`")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            await db.update_config('global_caption', msg.text)
            await query.message.edit("<b>✅ Global Caption Set!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data == "set_global_welcome":
        await query.message.edit("<b>👋 Send Global Welcome Text:</b>\n\nVars: `{mention}`, `{title}`")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            await db.update_config('welcome_text', msg.text)
            await query.message.edit("<b>✅ Global Welcome Text Set!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data == "toggle_shortner":
        conf = await db.get_config()
        curr = conf.get('shortlink_enable', False)
        await db.update_config('shortlink_enable', not curr)
        await cb_handler(client, type('obj', (object,), {'data': 'admin_shortner_menu', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

    elif query.data.startswith("set_short#"):
        target = query.data.split("#")[1]
        await query.message.edit(f"<b>✏️ Send {target.upper()}:</b>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            await db.update_config(f"shortlink_{target}", msg.text.strip())
            await query.message.edit("<b>✅ Updated!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data == "toggle_clone_status":
        conf = await db.get_config()
        curr = conf.get('disable_clone', False)
        await db.update_config('disable_clone', not curr)
        await cb_handler(client, type('obj', (object,), {'data': 'admin_clone_menu', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

    elif query.data.startswith("close_data"):
        await query.message.delete()
        try: await query.message.reply_to_message.delete()
        except: pass

    # ... (Keep existing User Command/Help/Clone handlers as is) ...
    # [Ensure previous handlers like 'start', 'help', 'stats', 'file#', 'stream#' are present here]
    # For brevity, I'm assuming you kept the standard user handlers from previous code blocks.
    # They don't change with this update.
    
    # ... [Insert Standard User Handlers Here] ...
    
    # 🔥 Payment Activation (Final Check)
    elif query.data == 'activate_plan':
        conf = await db.get_config()
        upi = conf.get('upi_id', UPI_ID)
        amt = int(conf.get('pay_amount', PRE_DAY_AMOUNT))
        qr_url = conf.get('payment_qr') 
        rec_user = conf.get('receipt_user', RECEIPT_SEND_USERNAME)
        
        q = await query.message.edit("<b>📅 Days?</b>\n<i>Send number (e.g. 30)</i>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            days = int(msg.text)
        except: return await q.delete()
        
        total = days * amt
        upi_link = f"upi://pay?pa={upi}&pn={UPI_NAME}&am={total}&cu=INR&tn={days}DaysPremium"
        
        caption = f"<b>💳 Pay ₹{total}</b>\nScan QR or Pay to: <code>{upi}</code>\n\n📸 Send screenshot to: {rec_user}"
        
        if qr_url:
            await query.message.reply_photo(qr_url, caption=caption)
        else:
            qr = qrcode.make(upi_link)
            qr.save("temp_qr.png")
            await query.message.reply_photo("temp_qr.png", caption=caption)
            os.remove("temp_qr.png")
        await q.delete()
