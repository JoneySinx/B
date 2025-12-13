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
    check_verification, get_verify_short_link, update_verify_status, broadcast_messages
)
from database.users_chats_db import db
from database.ia_filterdb import get_search_results, delete_files, delete_one_file, db_count_documents
from plugins.commands import get_grp_stg
from Script import script

logger = logging.getLogger(__name__)

BUTTONS = {}
CAP = {}
EXT_PATTERN = re.compile(r"\b(mkv|mp4|avi|m4v|webm|flv|mov|wmv|3gp|mpg|mpeg)\b", re.IGNORECASE)

# --- 🛠️ HELPER: GENERATE TOKEN ---
def get_random_token(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# --- 🚀 BROADCAST RUNNER (Background Task) ---
async def run_broadcast(client, message, admin_id):
    users = await db.get_all_users()
    total, success, blocked, deleted, failed = 0, 0, 0, 0, 0
    start_time = time_now()
    
    async for user in users:
        total += 1
        sts, msg = await broadcast_messages(user['_id'], message)
        if sts: success += 1
        elif msg == "Blocked": blocked += 1
        elif msg == "Deleted": deleted += 1
        else: failed += 1
    
    completed_in = get_readable_time(time_now() - start_time)
    await client.send_message(admin_id, f"<b>📢 Broadcast Completed!</b>\n\n<b>⏱️ Time:</b> {completed_in}\n<b>👥 Total:</b> {total}\n<b>✅ Success:</b> {success}\n<b>🚫 Blocked:</b> {blocked}\n<b>🗑️ Deleted:</b> {deleted}")

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
            
            # Delete Mode Toggle
            d_mode = conf.get('delete_mode', 'interactive')
            d_mode_txt = "🖱️ Interactive" if d_mode == 'interactive' else "⚠ General (Bulk)"
            
            btn = [
                [InlineKeyboardButton(f"Maintenance: {maint}", callback_data="toggle_bot#maint")],
                [InlineKeyboardButton(f"Premium Mode: {prem}", callback_data="toggle_bot#prem"), InlineKeyboardButton(f"Content Protect: {prot}", callback_data="toggle_bot#prot")],
                [InlineKeyboardButton(f"🗑️ Del Mode: {d_mode_txt}", callback_data="toggle_del_mode")], 
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
        
        # 9. BROADCAST MANAGER (NEW)
        elif query.data == "admin_broadcast_menu":
            btn = [
                [InlineKeyboardButton("📢 Broadcast Message", callback_data="broadcast_setup")],
                [InlineKeyboardButton("🔍 Search User Info", callback_data="search_user_setup")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_admin")]
            ]
            await query.message.edit("<b>📢 Communication Manager</b>\n\nSend messages or check user details.", reply_markup=InlineKeyboardMarkup(btn))

        # 10. SHORTNER & CLONE
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

    # 🔥 BROADCAST LOGIC
    elif query.data == "broadcast_setup":
        await query.message.edit("<b>📢 Send the Message to Broadcast:</b>\n\n<i>(Text, Photo, Video - Anything)</i>\n\nType /cancel to stop.")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=300)
            if msg.text == "/cancel": return await query.message.edit("❌ Cancelled.")
            temp.BROADCAST_MSG = msg # Save to temp
            btn = [[InlineKeyboardButton("✅ Confirm & Send", callback_data="broadcast_confirm")], [InlineKeyboardButton("❌ Cancel", callback_data="back_to_admin")]]
            await query.message.reply("<b>⚠️ Ready to Send!</b>", reply_markup=InlineKeyboardMarkup(btn))
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data == "broadcast_confirm":
        if not hasattr(temp, 'BROADCAST_MSG') or not temp.BROADCAST_MSG: return await query.answer("❌ Error: No message!", show_alert=True)
        await query.message.edit("<b>🚀 Broadcasting Started...</b>\n<i>You will get a log when finished.</i>")
        asyncio.create_task(run_broadcast(client, temp.BROADCAST_MSG, query.from_user.id))

    # 🔥 USER SEARCH LOGIC
    elif query.data == "search_user_setup":
        await query.message.edit("<b>🔍 Send User ID:</b>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            user_id = int(msg.text)
            u = await client.get_users(user_id)
            db_u = await db.is_user_exist(user_id)
            prem = await is_premium(user_id, client)
            verify = await db.get_verify_status(user_id)
            text = (f"<b>👤 User Info</b>\n\n<b>Name:</b> {u.mention}\n<b>ID:</b> <code>{u.id}</code>\n<b>In DB:</b> {db_u}\n<b>Premium:</b> {prem}\n<b>Verified:</b> {verify['is_verified']}")
            btn = [[InlineKeyboardButton("🚫 BAN", callback_data=f"ban_user#{user_id}"), InlineKeyboardButton("✅ UNBAN", callback_data=f"unban_user#{user_id}")]]
            await query.message.reply(text, reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e: await query.message.edit(f"<b>❌ User Not Found!</b>\n{e}")

    elif query.data.startswith("ban_user#"):
        user_id = int(query.data.split("#")[1])
        await db.add_banned_user(user_id) 
        temp.BANNED_USERS.append(user_id)
        await query.answer("🚫 User Banned!", show_alert=True)
        
    elif query.data.startswith("unban_user#"):
        user_id = int(query.data.split("#")[1])
        await db.remove_banned_user(user_id)
        if user_id in temp.BANNED_USERS: temp.BANNED_USERS.remove(user_id)
        await query.answer("✅ User Unbanned!", show_alert=True)

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

    # 🔥 SMART DELETE LOGIC (INTERACTIVE vs GENERAL)
    elif query.data.startswith("kill_file#"):
        _, target, query_val = query.data.split("#", 2)
        conf = await db.get_config()
        mode = conf.get('delete_mode', 'interactive') 
        
        search_mode = target if target != "all" else "hybrid"
        files, _, total = await get_search_results(query_val, mode=search_mode, max_results=50)
        
        if not files:
            return await query.message.edit(f"<b>❌ No Files Found in {target.upper()} DB!</b>\nQuery: `{query_val}`")

        # MODE 1: INTERACTIVE
        if mode == 'interactive':
            btn = []
            for file in files[:8]: 
                btn.append([InlineKeyboardButton(f"🗑️ {file.file_name[:30]}...", callback_data=f"del_one#{file.file_id}#{target}")])
            
            btn.append([InlineKeyboardButton(f"🔥 DELETE ALL {total} FOUND FILES", callback_data=f"del_all_confirm#{target}#{query_val}")])
            btn.append([InlineKeyboardButton("❌ Cancel", callback_data="close_data")])
            
            await query.message.edit(
                f"<b>🗑️ INTERACTIVE DELETE MODE</b>\n\n<b>🎯 Target:</b> {target.upper()}\n<b>🔍 Found:</b> {total} Files matching `{query_val}`\n\n<i>Click a file to delete ONLY that file.</i>",
                reply_markup=InlineKeyboardMarkup(btn)
            )

        # MODE 2: GENERAL
        else:
            file_list = "\n".join([f"• {f.file_name}" for f in files[:5]])
            if len(files) > 5: file_list += f"\n...and {total-5} more."
            btn = [[InlineKeyboardButton(f"✅ YES, DELETE ALL {total}", callback_data=f"del_all_confirm#{target}#{query_val}")], [InlineKeyboardButton("❌ NO", callback_data="close_data")]]
            await query.message.edit(f"<b>⚠️ CONFIRM DELETION</b>\n\n<b>🎯 Target:</b> {target.upper()}\n<b>🔍 Query:</b> `{query_val}`\n<b>Preview:</b>\n{file_list}", reply_markup=InlineKeyboardMarkup(btn))

    # 🔥 ACTION: DELETE ONE FILE
    elif query.data.startswith("del_one#"):
        _, file_id, target = query.data.split("#")
        await delete_one_file(file_id, target)
        await query.answer("✅ File Deleted!", show_alert=True)
        await query.message.edit(f"<b>✅ File Deleted Successfully!</b>\n\nTarget: {target.upper()}")

    # 🔥 ACTION: DELETE ALL CONFIRM
    elif query.data.startswith("del_all_confirm#"):
        _, target, query_val = query.data.split("#", 2)
        await query.message.edit(f"<b>⏳ Deleting ALL matching files from {target.upper()}...</b>")
        total = await delete_files(query_val, target=target)
        await query.message.edit(f"<b>✅ BULK DELETION COMPLETE!</b>\n\n<b>🗑️ Deleted:</b> {total} Files\n<b>🎯 Target:</b> {target.upper()}")
    
    # 🔥 TOGGLE DELETE MODE
    elif query.data == "toggle_del_mode":
        conf = await db.get_config()
        curr = conf.get('delete_mode', 'interactive')
        new_mode = 'general' if curr == 'interactive' else 'interactive'
        await db.update_config('delete_mode', new_mode)
        await cb_handler(client, type('obj', (object,), {'data': 'admin_bot_settings', 'message': query.message, 'from_user': query.from_user, 'answer': query.answer}))

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
    
    elif query.data.startswith("caption_setgs"):
        ident, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("🛑 Access Denied!", show_alert=True)
        await query.message.edit("<b>📝 Send New Caption:</b>\n\n<i>Variables: {file_name}, {file_size}, {file_caption}</i>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            await save_group_settings(int(grp_id), 'caption', msg.text)
            await query.message.edit("<b>✅ Group Caption Updated!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data.startswith("welcome_setgs"):
        ident, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("🛑 Access Denied!", show_alert=True)
        await query.message.edit("<b>👋 Send New Welcome Message:</b>\n\n<i>Variables: {mention}, {title}</i>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            await save_group_settings(int(grp_id), 'welcome', msg.text)
            await query.message.edit("<b>✅ Welcome Message Updated!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data.startswith("tutorial_setgs"):
        ident, grp_id = query.data.split("#")
        if not await is_check_admin(client, int(grp_id), query.from_user.id): return await query.answer("🛑 Access Denied!", show_alert=True)
        await query.message.edit("<b>📚 Send New Tutorial Link:</b>")
        try:
            msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
            await save_group_settings(int(grp_id), 'tutorial', msg.text)
            await query.message.edit("<b>✅ Tutorial Link Updated!</b>")
        except: await query.message.edit("<b>⏳ Timeout!</b>")

    elif query.data.startswith("bool_setgs"):
        ident, set_type, status, grp_id = query.data.split("#")
        userid = query.from_user.id
        if not await is_check_admin(client, int(grp_id), userid): return await query.answer("🛑 You are not Admin!", show_alert=True)
        await save_group_settings(int(grp_id), set_type, status != "True")
        btn = await get_grp_stg(int(grp_id))
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
    
    elif query.data == "open_group_settings":
        userid = query.from_user.id
        if not await is_check_admin(client, query.message.chat.id, userid): return
        btn = await get_grp_stg(query.message.chat.id)
        await query.message.edit(text=f"Settings for <b>{query.message.chat.title}</b>", reply_markup=InlineKeyboardMarkup(btn))

    # 🔥 STANDARD USER ACTIONS
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
        btn=[[InlineKeyboardButton("🎬 Wᴀᴛᴄʜ Oɴʟɪɴᴇ", url=watch), InlineKeyboardButton("⚡ Fᴀsᴛ Dᴏᴡɴʟᴏᴀᴅ", url=download)],[InlineKeyboardButton('❌ Cʟᴏsᴇ', callback_data='close_data')]]
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

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

    elif query.data == "start":
        buttons = [[InlineKeyboardButton('👨‍🚒 Help', callback_data='help'), InlineKeyboardButton('📊 Sᴛᴀᴛs', callback_data='stats')]]
        try: await query.message.edit_text(script.START_TXT.format(query.from_user.mention, get_wish()), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except MessageNotModified: pass

    elif query.data == "help":
        buttons = [[InlineKeyboardButton('🙋🏻‍♀️ User', callback_data='user_command'), InlineKeyboardButton('🤖 Clone', callback_data='clone_help'), InlineKeyboardButton('🦹 Admin', callback_data='admin_command')],[InlineKeyboardButton('🏄 Back', callback_data='start')]]
        try: await query.message.edit_text(script.HELP_TXT.format(query.from_user.mention), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except MessageNotModified: pass

    elif query.data == "user_command":
        buttons = [[InlineKeyboardButton('🏄 Back', callback_data='help')]]
        await query.message.edit_text(script.USER_COMMAND_TXT, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    
    elif query.data == "clone_help":
        buttons = [[InlineKeyboardButton('🏄 Back', callback_data='help')]]
        await query.message.edit_text(script.CLONE_TXT, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

    elif query.data == "admin_command":
        if query.from_user.id not in ADMINS: return await query.answer("🛑 ADMINS Only!", show_alert=True)
        buttons = [[InlineKeyboardButton('🏄 Back', callback_data='help')]]
        await query.message.edit_text(script.ADMIN_COMMAND_TXT, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)

    elif query.data == "stats":
        if query.from_user.id not in ADMINS: return await query.answer("🛑 ADMINS Only!", show_alert=True)
        pri, bak, tot = await db_count_documents()
        await query.message.edit_text(f"<b>📊 Quick Stats</b>\n\nPri: {pri}\nBak: {bak}\nTot: {tot}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('Back', callback_data='start')]]))

    elif query.data.startswith("checksub"):
        ident, mc = query.data.split("#")
        btn = await is_subscribed(client, query)
        if btn:
            await query.answer(f"🛑 Join Channel First!", show_alert=True)
            btn.append([InlineKeyboardButton("🔁 Try Again", callback_data=f"checksub#{mc}")])
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
            return
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start={mc}")
        await query.message.delete()
    
    elif query.data == "delete_all":
        try: await query.message.edit("<b>🗑️ Deleting...</b>")
        except: pass
        total = await delete_files("") 
        try: await query.message.edit(f"<b>✅ Deleted {total} Files.</b>")
        except: pass

    elif query.data.startswith("delete_"):
        _, query_ = query.data.split("_", 1)
        try: await query.message.edit(f"Deleting {query_}...")
        except: pass
        total = await delete_files(query_)
        try: await query.message.edit(f"<b>✅ Deleted {total} Files.</b>")
        except: pass
