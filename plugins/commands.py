import os
import random
import asyncio
import logging
import time
import io
import sys
import qrcode
from datetime import datetime, timedelta

# Try importing psutil for stats, else dummy
try:
    import psutil
except ImportError:
    psutil = None

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, CallbackQuery, Message
from hydrogram.errors import MessageTooLong, ChatAdminRequired, FloodWait

from Script import script
from database.ia_filterdb import db_count_documents, delete_files, get_file_details
from database.users_chats_db import db
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, URL, BIN_CHANNEL, 
    STICKERS, INDEX_CHANNELS, ADMINS, DELETE_TIME, 
    UPDATES_LINK, LOG_CHANNEL, PICS, IS_STREAM, REACTIONS, PM_FILE_DELETE_TIME,
    UPI_ID, UPI_NAME
)
from utils import (
    is_premium, upload_image, get_settings, get_size, is_subscribed, 
    is_check_admin, get_verify_status, update_verify_status, 
    get_readable_time, get_wish, temp, save_group_settings, check_verification, get_verify_short_link
)

logger = logging.getLogger(__name__)

# ==============================================================================
# 🎮 UNIVERSAL CALLBACK HANDLER (BRAIN OF THE BOT)
# ==============================================================================

@Client.on_callback_query()
async def cb_handler(client, query):
    data = query.data
    user_id = query.from_user.id
    
    # --- COMMON BUTTONS ---
    if data == "close_data":
        await query.message.delete()
        
    elif data == "home_cb":
        await start(client, query.message, is_cb=True)

    elif data == "help":
        text = script.HELP_TXT
        buttons = [
            [InlineKeyboardButton('👤 User', callback_data='help_user'), InlineKeyboardButton('🤖 Clone', callback_data='help_clone')],
            [InlineKeyboardButton('👮 Admin', callback_data='help_admin')],
            [InlineKeyboardButton('🏠 Home', callback_data='home_cb')]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "help_user":
        text = "<b>👤 User Help</b>\n\n1. <b>Search:</b> Type movie name.\n2. <b>Plan:</b> Check /my_plan.\n3. <b>Refer:</b> Use /referral to earn points."
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "help_clone":
        text = "<b>🤖 Clone Help</b>\n\n1. Go to @BotFather\n2. Create new bot & get Token.\n3. Use /clone [Token] here."
        buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    elif data == "help_admin":
        if user_id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
        await admin_panel_menu(query)

    # --- ADMIN PANEL SUB-MENUS ---
    elif data.startswith("admin_"):
        if user_id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
        await handle_admin_logic(client, query)

    # --- TOGGLES (MAINTENANCE / VERIFY) ---
    elif data == "toggle_maint":
        if user_id not in ADMINS: return
        conf = await db.get_config()
        await db.update_config('is_maintenance', not conf.get('is_maintenance'))
        await handle_admin_logic(client, query, refresh="admin_bot_settings") 
        
    elif data == "toggle_verify":
        if user_id not in ADMINS: return
        conf = await db.get_config()
        await db.update_config('is_verify', not conf.get('is_verify'))
        await handle_admin_logic(client, query, refresh="admin_bot_settings")

    # --- STATS REFRESH ---
    elif data == "stats_refresh":
        if user_id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
        text = await get_stats_text()
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="help")]]))

    # --- DELETE ACTION ---
    elif data.startswith("kill_file"):
        if user_id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
        _, target, keyword = data.split("#", 2)
        await query.answer("🗑️ Deleting...", show_alert=False)
        deleted = await delete_files(keyword, target)
        await query.message.edit_text(f"<b>✅ Deleted {deleted} Files from {target.upper()} DB!</b>")

    # --- INDEX ACTION ---
    elif data.startswith("index_start"):
        if user_id not in ADMINS: return await query.answer("❌ Admins Only!", show_alert=True)
        _, target, chat_id = data.split("#", 2)
        await query.message.edit_text(f"<b>🚀 Indexing Started on {target.upper()} DB!</b>\n\n<i>Check logs for progress.</i>")
        
    # --- CHECK SUB ---
    elif data.startswith("checksub"):
        if await is_subscribed(client, query.message):
            await query.answer("❌ You are NOT subscribed yet!", show_alert=True)
        else:
            await query.answer("✅ Subscribed!", show_alert=True)
            await start(client, query.message, is_cb=True)
            
    # --- PREMIUM ---
    elif data == "my_plan":
        await plan(client, query.message, is_cb=True)
        
    elif data == "buy_premium":
        await buy_premium_cb(client, query)

# ==============================================================================
# 👮 ADMIN LOGIC HANDLER
# ==============================================================================
async def handle_admin_logic(client, query, refresh=None):
    data = refresh if refresh else query.data
    conf = await db.get_config()
    
    if data == "admin_db_menu":
        pri, bak, tot = await db_count_documents()
        used, free = await db.get_db_size()
        txt = (
            f"<b>🗄️ DATABASE MANAGER</b>\n\n"
            f"<b>Primary Docs:</b> {pri}\n"
            f"<b>Backup Docs:</b> {bak}\n"
            f"<b>Total Docs:</b> {tot}\n"
            f"<b>Size:</b> {get_size(used)}"
        )
        btn = [[InlineKeyboardButton("🔙 Back", callback_data="help_admin")]]
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(btn))
        
    elif data == "admin_bot_settings":
        maint = conf.get('is_maintenance')
        verify = conf.get('is_verify')
        
        txt = f"<b>🛡️ BOT SETTINGS</b>\n\n<b>Maintenance:</b> {maint}\n<b>Verify Ads:</b> {verify}"
        btn = [
            [InlineKeyboardButton(f"Maintenance {'✅' if maint else '❌'}", callback_data="toggle_maint")],
            [InlineKeyboardButton(f"Verify Ads {'✅' if verify else '❌'}", callback_data="toggle_verify")],
            [InlineKeyboardButton("🔙 Back", callback_data="help_admin")]
        ]
        try: await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(btn))
        except: pass # Avoid error if message is not modified
        
    elif data == "admin_payment_menu":
        upi = UPI_ID if UPI_ID else "Not Set"
        active = conf.get('is_premium_active', True)
        txt = f"<b>💰 PAYMENT SETTINGS</b>\n\n<b>UPI ID:</b> <code>{upi}</code>\n<b>Premium Module:</b> {active}"
        btn = [[InlineKeyboardButton("🔙 Back", callback_data="help_admin")]]
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(btn))
        
    elif data == "admin_channel_menu":
        await query.answer("Use /index to manage channels.", show_alert=True)
        
    elif data == "admin_broadcast_menu":
        await query.answer("Use /broadcast command.", show_alert=True)
        
    elif data == "admin_clone_menu":
        await query.answer("Use /clone command.", show_alert=True)
        
    elif data == "admin_verify_menu":
         await query.answer("Manage in Bot Settings.", show_alert=True)
         
    else:
        await admin_panel_menu(query)

async def admin_panel_menu(query):
    conf = await db.get_config()
    maint = "🔴" if conf.get('is_maintenance') else "🟢"
    verify = "🟢" if conf.get('is_verify') else "🔴"
    
    text = (
        f"<b>⚙️ <u>GOD MODE CONTROL PANEL</u></b>\n\n"
        f"<b>🛡️ Maintenance:</b> {maint}\n"
        f"<b>🔐 Verify System:</b> {verify}\n"
        f"<i>Select a module to manage:</i>"
    )
    buttons = [
        [InlineKeyboardButton("🗄️ Database", callback_data="admin_db_menu"), InlineKeyboardButton("🤖 Bot Settings", callback_data="admin_bot_settings")],
        [InlineKeyboardButton("💰 Payments", callback_data="admin_payment_menu"), InlineKeyboardButton("🔐 Verify Ads", callback_data="admin_verify_menu")],
        [InlineKeyboardButton("🔙 Back", callback_data="help")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🚀 START COMMAND
# ==============================================================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message, is_cb=False):
    user = message.chat if is_cb else message.from_user
    chat_id = message.chat.id
    
    if user.id in temp.BANNED_USERS:
        return await message.reply("<b>🚫 You are BANNED!</b>")

    if not is_cb and message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(chat_id): await db.add_chat(chat_id, message.chat.title)
        btn = [[InlineKeyboardButton('⚡️ Jᴏɪɴ Uᴘᴅᴀᴛᴇs', url=UPDATES_LINK)]]
        await message.reply(f"Hello {user.mention}, Welcome to {message.chat.title}", reply_markup=InlineKeyboardMarkup(btn))
        return 

    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)

    # Command Handling (Only for messages)
    if not is_cb and len(message.command) == 2:
        mc = message.command[1]
        
        if mc.startswith('verify_'):
            token = mc.split("_")[1]
            stored = await get_verify_status(user.id)
            if stored.get('token') == token:
                await update_verify_status(user.id, is_verified=True, verified_time=time.time())
                await message.reply("<b>🎉 Verification Successful!</b>")
            else: await message.reply("<b>❌ Invalid Token!</b>")
            return
            
        if mc.startswith('ref_'):
            try:
                ref_by = int(mc.split("_")[1])
                if ref_by != user.id and not await db.is_user_exist(user.id):
                    await db.inc_balance(ref_by, 10) # 10 Points
                    await client.send_message(ref_by, f"🎉 New Referral! +10 Points.")
            except: pass

    # Normal Start
    conf = await db.get_config()
    txt = conf.get('tpl_start_msg', script.START_TXT)
    try: txt = txt.format(user.mention, get_wish())
    except: pass
    
    pics = conf.get('start_pics', PICS)
    if isinstance(pics, str): pics = [pics]
    if not pics: pics = PICS
    
    buttons = [
        [InlineKeyboardButton('👨‍🚒 Hᴇʟᴘ', callback_data='help'), InlineKeyboardButton('📊 Sᴛᴀᴛs', callback_data='stats_refresh')], 
        [InlineKeyboardButton('💎 Gᴏ Pʀᴇᴍɪᴜᴍ', callback_data="my_plan")]
    ]
    
    if is_cb:
        await message.edit_text(text=txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    else:
        try: await message.reply_photo(photo=random.choice(pics), caption=txt, reply_markup=InlineKeyboardMarkup(buttons))
        except: await message.reply_text(text=txt, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 📊 STATS COMMAND
# ==============================================================================
@Client.on_message(filters.command(["stats", "status"]) & filters.user(ADMINS))
async def stats(bot, message):
    msg = await message.reply("<b>🔄 Fetching Statistics...</b>")
    text = await get_stats_text()
    await msg.edit(text)

async def get_stats_text():
    pri, bak, total_files = await db_count_documents()
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    prm = await db.get_premium_count()
    used_db, free_db = await db.get_db_size()
    
    cpu = psutil.cpu_percent() if psutil else 0
    ram = psutil.virtual_memory().percent if psutil else 0
    uptime = get_readable_time(time.time() - temp.START_TIME)
    
    text = (
        f"<b>📊 SYSTEM STATISTICS</b>\n\n"
        f"<b>🤖 Uptime:</b> {uptime}\n"
        f"<b>🖥️ CPU:</b> {cpu}% | <b>RAM:</b> {ram}%\n"
        f"<b>🗄️ DATABASE</b>\n"
        f"<b>📂 Files:</b> {total_files} (Pri: {pri})\n"
        f"<b>👤 Users:</b> {users}\n"
        f"<b>💎 Premium:</b> {prm}\n"
        f"<b>💾 Size:</b> {get_size(used_db)}"
    )
    return text

# ==============================================================================
# 💰 PLAN / PREMIUM
# ==============================================================================
@Client.on_message(filters.command(["plan", "premium"]))
async def plan(client, message, is_cb=False):
    # If called from button, use edit logic
    user = message.chat if is_cb else message.from_user
    user_id = user.id
    
    db_user = await db.get_user(user_id)
    status = db_user.get('status', {}) if db_user else {}
    is_prem = status.get('premium', False)
    expiry = status.get('expire', 'Never')
    balance = await db.get_balance(user_id)
    
    text = (
        f"<b>💎 PREMIUM STATUS</b>\n\n"
        f"<b>👤 User:</b> {user.first_name}\n"
        f"<b>📊 Status:</b> {'✅ Premium' if is_prem else '❌ Free'}\n"
        f"<b>⏳ Expires:</b> {expiry}\n"
        f"<b>💰 Points:</b> {balance}\n\n"
        f"<i>Earn points via /referral to get Free Premium!</i>"
    )
    btn = [[InlineKeyboardButton("💰 Buy Premium", callback_data="buy_premium")]]
    if is_cb:
        btn.append([InlineKeyboardButton("🔙 Back", callback_data="start")])
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await message.reply(text, reply_markup=InlineKeyboardMarkup(btn))

async def buy_premium_cb(client, query):
    if UPI_ID:
        upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&cu=INR"
        qr = qrcode.make(upi_url)
        bio = io.BytesIO()
        qr.save(bio)
        bio.seek(0)
        caption = "<b>💸 Scan to Pay</b>\n\n1 Month: ₹30\n1 Year: ₹200\n\nSend Screenshot to Admin."
        btn = [[InlineKeyboardButton("📤 Send Screenshot", url=f"https://t.me/{RECEIPT_SEND_USERNAME}")]]
        
        await query.message.reply_photo(photo=bio, caption=caption, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await query.answer("Payment Not Set!", show_alert=True)

# ==============================================================================
# 📝 HELP & ABOUT
# ==============================================================================
@Client.on_message(filters.command('help') & filters.incoming)
async def help_cmd(client, message):
    text = script.HELP_TXT
    buttons = [
        [InlineKeyboardButton('👤 User', callback_data='help_user'), InlineKeyboardButton('🤖 Clone', callback_data='help_clone')],
        [InlineKeyboardButton('👮 Admin', callback_data='help_admin')],
        [InlineKeyboardButton('🏠 Home', callback_data='home_cb')]
    ]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command('about') & filters.incoming)
async def about_cmd(client, message):
    await message.reply(script.ABOUT_TXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='home_cb')]]))

# ==============================================================================
# 🛠️ ADMIN UTILS
# ==============================================================================
@Client.on_message(filters.command("ban") & filters.user(ADMINS))
async def ban_cmd(bot, message):
    try:
        user_id = int(message.command[1])
        await db.add_banned_user(user_id)
        temp.BANNED_USERS.append(user_id)
        await message.reply(f"🚫 Banned: {user_id}")
    except: await message.reply("Use: /ban ID")

@Client.on_message(filters.command("unban") & filters.user(ADMINS))
async def unban_cmd(bot, message):
    try:
        user_id = int(message.command[1])
        await db.remove_banned_user(user_id)
        if user_id in temp.BANNED_USERS: temp.BANNED_USERS.remove(user_id)
        await message.reply(f"✅ Unbanned: {user_id}")
    except: await message.reply("Use: /unban ID")

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_cmd(bot, message):
    if not message.reply_to_message:
        return await message.reply("Reply to a message!")
    from plugins.broadcast import broadcast_handler
    await broadcast_handler(bot, message)

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete_file_cmd(bot, message):
    try: query = message.text.split(" ", 1)[1]
    except: return await message.reply_text("<b>⚠️ Usage:</b> `/delete [File Name]`")
    btn = [
        [InlineKeyboardButton("🗑️ Primary Only", callback_data=f"kill_file#primary#{query}"), InlineKeyboardButton("🗑️ Backup Only", callback_data=f"kill_file#backup#{query}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
    ]
    await message.reply_text(f"<b>🗑️ DELETE MANAGER</b>\nQuery: `{query}`", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command("clone"))
async def clone_bot(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/clone [BOT_TOKEN]`")
    token = message.command[1]
    try:
        # Mock test
        test_client = Client("test_bot", api_id=client.api_id, api_hash=client.api_hash, bot_token=token, in_memory=True)
        await test_client.start()
        bot_info = await test_client.get_me()
        await test_client.stop()
        
        await db.add_clone(message.from_user.id, token, bot_info.id, bot_info.first_name)
        await message.reply(f"<b>✅ Clone Created:</b> @{bot_info.username}")
    except Exception as e: await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("referral"))
async def referral_cmd(client, message):
    link = f"https://t.me/{temp.U_NAME}?start=ref_{message.from_user.id}"
    await message.reply(f"<b>🔗 Your Referral Link:</b>\n{link}\n\n<i>Share to earn points!</i>")

@Client.on_message(filters.command("link"))
async def link_cmd(client, message):
    msg = message.reply_to_message
    if not msg: return await message.reply("Reply to a file.")
    link = f"{URL}watch/{msg.id}"
    await message.reply(f"🔗 Link: {link}")
