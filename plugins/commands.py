import os
import random
import asyncio
import logging
import time
import io
import qrcode
from datetime import datetime, timedelta

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, Message
from hydrogram.errors import MessageTooLong, ChatAdminRequired, FloodWait

from Script import script
from database.ia_filterdb import db_count_documents, delete_files, get_file_details
from database.users_chats_db import db
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, URL, BIN_CHANNEL, 
    STICKERS, INDEX_CHANNELS, ADMINS, DELETE_TIME, 
    UPDATES_LINK, LOG_CHANNEL, PICS, IS_STREAM, REACTIONS, PM_FILE_DELETE_TIME,
    UPI_ID, UPI_NAME, PAYMENT_QR
)
from utils import (
    is_premium, upload_image, get_settings, get_size, is_subscribed, 
    is_check_admin, get_verify_status, update_verify_status, 
    get_readable_time, get_wish, temp, save_group_settings, check_verification, get_verify_short_link
)

logger = logging.getLogger(__name__)

# --- HELPER FUNCTIONS ---
async def get_grp_stg(group_id):
    settings = await get_settings(group_id)
    btn = [[
        InlineKeyboardButton('📝 File Caption', callback_data=f'caption_setgs#{group_id}'),
        InlineKeyboardButton('👋 Welcome Msg', callback_data=f'welcome_setgs#{group_id}')
    ],[
        InlineKeyboardButton('📚 Tutorial Link', callback_data=f'tutorial_setgs#{group_id}')
    ],[
        InlineKeyboardButton(f'Spell Check {"✅" if settings["spell_check"] else "❌"}', callback_data=f'bool_setgs#spell_check#{settings["spell_check"]}#{group_id}'),
        InlineKeyboardButton(f'Welcome {"✅" if settings["welcome"] else "❌"}', callback_data=f'bool_setgs#welcome#{settings["welcome"]}#{group_id}')
    ],[
        InlineKeyboardButton(f"🗑️ Auto Delete: {get_readable_time(DELETE_TIME)}" if settings["auto_delete"] else "Auto Delete: ❌", callback_data=f'bool_setgs#auto_delete#{settings["auto_delete"]}#{group_id}')
    ],[
        InlineKeyboardButton(f"Mode: {'Link 🔗' if settings['links'] else 'Button 🔘'}", callback_data=f'bool_setgs#links#{settings["links"]}#{group_id}')
    ]]
    return btn

# ==============================================================================
# 🚀 START COMMAND (THE GATEWAY)
# ==============================================================================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    # 1. BAN CHECK (First Line of Defense)
    if message.from_user.id in temp.BANNED_USERS:
        return await message.reply("<b>🚫 You are BANNED from using this bot!</b>")

    # 2. GROUP HANDLING
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            username = f'@{message.chat.username}' if message.chat.username else 'Private'
            await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))       
            await db.add_chat(message.chat.id, message.chat.title)
        
        # MOOD SYSTEM: Global Welcome
        conf = await db.get_config()
        wel_text = conf.get('welcome_text', script.WELCOME_TEXT)
        try:
            txt = wel_text.format(mention=message.from_user.mention, title=message.chat.title)
        except: txt = f"Hello {message.from_user.mention}, Welcome to {message.chat.title}"
        
        btn = [[InlineKeyboardButton('⚡️ Jᴏɪɴ Uᴘᴅᴀᴛᴇs', url=UPDATES_LINK)]]
        await message.reply(text=txt, reply_markup=InlineKeyboardMarkup(btn))
        return 

    if not message.from_user: return

    # 3. MAINTENANCE CHECK
    conf = await db.get_config()
    if conf.get('is_maintenance') and message.from_user.id not in ADMINS:
        reason = conf.get('maintenance_reason', "Updating Server...")
        return await message.reply(f"<b>🚧 BOT UNDER MAINTENANCE 🚧</b>\n\n<i>Reason: {reason}</i>")

    # 4. USER REGISTRATION
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.NEW_USER_TXT.format(message.from_user.mention, message.from_user.id))

    # 🔥 5. VERIFY TOKEN HANDLER (Process Verification)
    if len(message.command) == 2 and message.command[1].startswith("verify_"):
        token = message.command[1].split("_")[1]
        stored = await get_verify_status(message.from_user.id)
        
        if stored.get('token') == token:
            # Full Verify
            await update_verify_status(message.from_user.id, is_verified=True, verified_time=time.time())
            await message.reply(f"<b>🎉 Verification Successful!</b>\n\n<i>You can now search files freely.</i>\n<i>Valid for: {int(conf.get('verify_duration', 86400)/3600)} Hours</i>")
            return
        else:
            return await message.reply("<b>❌ Invalid or Expired Token!</b>\nPlease generate a new link.")

    # 6. NORMAL START MESSAGE
    if (len(message.command) != 2) or (len(message.command) == 2 and message.command[1] == 'start'):
        # MOOD SYSTEM: Start Msg & Pic
        start_msg = conf.get('tpl_start_msg', script.START_TXT)
        try: txt = start_msg.format(message.from_user.mention, get_wish())
        except: txt = start_msg
        
        pics = conf.get('start_pics', PICS)
        if isinstance(pics, str): pics = [pics]
        if not pics: pics = PICS # Fallback
        
        buttons = [
            [InlineKeyboardButton('👨‍🚒 Hᴇʟᴘ', callback_data='help'), InlineKeyboardButton('📊 Sᴛᴀᴛs', callback_data='stats')], 
            [InlineKeyboardButton('💎 Gᴏ Pʀᴇᴍɪᴜᴍ', callback_data="my_plan")]
        ]
        
        try:
            await message.reply_photo(photo=random.choice(pics), caption=txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        except Exception:
            await message.reply_text(text=txt, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True)
        return

    mc = message.command[1]
    
    # 🔥 HANDLE MISSING COMMANDS
    if mc == 'premium': return await plan(client, message)
    if mc.startswith('ref_'): return await process_referral(client, message)
    
    # 7. SETTINGS SHORTCUT
    if mc.startswith('settings'):
        _, group_id = message.command[1].split("_")
        if not await is_check_admin(client, int(group_id), message.from_user.id): return await message.reply("<b>❌ Access Denied! Admins Only.</b>")
        btn = await get_grp_stg(int(group_id))
        return await message.reply(f"<b>⚙️ Settings for:</b> <code>{group_id}</code>", reply_markup=InlineKeyboardMarkup(btn))

    # 8. FORCE SUB CHECK
    btn = await is_subscribed(client, message)
    if btn:
        btn.append([InlineKeyboardButton("🔁 Try Again", callback_data=f"checksub#{mc}")])
        try:
            await message.reply_photo(photo=random.choice(PICS), caption=f"<b>👋 Hello {message.from_user.mention},</b>\n\n<i>Please Join My Channel to use me!</i>", reply_markup=InlineKeyboardMarkup(btn))
        except:
            await message.reply_text(f"<b>👋 Hello {message.from_user.mention},</b>\n\n<i>Please Join My Channel to use me!</i>", reply_markup=InlineKeyboardMarkup(btn))
        return 
    
    # 🔥 9. VERIFICATION CHECK (CRITICAL FIX FOR FILE LINKS)
    if conf.get('is_verify', False) and not await is_premium(message.from_user.id, client):
        is_verified = await check_verification(client, message.from_user.id)
        if not is_verified:
            # Redirect to Verification
            import string
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            await update_verify_status(message.from_user.id, verify_token=token, is_verified=False)
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{token}"
            short_link = await get_verify_short_link(verify_url)
            
            btn = [[InlineKeyboardButton("✅ Verify to Get File", url=short_link)]]
            return await message.reply(
                f"<b>🔐 Access Denied!</b>\n\n<i>You must verify yourself to access this file.</i>",
                reply_markup=InlineKeyboardMarkup(btn)
            )

    # 10. FILE RETRIEVAL (ALL FILES)
    if mc.startswith('all'):
        try: _, grp_id, key = mc.split("_", 2)
        except ValueError: return await message.reply("❌ Invalid Link")
        
        files = temp.FILES.get(key)
        if not files: return await message.reply('<b>⚠️ Session Expired! Search Again.</b>')
        
        settings = await get_settings(int(grp_id))
        total_files = await message.reply(f"<b>⚡ Processing {len(files)} Files...</b>")
        
        file_ids = [total_files.id]
        
        GLOBAL_CAP = conf.get('global_caption')

        for file in files:
            if settings['caption']: CAPTION = settings['caption']
            elif GLOBAL_CAP: CAPTION = GLOBAL_CAP
            else: CAPTION = "{file_name}"
            
            f_caption = CAPTION.format(file_name=file['file_name'], file_size=get_size(file['file_size']), file_caption=file['caption'])      
            btn = [[InlineKeyboardButton('❌ Close', callback_data='close_data')]]
            if IS_STREAM:
                btn.insert(0, [InlineKeyboardButton("🚀 Fast Download / Watch", callback_data=f"stream#{file['_id']}")])

            msg = await client.send_cached_media(chat_id=message.from_user.id, file_id=file['_id'], caption=f_caption, protect_content=conf.get('is_protect_content', False), reply_markup=InlineKeyboardMarkup(btn))
            file_ids.append(msg.id)

        del_time = conf.get('delete_time', DELETE_TIME)
        if settings['auto_delete']:
            msg = await message.reply(f"<b>⚠️ Files will be deleted in {get_readable_time(del_time)}!</b>")
            file_ids.append(msg.id)
            await asyncio.sleep(del_time)
            for i in range(0, len(file_ids), 100):
                try: await client.delete_messages(chat_id=message.chat.id, message_ids=file_ids[i:i+100])
                except: pass
        return

    # 11. SINGLE FILE
    try: type_, grp_id, file_id = mc.split("_", 2)
    except ValueError: return await message.reply("❌ Invalid Link")
    
    files_ = await get_file_details(file_id)
    if not files_: return await message.reply('<b>⚠️ File Not Found!</b>')
    
    settings = await get_settings(int(grp_id))
    
    if settings['caption']: CAPTION = settings['caption']
    elif conf.get('global_caption'): CAPTION = conf.get('global_caption')
    else: CAPTION = "{file_name}"
    
    f_caption = CAPTION.format(file_name=files_['file_name'], file_size=get_size(files_['file_size']), file_caption=files_['caption'])
    
    btn = [[InlineKeyboardButton('❌ Close', callback_data='close_data')]]
    if IS_STREAM:
        btn.insert(0, [InlineKeyboardButton("🚀 Fast Download / Watch", callback_data=f"stream#{file_id}")])
    
    vp = await client.send_cached_media(chat_id=message.from_user.id, file_id=file_id, caption=f_caption, protect_content=conf.get('is_protect_content', False), reply_markup=InlineKeyboardMarkup(btn))
    
    if settings['auto_delete']:
        del_time = conf.get('delete_time', DELETE_TIME)
        await asyncio.sleep(del_time)
        try: await vp.delete()
        except: pass

# ==============================================================================
# 🎛️ GOD MODE ADMIN PANEL
# ==============================================================================
@Client.on_message(filters.command(["admin", "settings", "panel"]) & filters.user(ADMINS))
async def admin_panel(client, message):
    conf = await db.get_config()
    maint = "🔴" if conf.get('is_maintenance') else "🟢"
    verify = "🟢" if conf.get('is_verify') else "🔴"
    
    text = (
        f"<b>⚙️ <u>GOD MODE CONTROL PANEL</u></b>\n\n"
        f"<b>🛡️ Maintenance:</b> {maint}\n"
        f"<b>🔐 Verify System:</b> {verify}\n"
        f"<i>My Lord, what is your command?</i>"
    )
    
    buttons = [
        [InlineKeyboardButton("🗄️ Database", callback_data="admin_db_menu"), InlineKeyboardButton("📺 Channels", callback_data="admin_channel_menu")],
        [InlineKeyboardButton("💰 Payments", callback_data="admin_payment_menu"), InlineKeyboardButton("🔐 Verify Ads", callback_data="admin_verify_menu")],
        [InlineKeyboardButton("🎭 Templates", callback_data="admin_template_menu"), InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton("🛡️ Bot Settings", callback_data="admin_bot_settings"), InlineKeyboardButton("🤖 Clone Manager", callback_data="admin_clone_menu")],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🛠️ DIRECT ADMIN UTILITY COMMANDS
# ==============================================================================

@Client.on_message(filters.command("ban") & filters.user(ADMINS))
async def ban_user_cmd(bot, message):
    try:
        user_id = int(message.command[1])
        await db.add_banned_user(user_id)
        temp.BANNED_USERS.append(user_id)
        await message.reply(f"<b>🚫 User {user_id} Banned!</b>")
    except: await message.reply("Usage: `/ban [User ID]`")

@Client.on_message(filters.command("unban") & filters.user(ADMINS))
async def unban_user_cmd(bot, message):
    try:
        user_id = int(message.command[1])
        await db.remove_banned_user(user_id)
        if user_id in temp.BANNED_USERS: temp.BANNED_USERS.remove(user_id)
        await message.reply(f"<b>✅ User {user_id} Unbanned!</b>")
    except: await message.reply("Usage: `/unban [User ID]`")

@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def total_users_cmd(bot, message):
    count = await db.total_users_count()
    await message.reply(f"<b>👥 Total Users:</b> {count}")

@Client.on_message(filters.command("leave") & filters.user(ADMINS))
async def leave_group_cmd(bot, message):
    if len(message.command) != 2: return await message.reply("Usage: `/leave [Chat ID]`")
    try:
        chat_id = int(message.command[1])
        await bot.leave_chat(chat_id)
        await message.reply(f"<b>✅ Left Chat:</b> {chat_id}")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_cmd(bot, message):
    if not message.reply_to_message:
        return await message.reply("<b>⚠️ Reply to a message to broadcast!</b>")
    
    await message.reply("<b>🚀 Broadcasting...</b>")
    from plugins.broadcast import broadcast_handler 
    # Use the detailed handler from plugins/broadcast.py, triggering command logic manually if needed
    # Or simplified logic:
    await broadcast_handler(bot, message)

# ==============================================================================
# 🗑️ SMART DELETE
# ==============================================================================
@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete_file_cmd(bot, message):
    try: 
        query = message.text.split(" ", 1)[1]
    except: 
        return await message.reply_text("<b>⚠️ Usage:</b> `/delete [File Name]`")
        
    btn = [
        [
            InlineKeyboardButton("🗑️ Primary Only", callback_data=f"kill_file#primary#{query}"),
            InlineKeyboardButton("🗑️ Backup Only", callback_data=f"kill_file#backup#{query}")
        ],
        [InlineKeyboardButton("🔥 DESTROY BOTH (ALL)", callback_data=f"kill_file#all#{query}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
    ]
    
    await message.reply_text(
        f"<b>🗑️ DELETE MANAGER</b>\n\n"
        f"<b>Query:</b> `{query}`\n"
        f"<i>Select target database to delete from:</i>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )

# ==============================================================================
# 📂 INDEXING
# ==============================================================================
@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_handler(client, message):
    if len(message.command) != 2: return await message.reply("<b>❌ Usage:</b> `/index [Channel ID]`")
    try:
        channel_id = int(message.command[1])
        chat = await client.get_chat(channel_id)
    except Exception as e: return await message.reply(f"<b>❌ Error:</b> `{e}`")

    text = f"<b>📂 INDEXING MANAGER</b>\n\n<b>📢 Channel:</b> {chat.title}\n<i>Where to save files?</i>"
    buttons = [
        [InlineKeyboardButton("📂 Primary DB", callback_data=f"index_start#primary#{channel_id}"), InlineKeyboardButton("🗄️ Backup DB", callback_data=f"index_start#backup#{channel_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
    ]
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🕵️ GOD COMMANDS
# ==============================================================================
@Client.on_message(filters.command("info") & filters.user(ADMINS))
async def user_info(bot, message):
    if len(message.command) != 2: return await message.reply("Use: `/info [User ID]`")
    try:
        user_id = int(message.command[1])
        user = await bot.get_users(user_id)
        db_u = await db.is_user_exist(user_id)
        prem = await is_premium(user_id, bot)
        verify = await get_verify_status(user_id)
        
        txt = (
            f"<b>🕵️ USER INTELLIGENCE</b>\n\n"
            f"<b>Name:</b> {user.mention}\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>In DB:</b> {db_u}\n"
            f"<b>Premium:</b> {prem}\n"
            f"<b>Verified:</b> {verify['is_verified']}"
        )
        await message.reply(txt)
    except Exception as e: await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("dm") & filters.user(ADMINS))
async def god_speak(bot, message):
    if len(message.command) < 3: return await message.reply("Use: `/dm [User ID] [Message]`")
    try:
        user_id = int(message.command[1])
        msg = message.text.split(None, 2)[2]
        await bot.send_message(user_id, f"<b>🔔 Message from Admin:</b>\n\n{msg}")
        await message.reply("✅ Message Sent!")
    except Exception as e: await message.reply(f"❌ Failed: {e}")

@Client.on_message(filters.command("purge") & filters.user(ADMINS))
async def purge_zombies(bot, message):
    msg = await message.reply("<b>🧟 Checking for Zombies (Deleted Accounts)...</b>")
    users = await db.get_all_users()
    deleted = 0
    async for user in users:
        try:
            await bot.get_chat(user['id'])
        except:
            await db.delete_user(user['id'])
            deleted += 1
    await msg.edit(f"<b>✅ Purge Complete!</b>\nRemoved {deleted} Zombie Users.")

# ==============================================================================
# 📊 STATS
# ==============================================================================
@Client.on_message(filters.command('stats') & filters.user(ADMINS))
async def stats(bot, message):
    pri, bak, total_files = await db_count_documents()
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    prm = await db.get_premium_count()
    used_bytes, free_bytes = await db.get_db_size()
    
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid').upper()
    
    text = script.STATUS_TXT.format(
        pri, bak, total_files, users, chats, prm, 
        get_size(used_bytes), get_size(free_bytes), mode, 
        get_readable_time(time.time() - temp.START_TIME)
    )
    await message.reply_text(text)

# ==============================================================================
# 🔗 UTILITY COMMANDS (LINK / PLAN / REF / CLONE) - 🔥 FIXED
# ==============================================================================

@Client.on_message(filters.command('link'))
async def link(bot, message):
    msg = message.reply_to_message
    if not msg: return await message.reply('<b>Reply to a File!</b>')
    try:
        media = getattr(msg, msg.media.value)
        # Assuming you have a route like /watch/{id} set up in web/route.py
        # You might need to forward to BIN_CHANNEL to get a permanent ID if not public
        if BIN_CHANNEL:
            try:
                msg = await msg.copy(BIN_CHANNEL)
            except: pass # If failed, uses original
            
        online = f"{URL}watch/{msg.id}"
        download = f"{URL}download/{msg.id}"
        
        await message.reply_text(
            f"<b>🔗 Link Generated!</b>\n\n<b>📺 Watch:</b> {online}\n<b>📥 Download:</b> {download}",
            quote=True,
            disable_web_page_preview=True
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command(["plan", "premium"]))
async def plan(client, message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    status = user.get('status', {})
    
    is_prem = status.get('premium', False)
    expiry = status.get('expire', 'Never')
    
    # 🖼️ GENERATE QR CODE FOR PAYMENT
    # Using UPI_ID from info.py
    if UPI_ID:
        upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&cu=INR"
        qr = qrcode.make(upi_url)
        bio = io.BytesIO()
        qr.save(bio)
        bio.seek(0)
        
        caption = (
            f"<b>💎 PREMIUM PLANS</b>\n\n"
            f"<b>👤 User:</b> {message.from_user.mention}\n"
            f"<b>📊 Status:</b> {'✅ Premium' if is_prem else '❌ Free'}\n"
            f"<b>⏳ Expires:</b> {expiry}\n\n"
            f"<b>💸 Pricing:</b>\n"
            f"• 1 Month: ₹30\n"
            f"• 1 Year: ₹200\n\n"
            f"<i>Scan QR to pay and send screenshot to Admin.</i>"
        )
        
        btn = [[InlineKeyboardButton("📤 Send Screenshot", url=f"https://t.me/{RECEIPT_SEND_USERNAME}")]]
        await message.reply_photo(photo=bio, caption=caption, reply_markup=InlineKeyboardMarkup(btn))
    else:
        await message.reply("❌ Payment details not configured by Admin.")

@Client.on_message(filters.command("referral"))
async def referral(client, message):
    user_id = message.from_user.id
    link = f"https://t.me/{temp.U_NAME}?start=ref_{user_id}"
    
    balance = await db.get_balance(user_id)
    conf = await db.get_config()
    points = conf.get('points_per_referral', 10)
    
    text = (
        f"<b>💰 REFERRAL SYSTEM</b>\n\n"
        f"<b>🔗 Link:</b> {link}\n\n"
        f"<b>💵 Your Points:</b> {balance}\n"
        f"<b>🎁 Per Refer:</b> {points} Points\n\n"
        f"<i>Collect points to redeem Premium!</i>"
    )
    
    btn = [[InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join%20this%20awesome%20bot!")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

async def process_referral(client, message):
    try:
        ref_by = int(message.command[1].split("_")[1])
        if ref_by == message.from_user.id: return # Cannot refer self
        
        if not await db.is_user_exist(message.from_user.id):
            conf = await db.get_config()
            points = conf.get('points_per_referral', 10)
            
            await db.inc_balance(ref_by, points)
            try:
                await client.send_message(ref_by, f"<b>🎉 New Referral!</b>\n\n{message.from_user.mention} joined using your link.\n<b>➕ Added:</b> {points} Points")
            except: pass
    except: pass

@Client.on_message(filters.command("clone"))
async def clone_bot(client, message):
    await message.reply(
        "<b>🤖 CLONE BOT CREATOR</b>\n\n"
        "1. Create a bot in @BotFather\n"
        "2. Get the <b>Bot Token</b>\n"
        "3. Send the token here.\n\n"
        "<i>Feature coming soon in V2 UI...</i>"
    )
