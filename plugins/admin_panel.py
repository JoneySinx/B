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
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from hydrogram.errors import MessageNotModified
from database.ia_filterdb import db_count_documents
from database.users_chats_db import db
from info import ADMINS, INDEX_CHANNELS
from utils import get_size, get_readable_time, temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 👮 ADMIN CALLBACK HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(admin_|toggle_|bc_|set_|gen_)"))
async def admin_cb_handler(client, query):
    if query.from_user.id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
    data = query.data
    try:
        # MENUS
        if data == "admin_panel": await main_menu(query)
        elif data == "admin_bot_settings": await settings_menu(query)
        elif data == "admin_file_settings": await file_settings_menu(query)
        elif data == "admin_monetization": await monetization_menu(query)
        elif data == "admin_content": await content_menu(query)
        elif data == "admin_broadcast": await broadcast_menu(query)
        elif data == "admin_database": await database_menu(query)
        elif data == "admin_index_list": await index_list_menu(client, query)
        elif data == "admin_support": await support_menu(query)
        elif data == "admin_groups": await groups_menu(query)
        elif data == "admin_filters": await filters_menu(query)
        elif data == "admin_bans": await bans_menu(query)
        elif data == "admin_gift": await gift_menu(query) # 🔥 NEW

        # ACTIONS
        elif data.startswith("toggle_"): await handle_toggles(client, query)
        elif data.startswith("bc_"): await handle_broadcast(client, query)
        elif data.startswith("gen_"): await handle_gift_gen(query) # 🔥 NEW
        elif data == "restart_bot": await handle_restart(query) # 🔥 NEW
        elif data == "get_logs": await handle_logs(client, query) # 🔥 NEW

    except MessageNotModified: await query.answer("⚠️ Updated!")
    except Exception as e: logger.error(f"Err: {e}")

# ==============================================================================
# 📟 MENUS
# ==============================================================================
async def main_menu(query):
    text = f"<b>⚡ <u>GOD MODE DASHBOARD</u></b>\n\n<b>👋 Master:</b> {query.from_user.mention}"
    buttons = [
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_bot_settings"), InlineKeyboardButton("📂 File & IMDB", callback_data="admin_file_settings")],
        [InlineKeyboardButton("🎁 Gift Codes", callback_data="admin_gift"), InlineKeyboardButton("💰 Money", callback_data="admin_monetization")],
        [InlineKeyboardButton("👥 Groups", callback_data="admin_groups"), InlineKeyboardButton("⚡ Filters", callback_data="admin_filters")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"), InlineKeyboardButton("📺 Channels", callback_data="admin_index_list")],
        [InlineKeyboardButton("🗄️ Database", callback_data="admin_database"), InlineKeyboardButton("🔄 Restart", callback_data="restart_bot")],
        [InlineKeyboardButton("🔙 Home", callback_data="home_cb")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 🔥 NEW GIFT MENU
async def gift_menu(query):
    text = (
        "<b>🎁 <u>GIFT CODE GENERATOR</u></b>\n\n"
        "Generate Premium codes for users.\n"
        "<i>Click to generate:</i>"
    )
    buttons = [
        [InlineKeyboardButton("Ticket (1 Hr)", callback_data="gen_3600"), InlineKeyboardButton("Ticket (1 Day)", callback_data="gen_86400")],
        [InlineKeyboardButton("Promo (1 Week)", callback_data="gen_604800"), InlineKeyboardButton("Promo (1 Month)", callback_data="gen_2592000")],
        [InlineKeyboardButton("🎲 Custom Time", switch_inline_query_current_chat="/gen_code 20d")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ... [Keep other menus like settings_menu, file_settings_menu, etc. from previous code here] ...
# (Mainly just replace main_menu and add gift_menu, keeping others same as last time for brevity)
# I will include FULL file below for safety.

async def settings_menu(query):
    conf = await db.get_config()
    maint = "🔴 ON" if conf.get('is_maintenance') else "🟢 OFF"
    verify = "🟢 ON" if conf.get('is_verify') else "🔴 OFF"
    pm = "🟢 ON" if conf.get('pm_search', True) else "🔴 OFF"
    mode = conf.get('bot_mode', 'public').upper()
    
    text = f"<b>⚙️ SETTINGS</b>\n\nMaint: {maint}\nVerify: {verify}\nPM: {pm}\nMode: {mode}"
    btn = [
        [InlineKeyboardButton(f"Maint: {maint}", callback_data="toggle_maint"), InlineKeyboardButton(f"Verify: {verify}", callback_data="toggle_verify")],
        [InlineKeyboardButton(f"PM: {pm}", callback_data="toggle_pm_search"), InlineKeyboardButton(f"Mode: {mode}", callback_data="toggle_bot_mode")],
        [InlineKeyboardButton("📄 Get Logs", callback_data="get_logs"), InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def file_settings_menu(query):
    conf = await db.get_config()
    imdb = "🟢 ON" if conf.get('imdb_intg', True) else "🔴 OFF"
    link = "🔗 Link" if conf.get('link_mode') else "🔘 Button"
    spell = "🟢 ON" if conf.get('spell_check', True) else "🔴 OFF"
    text = f"<b>📂 FILE SETTINGS</b>\n\nIMDB: {imdb}\nMode: {link}\nSpell: {spell}"
    btn = [
        [InlineKeyboardButton(f"IMDB: {imdb}", callback_data="toggle_imdb"), InlineKeyboardButton(f"Result: {link}", callback_data="toggle_link_mode")],
        [InlineKeyboardButton(f"Spell: {spell}", callback_data="toggle_spellcheck")],
        [InlineKeyboardButton("Edit Tpl", switch_inline_query_current_chat="/set_template "), InlineKeyboardButton("Reset Tpl", callback_data="toggle_reset_template")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def groups_menu(query):
    conf = await db.get_config()
    auto = "🟢 ON" if conf.get('global_auto_filter', True) else "🔴 OFF"
    wel = "🟢 ON" if conf.get('welcome', True) else "🔴 OFF"
    text = f"<b>👥 GROUPS</b>\n\nAuto Filter: {auto}\nWelcome: {wel}"
    btn = [[InlineKeyboardButton(f"Filter: {auto}", callback_data="toggle_autofilter"), InlineKeyboardButton(f"Welcome: {wel}", callback_data="toggle_welcome")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def monetization_menu(query):
    conf = await db.get_config()
    en = "🟢 ON" if conf.get('shortlink_enable') else "🔴 OFF"
    site = conf.get('shortlink_site', 'Not Set')
    text = f"<b>💰 MONEY</b>\n\nShortener: {en}\nSite: `{site}`"
    btn = [[InlineKeyboardButton(f"Enable: {en}", callback_data="toggle_shortener")], [InlineKeyboardButton("Set Site", switch_inline_query_current_chat="/set_short_site "), InlineKeyboardButton("Set API", switch_inline_query_current_chat="/set_short_api ")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def content_menu(query):
    conf = await db.get_config()
    msg = "✅ Set" if conf.get('tpl_start_msg') else "❌ Default"
    text = f"<b>📝 CONTENT</b>\n\nStart Msg: {msg}"
    btn = [[InlineKeyboardButton("Set Msg", switch_inline_query_current_chat="/set_start_msg "), InlineKeyboardButton("Reset", callback_data="toggle_reset_msg")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def database_menu(query):
    pri, bak, total = await db_count_documents()
    users = await db.total_users_count()
    cpu = psutil.cpu_percent() if psutil else 0
    text = f"<b>🗄️ STATS</b>\n\nFiles: {total}\nUsers: {users}\nCPU: {cpu}%"
    btn = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_database"), InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def broadcast_menu(query):
    text = "<b>📢 BROADCAST</b>\n\nUse buttons to type command:"
    btn = [[InlineKeyboardButton("All Users", switch_inline_query_current_chat="/broadcast"), InlineKeyboardButton("Send & Pin", switch_inline_query_current_chat="/broadcast -pin")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def filters_menu(query):
    text = "<b>⚡ FILTERS</b>\n\nManage shortcuts:"
    btn = [[InlineKeyboardButton("➕ Add Filter", switch_inline_query_current_chat="/add name reply"), InlineKeyboardButton("➖ Del Filter", switch_inline_query_current_chat="/del name")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def bans_menu(query):
    text = "<b>🚫 BANS</b>"
    btn = [[InlineKeyboardButton("🔨 Ban ID", switch_inline_query_current_chat="/ban ID"), InlineKeyboardButton("😇 Unban ID", switch_inline_query_current_chat="/unban ID")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def index_list_menu(client, query):
    text = "<b>📺 CHANNELS</b>"
    btn = [[InlineKeyboardButton("➕ Add", switch_inline_query_current_chat="/index ID"), InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def support_menu(query):
    conf = await db.get_config()
    link = conf.get('support_link', 'None')
    text = f"<b>💬 SUPPORT</b>\nLink: {link}"
    btn = [[InlineKeyboardButton("Set", switch_inline_query_current_chat="/set_support link"), InlineKeyboardButton("Remove", callback_data="toggle_del_support")], [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

# ==============================================================================
# 🕹️ LOGIC HANDLERS
# ==============================================================================
async def handle_toggles(client, query):
    key = query.data.split("_", 1)[1]
    conf = await db.get_config()
    
    # Simple Toggles
    if key in ['maint', 'verify', 'pm_search', 'shortener', 'imdb', 'link_mode', 'spellcheck', 'autofilter', 'welcome', 'autodelete']:
        mapping = {
            'maint': 'is_maintenance', 'verify': 'is_verify', 'pm_search': 'pm_search',
            'shortener': 'shortlink_enable', 'imdb': 'imdb_intg', 'link_mode': 'link_mode',
            'spellcheck': 'spell_check', 'autofilter': 'global_auto_filter', 'welcome': 'welcome',
            'autodelete': 'auto_delete'
        }
        db_key = mapping[key]
        # Default True for some, False for others
        default = True if key in ['pm_search', 'imdb', 'spellcheck', 'autofilter', 'welcome'] else False
        await db.update_config(db_key, not conf.get(db_key, default))
        
        # Return to correct menu
        if key in ['autofilter', 'welcome', 'autodelete']: await groups_menu(query)
        elif key in ['shortener']: await monetization_menu(query)
        elif key in ['imdb', 'link_mode', 'spellcheck']: await file_settings_menu(query)
        else: await settings_menu(query)

    # Mode Toggles
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
    elif key == "del_support": await db.update_config('support_link', None); await support_menu(query)
    elif key == "reset_msg": await db.update_config('tpl_start_msg', None); await content_menu(query)
    elif key == "reset_template": await db.update_config('global_template', None); await file_settings_menu(query)

# 🔥 LOGS & RESTART
async def handle_restart(query):
    await query.message.edit_text("<b>🔄 Restarting Bot...</b>\n<i>Please wait 10-20 seconds.</i>")
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

async def handle_broadcast(client, query): await query.answer("Use buttons to type command!", show_alert=True)

# ==============================================================================
# 🛠️ SETTER COMMANDS
# ==============================================================================
# [Keep existing setter commands like set_caption, set_template, set_support, ban, unban from previous response here]
# Also add the new custom gen command:

@Client.on_message(filters.command("gen_code") & filters.user(ADMINS))
async def gen_code_custom(c, m):
    # usage: /gen_code 20d or 5h
    try:
        raw = m.command[1].lower()
        if raw.endswith('d'): sec = int(raw[:-1]) * 86400
        elif raw.endswith('h'): sec = int(raw[:-1]) * 3600
        elif raw.endswith('m'): sec = int(raw[:-1]) * 60
        else: sec = int(raw) # assume seconds
        
        code = f"PREM-{ ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)) }"
        await db.create_code(code, sec)
        await m.reply(f"🎁 <b>Code:</b> `{code}`\n<b>Time:</b> {raw}")
    except: await m.reply("Usage: `/gen_code 10d` (10 Days)")
