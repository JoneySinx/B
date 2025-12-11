import logging
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp
from database.users_chats_db import db
from info import SUPPORT_LINK

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

# --- BANNED USER HANDLER (PRIVATE) ---
@Client.on_message(filters.private & banned_user_filter & filters.incoming)
async def is_user_banned(bot, message):
    """बैन किए गए यूजर को हैंडल करता है"""
    
    # DB से बैन का कारण प्राप्त करें
    ban_info = await db.get_ban_status(message.from_user.id)
    reason = ban_info.get("ban_reason", "Violation of Rules")
    
    # Advanced UI Message
    text = (
        f"<b>🚫 Aᴄᴄᴇss Dᴇɴɪᴇᴅ / प्रवेश वर्जित</b>\n\n"
        f"👮‍♂️ <b>Dᴇᴀʀ Usᴇʀ:</b> {message.from_user.mention}\n"
        f"🛑 <b>Sᴛᴀᴛᴜs:</b> <code>Bᴀɴɴᴇᴅ 🔒</code>\n\n"
        f"📝 <b>Rᴇᴀsᴏɴ:</b> <code>{reason}</code>\n\n"
        f"<i>If you think this is a mistake, please contact support.</i>"
    )

    btn = [[InlineKeyboardButton('🛠️ Sᴜᴘᴘᴏʀᴛ / सहायता', url=SUPPORT_LINK)]]
    
    try:
        # कोट करके रिप्लाई करें ताकि यूजर को पता चले
        await message.reply(
            text=text,
            reply_markup=InlineKeyboardMarkup(btn),
            quote=True
        )
    except Exception as e:
        logger.warning(f"Failed to reply to banned user {message.from_user.id}: {e}")
    
    # आगे की प्रोसेसिंग रोकें
    message.stop_propagation()

# --- DISABLED GROUP HANDLER (GROUPS) ---
@Client.on_message(filters.group & disabled_group_filter & filters.incoming)
async def is_group_disabled(bot, message):
    """बैन किए गए ग्रुप को हैंडल करता है और Leave करता है"""
    
    # DB से ग्रुप बैन का कारण प्राप्त करें
    chat_info = await db.get_chat(message.chat.id)
    reason = chat_info.get('reason', "Policy Violation") if chat_info else "Unknown"
    
    # Advanced UI Message for Groups
    text = (
        f"<b>🚫 Sᴇʀᴠɪᴄᴇ Tᴇʀᴍɪɴᴀᴛᴇᴅ / सेवा समाप्त</b>\n\n"
        f"🛑 <b>Gʀᴏᴜᴘ:</b> {message.chat.title}\n"
        f"🔒 <b>Sᴛᴀᴛᴜs:</b> <code>Dɪsᴀʙʟᴇᴅ ʙʏ Aᴅᴍɪɴ</code>\n\n"
        f"📝 <b>Rᴇᴀsᴏɴ:</b> <code>{reason}</code>\n\n"
        f"<i>🤖 The bot will leave this chat now. Contact support for appeals.</i>"
    )

    btn = [[InlineKeyboardButton('🛠️ Sᴜᴘᴘᴏʀᴛ / सहायता', url=SUPPORT_LINK)]]

    try:
        # 1. Send Warning Message
        sent_msg = await message.reply(
            text=text,
            reply_markup=InlineKeyboardMarkup(btn)
        )
        
        # 2. Try to Pin the message (So admins see it)
        try:
            await sent_msg.pin(disable_notification=False)
        except Exception:
            pass # पिन की परमिशन नहीं होगी तो इग्नोर करें
        
        # 3. Wait 5 Seconds (User पढ़ने का समय)
        await asyncio.sleep(5)
        
        # 4. Leave Chat
        await bot.leave_chat(message.chat.id)
        
    except Exception as e:
        logger.error(f"Error handling disabled group {message.chat.id}: {e}")
        # अगर मैसेज नहीं भेज पाए, तो भी चुपचाप निकलने की कोशिश करें
        try:
            await bot.leave_chat(message.chat.id)
        except:
            pass

    # आगे की प्रोसेसिंग रोकें
    message.stop_propagation()
