import os
import random
import asyncio
import logging
import time
import io
import sys
import qrcode
from datetime import datetime, timedelta

# Try importing psutil
try:
    import psutil
except ImportError:
    psutil = None

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, CallbackQuery, Message
from hydrogram.errors import MessageTooLong, ChatAdminRequired, FloodWait, MessageNotModified

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

# --- HELPER: GROUP SETTINGS BUTTONS ---
async def get_grp_stg(group_id):
    settings = await get_settings(group_id)
    btn = [[
        InlineKeyboardButton('📝 Caption', callback_data=f'caption_setgs#{group_id}'),
        InlineKeyboardButton('👋 Welcome', callback_data=f'welcome_setgs#{group_id}')
    ],[
        InlineKeyboardButton(f'Spell Check {"✅" if settings["spell_check"] else "❌"}', callback_data=f'bool_setgs#spell_check#{settings["spell_check"]}#{group_id}'),
        InlineKeyboardButton(f'Auto Delete {"✅" if settings["auto_delete"] else "❌"}', callback_data=f'bool_setgs#auto_delete#{settings["auto_delete"]}#{group_id}')
    ]]
    return btn

# ==============================================================================
# 🎮 UNIVERSAL CALLBACK HANDLER (USER SIDE)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(home_cb|help|close_data|my_plan|buy_premium|help_)"))
async def user_cb_handler(client, query):
    data = query.data
    try:
        # --- COMMON BUTTONS ---
        if data == "close_data":
            await query.message.delete()
            
        elif data == "home_cb":
            await start(client, query.message, is_cb=True)

        elif data == "help":
            text = script.HELP_TXT
            buttons = [
                [InlineKeyboardButton('👤 User', callback_data='help_user'), InlineKeyboardButton('🤖 Clone', callback_data='help_clone')],
                [InlineKeyboardButton('👮 Admin', callback_data='help_admin')], # Logic in admin_panel.py
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
            
        # "help_admin" is handled in admin_panel.py via regex

        elif data == "my_plan":
            await plan(client, query.message, is_cb=True)
            
        elif data == "buy_premium":
            await buy_premium_cb(client, query)

    except MessageNotModified:
        await query.answer("⚠️ Already on this page!")
        pass
    except Exception as e:
        logger.error(f"CB Error: {e}")
        pass

# ==============================================================================
# 🚀 START COMMAND (WITH FILE RETRIEVAL)
# ==============================================================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message, is_cb=False):
    user = message.chat if is_cb else message.from_user
    chat_id = message.chat.id
    
    # 1. BAN CHECK
    if user.id in temp.BANNED_USERS:
        return await message.reply("<b>🚫 You are BANNED!</b>")

    # 2. GROUP CHECK
    if not is_cb and message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(chat_id): await db.add_chat(chat_id, message.chat.title)
        btn = [[InlineKeyboardButton('⚡️ Jᴏɪɴ Uᴘᴅᴀᴛᴇs', url=UPDATES_LINK)]]
        await message.reply(f"Hello {user.mention}, Welcome to {message.chat.title}", reply_markup=InlineKeyboardMarkup(btn))
        return 

    # 3. MAINTENANCE CHECK
    conf = await db.get_config()
    if conf.get('is_maintenance') and user.id not in ADMINS:
        reason = conf.get('maintenance_reason', "Updating Server...")
        if is_cb: await message.answer("🚧 Maintenance Mode ON!", show_alert=True)
        else: await message.reply(f"<b>🚧 BOT UNDER MAINTENANCE 🚧</b>\n\n<i>Reason: {reason}</i>")
        return

    # 4. USER DB
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)

    # --- DEEP LINK HANDLING ---
    if not is_cb and len(message.command) == 2:
        mc = message.command[1]
        
        # A. Verification Logic
        if mc.startswith('verify_'):
            token = mc.split("_")[1]
            stored = await get_verify_status(user.id)
            if stored.get('token') == token:
                await update_verify_status(user.id, is_verified=True, verified_time=time.time())
                await message.reply("<b>🎉 Verification Successful!</b>")
            else: await message.reply("<b>❌ Invalid Token!</b>")
            return
            
        # B. Referral Logic
        if mc.startswith('ref_'):
            try:
                ref_by = int(mc.split("_")[1])
                if ref_by != user.id and not await db.is_user_exist(user.id):
                    await db.inc_balance(ref_by, 10)
                    await client.send_message(ref_by, f"🎉 New Referral! +10 Points.")
            except: pass
        
        # C. Group Settings Logic
        if mc.startswith('settings_'):
             try:
                _, group_id = mc.split("_")
                if not await is_check_admin(client, int(group_id), user.id):
                    return await message.reply("❌ Admins Only!")
                btn = await get_grp_stg(int(group_id))
                return await message.reply(f"<b>⚙️ Settings for:</b> <code>{group_id}</code>", reply_markup=InlineKeyboardMarkup(btn))
             except: pass

        # D. FILE RETRIEVAL LOGIC (🔥 FIXED)
        if mc.startswith('all') or "_" in mc or mc.isdigit():
            # 1. Force Sub Check
            btn = await is_subscribed(client, message)
            if btn:
                btn.append([InlineKeyboardButton("🔁 Try Again", callback_data=f"checksub#{mc}")])
                return await message.reply(f"<b>👋 Hello {user.mention},</b>\n\n<i>Please Join My Channel to use me!</i>", reply_markup=InlineKeyboardMarkup(btn))
            
            # 2. Verification Check
            if conf.get('is_verify', False) and not await is_premium(user.id, client):
                is_verified = await check_verification(client, user.id)
                if not is_verified:
                    import string
                    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                    await update_verify_status(user.id, verify_token=token, is_verified=False)
                    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
                    short_link = await get_verify_short_link(verify_url)
                    btn = [[InlineKeyboardButton("✅ Verify to Get File", url=short_link)]]
                    return await message.reply(f"<b>🔐 Access Denied!</b>\n\n<i>Verify yourself to access this file.</i>", reply_markup=InlineKeyboardMarkup(btn))

            # 3. Fetch Files
            files = []
            if mc.startswith('all'):
                try:
                    _, grp_id, key = mc.split("_", 2)
                    files = temp.FILES.get(key, [])
                    if not files: return await message.reply('<b>⚠️ Session Expired! Search Again.</b>')
                except: pass
            elif "_" in mc: # single file like 4282_9282 (legacy) or just ID
                 try:
                    files = [] # Placeholder for complex logic
                 except: pass
            else: # Single File ID
                 try:
                     file = await get_file_details(mc)
                     if file: files = [file]
                 except: pass
            
            if not files: return await message.reply("<b>❌ File Not Found!</b>")

            # 4. Send Files & Auto Delete
            msg = await message.reply(f"<b>⚡ Sending {len(files)} Files...</b>")
            sent_msgs = []
            
            for file in files:
                btn = [[InlineKeyboardButton('❌ Close', callback_data='close_data')]]
                if IS_STREAM:
                    btn.insert(0, [InlineKeyboardButton("🚀 Stream/DL", callback_data=f"stream#{file['file_id']}")])
                
                caption = f"<b>📂 {file['file_name']}</b>\n📦 {get_size(file['file_size'])}"
                m = await client.send_cached_media(
                    chat_id=user.id, 
                    file_id=file['file_id'], 
                    caption=caption, 
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                sent_msgs.append(m.id)
            
            await msg.delete()
            
            # 5. Auto Delete Logic
            if DELETE_TIME and DELETE_TIME > 0:
                await asyncio.sleep(DELETE_TIME)
                try:
                    await client.delete_messages(user.id, sent_msgs)
                except: pass
            return

    # --- NORMAL START MSG ---
    txt = conf.get('tpl_start_msg', script.START_TXT)
    try: txt = txt.format(user.mention, get_wish())
    except: pass
    
    pics = conf.get('start_pics', PICS)
    if isinstance(pics, str): pics = [pics]
    if not pics: pics = PICS
    
    buttons = [
        [InlineKeyboardButton('👨‍🚒 Hᴇʟᴘ', callback_data='help'), InlineKeyboardButton('🤖 Clone', callback_data='help_clone')], 
        [InlineKeyboardButton('💎 Gᴏ Pʀᴇᴍɪᴜᴍ', callback_data="my_plan")]
    ]
    if user.id in ADMINS:
        buttons.insert(0, [InlineKeyboardButton('⚡ GOD MODE PANEL ⚡', callback_data='admin_panel')])

    if is_cb:
        try:
            await message.edit_text(text=txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except MessageNotModified: pass
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
        f"<b>📂 Files:</b> {total_files}\n"
        f"<b>👤 Users:</b> {users} | <b>💎 Prem:</b> {prm}\n"
        f"<b>💾 Size:</b> {get_size(used_db)}"
    )
    return text

# ==============================================================================
# 💰 PLAN / PREMIUM
# ==============================================================================
@Client.on_message(filters.command(["plan", "premium"]))
async def plan(client, message, is_cb=False):
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
        try:
            await message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified: pass
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
        [InlineKeyboardButton('👮 Admin', callback_data='help_admin')], # Logic in admin_panel.py
        [InlineKeyboardButton('🏠 Home', callback_data='home_cb')]
    ]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command('about') & filters.incoming)
async def about_cmd(client, message):
    await message.reply(script.ABOUT_TXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔙 Back', callback_data='home_cb')]]))

# ==============================================================================
# 🛠️ ADMIN UTILS (COMMANDS)
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
