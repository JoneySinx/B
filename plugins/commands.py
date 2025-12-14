import os
import random
import asyncio
import logging
import time
import io
import sys
import qrcode
from datetime import datetime, timedelta

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from hydrogram.errors import MessageNotModified

from Script import script
from database.ia_filterdb import get_file_details, delete_all_filters # 🔥 ADDED delete_all_filters
from database.users_chats_db import db
from info import ADMINS, UPDATES_LINK, PICS, IS_STREAM, UPI_ID, UPI_NAME, RECEIPT_SEND_USERNAME, URL, DELETE_TIME
from utils import (
    is_premium, get_size, is_subscribed, get_verify_status, update_verify_status, 
    get_wish, temp, check_verification, get_verify_short_link, get_readable_time
)

logger = logging.getLogger(__name__)

# ==============================================================================
# 🎮 USER CALLBACK HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(home_cb|help|close_data|my_plan|buy_premium|help_)"))
async def user_cb_handler(client, query):
    data = query.data
    try:
        # 1. Close Button
        if data == "close_data":
            await query.message.delete()
            
        # 2. Home Button
        elif data == "home_cb":
            await start(client, query.message, is_cb=True)

        # 3. Help Menu
        elif data == "help":
            # Admin button only visible if user is admin
            btn = [
                [InlineKeyboardButton('👤 User', callback_data='help_user'), InlineKeyboardButton('🤖 Clone', callback_data='help_clone')],
                [InlineKeyboardButton('🏠 Home', callback_data='home_cb')]
            ]
            if query.from_user.id in ADMINS:
                btn.insert(1, [InlineKeyboardButton('👮 Admin Panel', callback_data='admin_panel')]) # Calls admin_panel.py

            await query.message.edit_text(script.HELP_TXT, reply_markup=InlineKeyboardMarkup(btn))

        elif data == "help_user":
            text = (
                "<b>👤 User Help</b>\n\n"
                "1. <b>Search:</b> Type movie/series name.\n"
                "2. <b>Plan:</b> Check /my_plan status.\n"
                "3. <b>Refer:</b> Use /referral to earn points.\n"
                "4. <b>Gift:</b> Use `/redeem CODE` to activate premium."
            )
            buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

        elif data == "help_clone":
            text = (
                "<b>🤖 Clone Help</b>\n\n"
                "1. Go to @BotFather and create a new bot.\n"
                "2. Get the <b>Bot Token</b>.\n"
                "3. Send: `/clone [Bot Token]` here.\n\n"
                "<i>Your clone will work same as me!</i>"
            )
            buttons = [[InlineKeyboardButton('🔙 Back', callback_data='help')]]
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

        # 4. Premium Section
        elif data == "my_plan":
            await plan(client, query.message, is_cb=True)
            
        elif data == "buy_premium":
            await buy_premium_cb(client, query)

    except MessageNotModified:
        await query.answer("⚠️ Already Updated!")
    except Exception as e:
        logger.error(f"User CB Error: {e}")

# ==============================================================================
# 🚀 START COMMAND (Gateway)
# ==============================================================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message, is_cb=False):
    user = message.chat if is_cb else message.from_user
    
    # 1. BAN CHECK
    if user.id in temp.BANNED_USERS:
        return await message.reply("<b>🚫 You are BANNED!</b>")

    # 2. GROUP CHECK
    if not is_cb and message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id):
            await db.add_chat(message.chat.id, message.chat.title)
        
        # Get Group Welcome Settings
        settings = await db.get_settings(message.chat.id)
        if settings.get('welcome', True):
            btn = [[InlineKeyboardButton('⚡️ Jᴏɪɴ Uᴘᴅᴀᴛᴇs', url=UPDATES_LINK)]]
            await message.reply(f"Hello {user.mention}, Welcome to {message.chat.title}!", reply_markup=InlineKeyboardMarkup(btn))
        return

    # 3. GLOBAL CONFIG CHECKS (Maintenance & Modes)
    conf = await db.get_config()
    
    # Maintenance Mode
    if conf.get('is_maintenance') and user.id not in ADMINS:
        return await message.reply("<b>🚧 BOT UNDER MAINTENANCE 🚧</b>\n\n<i>Developers are working. Please try again later.</i>")

    # Bot Modes (Admin Only / Premium Only)
    if not is_cb:
        mode = conf.get('bot_mode', 'public')
        if mode == 'admin' and user.id not in ADMINS:
            return await message.reply("<b>🔒 Admin Only Mode!</b>\nCurrently, only admins can use this bot.")
        if mode == 'premium' and not await is_premium(user.id, client):
            return await message.reply("<b>💎 Premium Only Mode!</b>\nOnly Premium users can access this bot.\nUse /plan to buy.")

    # 4. REGISTER USER
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)

    # 5. DEEP LINK HANDLING
    if not is_cb and len(message.command) == 2:
        mc = message.command[1]
        
        # A. Verification Logic
        if mc.startswith('verify_'):
            token = mc.split("_")[1]
            stored = await get_verify_status(user.id)
            if stored.get('token') == token:
                await update_verify_status(user.id, is_verified=True, verified_time=time.time())
                await message.reply("<b>🎉 Verification Successful!</b>\nYou can now search files.")
            else:
                await message.reply("<b>❌ Invalid or Expired Token!</b>")
            return
        
        # B. Referral Logic
        if mc.startswith('ref_'):
            try:
                ref_by = int(mc.split("_")[1])
                if ref_by != user.id and not await db.is_user_exist(user.id):
                    points = conf.get('points_per_referral', 10)
                    await db.inc_balance(ref_by, points)
                    await client.send_message(ref_by, f"🎉 <b>New Referral!</b>\nYou earned +{points} points.")
            except: pass

        # C. FILE RETRIEVAL LOGIC
        if mc.startswith('all') or "_" in mc or mc.isdigit():
            # Check Force Subscribe
            if not await is_subscribed(client, message):
                # is_subscribed handles the response, we just return
                return 

            # Verify Ads Check (Controlled by Admin Panel)
            if conf.get('is_verify', False) and not await is_premium(user.id, client):
                if not await check_verification(client, user.id):
                    import string
                    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
                    await update_verify_status(user.id, verify_token=token, is_verified=False)
                    
                    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
                    link = await get_verify_short_link(verify_url)
                    
                    btn = [[InlineKeyboardButton("✅ Verify to Get File", url=link)]]
                    return await message.reply("<b>🔐 Verification Required!</b>\n\nPlease verify yourself to access this file.", reply_markup=InlineKeyboardMarkup(btn))

            # Fetch Files
            files = []
            try:
                if mc.startswith('all'):
                    _, grp, key = mc.split("_", 2)
                    files = temp.FILES.get(key, [])
                elif mc.isdigit():
                    f = await get_file_details(mc)
                    if f: files = [f]
            except: pass
            
            if not files: return await message.reply("<b>❌ File Not Found!</b>\nIt might have been deleted.")
            
            # Send Files
            msg = await message.reply(f"<b>⚡ Sending {len(files)} Files...</b>")
            sent_msgs = []
            
            for file in files:
                btn = [[InlineKeyboardButton('❌ Close', callback_data='close_data')]]
                if IS_STREAM:
                    btn.insert(0, [InlineKeyboardButton("🚀 Stream/DL", callback_data=f"stream#{file['file_id']}")])
                
                # Dynamic Caption from Admin Settings
                custom_cap = conf.get('global_caption')
                if custom_cap:
                    try:
                        cap = custom_cap.format(file_name=file['file_name'], file_size=get_size(file['file_size']), caption=file.get('caption', ''))
                    except:
                        cap = f"<b>📂 {file['file_name']}</b>\n📦 {get_size(file['file_size'])}"
                else:
                    cap = f"<b>📂 {file['file_name']}</b>\n📦 {get_size(file['file_size'])}"
                
                m = await client.send_cached_media(
                    chat_id=user.id, 
                    file_id=file['file_id'], 
                    caption=cap, 
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                sent_msgs.append(m.id)
            
            await msg.delete()
            
            # Auto Delete (If Enabled in Group/Settings) - Using Global default if private
            if DELETE_TIME and DELETE_TIME > 0:
                await asyncio.sleep(DELETE_TIME)
                try: await client.delete_messages(user.id, sent_msgs)
                except: pass
            return

    # 6. NORMAL START MESSAGE
    # Fetch Custom Start Msg/Pic from Admin Panel settings
    txt = conf.get('tpl_start_msg', script.START_TXT)
    try: txt = txt.format(user.mention, get_wish())
    except: pass
    
    pics = conf.get('start_pics', PICS)
    if isinstance(pics, str): pics = [pics]
    if not pics: pics = PICS

    # Support Group Link (Managed in Admin Panel)
    sup_link = conf.get('support_link')

    buttons = [
        [InlineKeyboardButton('👨‍🚒 Hᴇʟᴘ', callback_data='help'), InlineKeyboardButton('🤖 Clone', callback_data='help_clone')], 
        [InlineKeyboardButton('💎 Gᴏ Pʀᴇᴍɪᴜᴍ', callback_data="my_plan")]
    ]
    if sup_link:
        buttons.insert(1, [InlineKeyboardButton('💬 Support Group', url=sup_link)])
        
    # 🔥 Admin Only Button (Triggers admin_panel.py)
    if user.id in ADMINS:
        buttons.insert(0, [InlineKeyboardButton('⚡ GOD MODE PANEL ⚡', callback_data='admin_panel')])

    if is_cb:
        try: await message.edit_text(text=txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except MessageNotModified: pass
    else:
        try: await message.reply_photo(photo=random.choice(pics), caption=txt, reply_markup=InlineKeyboardMarkup(buttons))
        except: await message.reply_text(text=txt, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 💰 PREMIUM, GIFT & REFERRAL
# ==============================================================================
@Client.on_message(filters.command(["plan", "premium"]))
async def plan(client, message, is_cb=False):
    user = message.chat if is_cb else message.from_user
    u = await db.get_user(user.id)
    prem = u.get('status', {}).get('premium', False)
    exp = u.get('status', {}).get('expire', 'Never')
    bal = u.get('balance', 0)
    
    # Format Expiry
    if isinstance(exp, datetime):
        exp = exp.strftime("%d-%m-%Y")

    txt = (
        f"<b>💎 PREMIUM STATUS</b>\n\n"
        f"<b>👤 User:</b> {user.first_name}\n"
        f"<b>📊 Status:</b> {'✅ Premium' if prem else '❌ Free'}\n"
        f"<b>⏳ Expires:</b> {exp}\n"
        f"<b>💰 Points:</b> {bal}\n\n"
        f"<i>💡 Got a Gift Code? Use /redeem CODE</i>"
    )
    btn = [[InlineKeyboardButton("💰 Buy Premium", callback_data="buy_premium")]]
    if is_cb:
        btn.append([InlineKeyboardButton("🔙 Back", callback_data="start")])
        try: await message.edit_text(txt, reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified: pass
    else:
        await message.reply(txt, reply_markup=InlineKeyboardMarkup(btn))

# 🔥 GIFT REDEEM COMMAND
@Client.on_message(filters.command("redeem"))
async def redeem_code(client, message):
    if len(message.command) < 2: return await message.reply("<b>⚠️ Usage:</b> `/redeem YOUR-CODE`")
    code = message.command[1]
    
    # Check Code in DB
    data = await db.get_code(code)
    if not data:
        return await message.reply("<b>❌ Invalid or Expired Code!</b>")
    
    # Calculate New Expiry
    duration = data['duration']
    u = await db.get_user(message.from_user.id)
    curr_exp = u.get('status', {}).get('expire')
    
    # If already premium, add time. Else start from now.
    if curr_exp and isinstance(curr_exp, datetime) and curr_exp > datetime.now():
        expiry = curr_exp + timedelta(seconds=duration)
    else:
        expiry = datetime.now() + timedelta(seconds=duration)

    await db.update_plan(message.from_user.id, {'premium': True, 'expire': expiry})
    await db.delete_code(code)
    
    await message.reply(f"<b>🎉 Congratulations! Gift Redeemed.</b>\n\n<b>⏳ Added:</b> {get_readable_time(duration)}\n<b>📅 Expires:</b> {expiry.strftime('%d-%m-%Y')}")

async def buy_premium_cb(client, query):
    if not UPI_ID: return await query.answer("Payment Not Configured by Admin!", show_alert=True)
    upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&cu=INR"
    qr = qrcode.make(upi_url)
    bio = io.BytesIO(); qr.save(bio); bio.seek(0)
    await query.message.reply_photo(photo=bio, caption="<b>💸 Scan QR to Pay</b>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Send Screenshot", url=f"https://t.me/{RECEIPT_SEND_USERNAME}")]]))

@Client.on_message(filters.command("referral"))
async def referral(client, message):
    conf = await db.get_config()
    pts = conf.get('points_per_referral', 10)
    link = f"https://t.me/{temp.U_NAME}?start=ref_{message.from_user.id}"
    await message.reply(f"<b>🎁 Referral Program</b>\n\nInvite friends & earn {pts} points!\n\n<b>🔗 Your Link:</b>\n{link}")

# ==============================================================================
# 🤖 UTILS (Clone, Link, Help)
# ==============================================================================
@Client.on_message(filters.command("clone"))
async def clone_bot(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/clone [BOT_TOKEN]`")
    token = message.command[1]
    try:
        test = Client("test", api_id=client.api_id, api_hash=client.api_hash, bot_token=token, in_memory=True)
        await test.start(); b = await test.get_me(); await test.stop()
        await db.add_clone(message.from_user.id, token, b.id, b.first_name)
        await message.reply(f"<b>✅ Clone Created Successfully!</b>\n\nUser: @{b.username}")
    except Exception as e: await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command('help') & filters.incoming)
async def help_cmd(client, message):
    await message.reply(script.HELP_TXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🏠 Home', callback_data='home_cb')]]))

@Client.on_message(filters.command("link"))
async def link_cmd(client, message):
    msg = message.reply_to_message
    if not msg: return await message.reply("Reply to a file.")
    link = f"{URL}watch/{msg.id}"
    await message.reply(f"<b>🔗 Direct Link:</b>\n{link}")

# ==============================================================================
# 🔥 ADMIN COMMANDS: /delete_all (God Mode Tool)
# ==============================================================================
@Client.on_message(filters.command("delete_all") & filters.private & filters.user(ADMINS))
async def delete_all_filters_cmd(client, message):
    await message.reply(
        "<b>⚠️ WARNING: Are you sure you want to delete ALL filters from the database? This action is irreversible!</b>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 YES, Delete Everything", callback_data="purge_confirm_all_cmd")],
            [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
        ]),
        parse_mode=enums.ParseMode.HTML
    )

@Client.on_callback_query(filters.regex(r"^purge_confirm_all_cmd"))
async def purge_confirm_all_cmd_cb(client, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("🛑 Access Denied!", show_alert=True)
    
    await query.message.edit_text("<b>🗑️ Deleting all filters... Please wait.</b>", parse_mode=enums.ParseMode.HTML)
    
    try:
        # Calls the function from database/ia_filterdb.py
        count = await delete_all_filters()
        
        await query.message.edit_text(f"<b>✅ ALL Filters Deleted Successfully!</b>\n\n🗑️ Total {count} items removed.", parse_mode=enums.ParseMode.HTML)
        
        await asyncio.sleep(5)
        try: await query.message.delete()
        except: pass
        
    except Exception as e:
        logger.error(f"Error deleting all filters: {e}")
        await query.message.edit_text(f"<b>❌ Error during deletion:</b> <code>{e}</code>", parse_mode=enums.ParseMode.HTML)
