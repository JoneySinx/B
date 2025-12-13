import logging
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp
from database.users_chats_db import db
from info import SUPPORT_LINK, LOG_CHANNEL, ADMINS

# लॉगिंग सेट करें
logger = logging.getLogger(__name__)

# --- CUSTOM FILTERS (Optimized) ---

async def banned_users(_, __, message: Message):
    """चेक करता है कि क्या यूजर BANNED_USERS लिस्ट में है"""
    if not message.from_user:
        return False
    return message.from_user.id in temp.BANNED_USERS

async def disabled_chat(_, __, message: Message):
    """चेक करता है कि क्या ग्रुप BANNED_CHATS लिस्ट में है"""
    return message.chat.id in temp.BANNED_CHATS

# कस्टम फिल्टर बनाएं
banned_user_filter = filters.create(banned_users)
disabled_group_filter = filters.create(disabled_chat)

# ==============================================================================
# 🚫 BANNED USER HANDLER (JAIL SYSTEM)
# ==============================================================================
@Client.on_message(filters.private & banned_user_filter & filters.incoming)
async def is_user_banned(bot, message):
    """
    Handles Banned Users with God Mode Features (Shadow Ban & Alerts).
    """
    user_id = message.from_user.id
    
    # 1. Fetch Ban Details
    ban_info = await db.get_ban_status(user_id)
    reason = ban_info.get("ban_reason", "Violation of Rules") if ban_info else "Bad Behavior"
    
    # 👑 GOD MODE: SHADOW BAN CHECK
    # अगर 'is_shadow' True है, तो बोट रिप्लाई ही नहीं करेगा (Silent Ignore)
    if ban_info and ban_info.get("is_shadow", False):
        message.stop_propagation()
        return

    # 🚨 SECURITY ALERT (LOG CHANNEL)
    # एडमिन को पता चलना चाहिए कि कैदी भागने की कोशिश कर रहा है
    try:
        await bot.send_message(
            LOG_CHANNEL,
            f"<b>🚨 BANNED USER DETECTED</b>\n\n"
            f"👤 <b>User:</b> {message.from_user.mention} (`{user_id}`)\n"
            f"📝 <b>Tried to Send:</b> `{message.text[:50]}`\n"
            f"🚫 <b>Reason:</b> {reason}"
        )
    except: pass

    # 2. Advanced Ban Message
    text = (
        f"<b>🚫 Aᴄᴄᴇss Dᴇɴɪᴇᴅ / प्रवेश वर्जित</b>\n\n"
        f"👮‍♂️ <b>Usᴇʀ:</b> {message.from_user.mention}\n"
        f"🛑 <b>Sᴛᴀᴛᴜs:</b> <code>Bʟᴀᴄᴋʟɪsᴛᴇᴅ 🔒</code>\n\n"
        f"📝 <b>Rᴇᴀsᴏɴ:</b> <code>{reason}</code>\n\n"
        f"<i>⚠️ You have been banned by the Administrator. If you think this is a mistake, you can submit an appeal.</i>"
    )

    # 3. Appeal Button (Auto-Generated Message)
    appeal_msg = f"Hello Admin, I am banned from the bot.\nID: {user_id}\nReason: {reason}\nPlease review my ban."
    appeal_url = f"https://t.me/share/url?url={appeal_msg}"

    btn = [
        [InlineKeyboardButton('🛠️ Sᴜᴘᴘᴏʀᴛ Cʜᴀᴛ', url=SUPPORT_LINK)],
        [InlineKeyboardButton('📝 Sᴜʙᴍɪᴛ Aᴘᴘᴇᴀʟ', url=appeal_url)] # One-Click Appeal
    ]
    
    try:
        await message.reply(
            text=text,
            reply_markup=InlineKeyboardMarkup(btn),
            quote=True
        )
    except Exception as e:
        logger.warning(f"Failed to reply to banned user {user_id}: {e}")
    
    # आगे की प्रोसेसिंग रोकें
    message.stop_propagation()

# ==============================================================================
# 🛑 DISABLED GROUP HANDLER (AUTO-PURGE)
# ==============================================================================
@Client.on_message(filters.group & disabled_group_filter & filters.incoming)
async def is_group_disabled(bot, message):
    """
    Handles Banned Groups -> Warns, Pins, Leaves.
    """
    # 1. Fetch Group Details
    chat_info = await db.get_chat(message.chat.id)
    reason = chat_info.get('reason', "Policy Violation") if chat_info else "Spam/Abuse"
    
    # 2. Termination Message
    text = (
        f"<b>🚫 Sᴇʀᴠɪᴄᴇ Tᴇʀᴍɪɴᴀᴛᴇᴅ</b>\n\n"
        f"🛑 <b>Gʀᴏᴜᴘ:</b> {message.chat.title}\n"
        f"🔒 <b>Sᴛᴀᴛᴜs:</b> <code>Dɪsᴀʙʟᴇᴅ ʙʏ Aᴅᴍɪɴ</code>\n\n"
        f"📝 <b>Rᴇᴀsᴏɴ:</b> <code>{reason}</code>\n\n"
        f"<i>🤖 The bot will leave this chat in 5 seconds.</i>"
    )

    btn = [[InlineKeyboardButton('👮‍♂️ Cᴏɴᴛᴀᴄᴛ Sᴜᴘᴘᴏʀᴛ', url=SUPPORT_LINK)]]

    try:
        # Send Warning
        sent_msg = await message.reply(text, reply_markup=InlineKeyboardMarkup(btn))
        
        # Try to Pin (For Visibility)
        try: await sent_msg.pin(disable_notification=False)
        except: pass
        
        # Wait for users to read
        await asyncio.sleep(5)
        
        # Leave
        await bot.leave_chat(message.chat.id)
        
    except Exception as e:
        logger.error(f"Error leaving disabled group {message.chat.id}: {e}")
        try: await bot.leave_chat(message.chat.id)
        except: pass

    message.stop_propagation()
