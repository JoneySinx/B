import os
import time
import logging
import random
import string
import sys
import asyncio
from datetime import datetime

try: import psutil
except: psutil = None

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from hydrogram.errors import MessageNotModified
from database.ia_filterdb import db_count_documents
from database.users_chats_db import db
from info import ADMINS, INDEX_CHANNELS
from utils import get_size, get_readable_time, temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 👮 ADMIN CALLBACK HANDLER (ROUTE MANAGER)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(admin_|toggle_|bc_|set_|gen_)"))
async def admin_cb_handler(client, query):
    if query.from_user.id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
    data = query.data
    try:
        # --- MENUS ---
        if data == "admin_panel": await main_menu(query)
        elif data == "admin_bot_settings": await settings_menu(query)
        elif data == "admin_file_settings": await file_settings_menu(query)
        elif data == "admin_monetization": await monetization_menu(query)
        elif data == "admin_content": await content_menu(query)
        elif data == "admin_broadcast": await broadcast_menu(query)
        elif data == "admin_database": await database_menu(query)
        elif data == "admin_gift": await gift_menu(query)

        # --- TOGGLES & ACTIONS ---
        elif data.startswith("toggle_"): await handle_toggles(client, query)
        elif data.startswith("gen_"): await handle_gift_gen(query)
        elif data == "restart_bot": await handle_restart(query)
        elif data == "get_logs": await handle_logs(client, query)
        
    except MessageNotModified: await query.answer("⚠️ Already Updated!")
    except Exception as e: logger.error(f"Admin Panel Error: {e}")

# ==============================================================================
# 📟 DASHBOARD MENUS
# ==============================================================================

# 1. MAIN HOME
async def main_menu(query):
    text = f"<b>⚡ <u>GOD MODE DASHBOARD</u></b>\n\n<b>👋 Master:</b> {query.from_user.mention}"
    buttons = [
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_bot_settings"), InlineKeyboardButton("📂 File & IMDB", callback_data="admin_file_settings")],
        [InlineKeyboardButton("🎁 Gift Codes", callback_data="admin_gift"), InlineKeyboardButton("💰 Money", callback_data="admin_monetization")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("📝 Content", callback_data="admin_content")],
        [InlineKeyboardButton("🗄️ Database & Stats", callback_data="admin_database"), InlineKeyboardButton("🔄 Restart", callback_data="restart_bot")],
        [InlineKeyboardButton("🔙 Home", callback_data="home_cb")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 2. SYSTEM SETTINGS
async def settings_menu(query):
    conf = await db.get_config()
    maint = "🔴 ON" if conf.get('is_maintenance') else "🟢 OFF"
    verify = "🟢 ON" if conf.get('is_verify') else "🔴 OFF"
    pm_search = "🟢 ON" if conf.get('pm_search', True) else "🔴 OFF"
    mode = conf.get('bot_mode', 'public').upper()
    search_src = conf.get('search_mode', 'hybrid').upper()
    
    text = f"<b>⚙️ <u>SYSTEM SETTINGS</u></b>\n\n<b>🛡️ Maintenance:</b> {maint}\n<b>🔐 Verify Ads:</b> {verify}\n<b>🔍 PM Search:</b> {pm_search}\n<b>🤖 Bot Mode:</b> {mode}\n<b>📂 Search Source:</b> {search_src}"
    
    buttons = [
        [InlineKeyboardButton(f"Maint: {maint}", callback_data="toggle_maint"), InlineKeyboardButton(f"Verify: {verify}", callback_data="toggle_verify")],
        [InlineKeyboardButton(f"PM Search: {pm_search}", callback_data="toggle_pm_search"), InlineKeyboardButton(f"Mode: {mode} 🔄", callback_data="toggle_bot_mode")],
        [InlineKeyboardButton(f"Source: {search_src} 🔄", callback_data="toggle_search_mode"), InlineKeyboardButton("📄 Get Logs", callback_data="get_logs")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 3. FILE & IMDB SETTINGS
async def file_settings_menu(query):
    conf = await db.get_config()
    
    imdb = "🟢 ON" if conf.get('imdb_intg', True) else "🔴 OFF"
    link_mode = "🔗 Link" if conf.get('link_mode') else "🔘 Button"
    spell = "🟢 ON" if conf.get('spell_check', True) else "🔴 OFF"
    
    tpl_status = "✅ Custom" if conf.get('global_template') else "❌ Default"
    cap_status = "✅ Custom" if conf.get('global_caption') else "❌ Default"
    
    text = f"<b>📂 <u>FILE & IMDB SETTINGS</u></b>\n\n<b>🎬 IMDB:</b> {imdb}\n<b>🔤 Spell Check:</b> {spell}\n<b>📑 Result Mode:</b> {link_mode}\n\n<b>📝 Template:</b> {tpl_status}\n<b>📝 Caption:</b> {cap_status}"
    
    buttons = [
        [InlineKeyboardButton(f"IMDB: {imdb}", callback_data="toggle_imdb"), InlineKeyboardButton(f"Result: {link_mode}", callback_data="toggle_link_mode")],
        [InlineKeyboardButton(f"Spell Check: {spell}", callback_data="toggle_spellcheck")],
        [InlineKeyboardButton("✏️ Edit Template", switch_inline_query_current_chat="/set_template "), InlineKeyboardButton("🔄 Reset Tpl", callback_data="toggle_reset_template")],
        [InlineKeyboardButton("✏️ Edit Caption", switch_inline_query_current_chat="/set_caption "), InlineKeyboardButton("🔄 Reset Cap", callback_data="toggle_reset_caption")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 4. GIFT MENU
async def gift_menu(query):
    text = "<b>🎁 <u>GIFT CODE GENERATOR</u></b>\n\nGenerate Premium codes for users."
    buttons = [
        [InlineKeyboardButton("Ticket (1 Hr)", callback_data="gen_3600"), InlineKeyboardButton("Ticket (1 Day)", callback_data="gen_86400")],
        [InlineKeyboardButton("Promo (1 Week)", callback_data="gen_604800"), InlineKeyboardButton("Promo (1 Month)", callback_data="gen_2592000")],
        [InlineKeyboardButton("🎲 Custom Time", switch_inline_query_current_chat="/gen_code 20d")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 5. CONTENT MANAGER (Start Msg/Pic)
async def content_menu(query):
    conf = await db.get_config()
    msg = "✅ Set" if conf.get('tpl_start_msg') else "❌ Default"
    pic = "✅ Set" if conf.get('start_pics') else "❌ Default"
    
    text = f"<b>📝 <u>START CONTENT</u></b>\n\n<b>🔸 Start Msg:</b> {msg}\n<b>🔸 Start Pic:</b> {pic}"
    buttons = [
        [InlineKeyboardButton("✏️ Set Msg", switch_inline_query_current_chat="/set_start_msg "), InlineKeyboardButton("✏️ Set Pic", switch_inline_query_current_chat="/set_start_pic ")],
        [InlineKeyboardButton("🔄 Reset Msg", callback_data="toggle_reset_msg"), InlineKeyboardButton("🔄 Reset Pic", callback_data="toggle_reset_pics")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 6. MONETIZATION
async def monetization_menu(query):
    conf = await db.get_config()
    status = "🟢 ON" if conf.get('shortlink_enable') else "🔴 OFF"
    site = conf.get('shortlink_site', 'Not Set')
    
    text = f"<b>💰 <u>MONETIZATION</u></b>\n\n<b>🔸 Status:</b> {status}\n<b>🔸 Site:</b> `{site}`"
    buttons = [
        [InlineKeyboardButton(f"Enable: {status}", callback_data="toggle_shortener")],
        [InlineKeyboardButton("✏️ Set Site", switch_inline_query_current_chat="/set_short_site "), InlineKeyboardButton("✏️ Set API", switch_inline_query_current_chat="/set_short_api ")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 7. DATABASE
async def database_menu(query):
    pri, bak, total = await db_count_documents()
    users = await db.total_users_count()
    cpu = psutil.cpu_percent() if psutil else 0
    ram = psutil.virtual_memory().percent if psutil else 0
    uptime = get_readable_time(time.time() - temp.START_TIME)
    
    text = f"<b>📊 <u>SERVER STATUS</u></b>\n<b>🤖 Uptime:</b> {uptime}\n<b>🖥️ CPU:</b> {cpu}% | <b>RAM:</b> {ram}%\n\n<b>🗄️ <u>DB STATS</u></b>\n<b>📂 Files:</b> {total}\n<b>👤 Users:</b> {users}"
    buttons = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_database"), InlineKeyboardButton("🗑️ Delete File", switch_inline_query_current_chat="/delete name")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🕹️ TOGGLE LOGIC
# ==============================================================================
async def handle_toggles(client, query):
    data = query.data
    conf = await db.get_config()
    key = data.split("_", 1)[1]
    
    mapping = {
        'imdb': ('imdb_intg', True), 'link_mode': ('link_mode', False), 
        'spellcheck': ('spell_check', True), 'maint': ('is_maintenance', False), 
        'verify': ('is_verify', False), 'pm_search': ('pm_search', True),
        'shortener': ('shortlink_enable', False)
    }
    
    if key in mapping:
        db_key, default = mapping[key]
        await db.update_config(db_key, not conf.get(db_key, default))
        
        if key in ['imdb', 'link_mode', 'spellcheck']: await file_settings_menu(query)
        elif key in ['shortener']: await monetization_menu(query)
        else: await settings_menu(query)
        return

    # Mode Toggles (3-way)
    elif key == "bot_mode":
        modes = ['public', 'admin', 'premium']
        curr = conf.get('bot_mode', 'public')
        await db.update_config('bot_mode', modes[(modes.index(curr)+1)%3])
        await settings_menu(query)
    elif key == "search_mode":
        modes = ['hybrid', 'primary', 'backup']
        curr = conf.get('search_mode', 'hybrid')
        await db.update_config('search_mode', modes[(modes.index(curr)+1)%3])
        await settings_menu(query)

    # Reset Actions
    elif key == "reset_template": await db.update_config('global_template', None); await file_settings_menu(query)
    elif key == "reset_caption": await db.update_config('global_caption', None); await file_settings_menu(query)
    elif key == "reset_msg": await db.update_config('tpl_start_msg', None); await content_menu(query)
    elif key == "reset_pics": await db.update_config('start_pics', None); await content_menu(query)

# 🔥 LOGS & RESTART
async def handle_restart(query):
    await query.message.edit_text("<b>🔄 Restarting Bot...</b>\n<i>Please wait 10-20 seconds.</i>")
    # Save restart status for completion log
    await db.update_config('restart_status', {'chat_id': query.message.chat.id, 'msg_id': query.message.id})
    os.execl(sys.executable, sys.executable, *sys.argv)

async def handle_logs(client, query):
    if os.path.exists("log.txt"):
        await client.send_document(chat_id=query.from_user.id, document="log.txt", caption="📄 <b>System Logs</b>")
        await query.answer("Logs Sent!", show_alert=True)
    else: await query.answer("No Logs Found!", show_alert=True)

# 🔥 GIFT GENERATION LOGIC
async def handle_gift_gen(query):
    sec = int(query.data.split("_")[1])
    code = f"PREM-{ ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)) }"
    await db.create_code(code, sec)
    
    dur = get_readable_time(sec)
    txt = f"<b>🎁 Generated Gift Code</b>\n\n<code>{code}</code>\n\n<b>Duration:</b> {dur}\n<i>User can use /redeem {code}</i>"
    await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_gift")]]))

# ==============================================================================
# 🛠️ SETTER COMMANDS (Add to end of file)
# ==============================================================================
@Client.on_message(filters.command("set_caption") & filters.user(ADMINS))
async def set_cap(c, m): await db.update_config('global_caption', m.text.split(" ", 1)[1]); await m.reply("✅ Caption Set")

@Client.on_message(filters.command("set_template") & filters.user(ADMINS))
async def set_tpl(c, m): await db.update_config('global_template', m.text.split(" ", 1)[1]); await m.reply("✅ Template Set")

@Client.on_message(filters.command("set_short_api") & filters.user(ADMINS))
async def set_api(c, m): await db.update_config('shortlink_api', m.text.split(" ", 1)[1]); await m.reply("✅ API Set")

@Client.on_message(filters.command("set_short_site") & filters.user(ADMINS))
async def set_site(c, m): await db.update_config('shortlink_site', m.text.split(" ", 1)[1]); await m.reply("✅ Site Set")

@Client.on_message(filters.command("set_start_msg") & filters.user(ADMINS))
async def set_msg(c, m): await db.update_config('tpl_start_msg', m.text.split(" ", 1)[1]); await m.reply("✅ Msg Set")

@Client.on_message(filters.command("set_start_pic") & filters.user(ADMINS))
async def set_pic(c, m): await db.update_config('start_pics', m.text.split(" ", 1)[1]); await m.reply("✅ Pic Set")

@Client.on_message(filters.command("gen_code") & filters.user(ADMINS))
async def gen_code_custom(c, m):
    try:
        raw = m.command[1].lower()
        if raw.endswith('d'): sec = int(raw[:-1]) * 86400
        elif raw.endswith('h'): sec = int(raw[:-1]) * 3600
        elif raw.endswith('m'): sec = int(raw[:-1]) * 60
        else: sec = int(raw)
        
        code = f"PREM-{ ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)) }"
        await db.create_code(code, sec)
        await m.reply(f"🎁 <b>Code:</b> `{code}`\n<b>Time:</b> {get_readable_time(sec)}")
    except: await m.reply("Usage: `/gen_code 10d` (10 Days)")
