import logging
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from utils import temp
from database.users_chats_db import db
from info import SUPPORT_LINK

# लॉगिंग सेट करें
logger = logging.getLogger(__name__)

async def banned_users(_, __, message: Message):
    """चेक करता है कि यूजर temp.BANNED_USERS लिस्ट में है या नहीं"""
    return (
        message.from_user is not None or not message.sender_chat
    ) and message.from_user.id in temp.BANNED_USERS

# कस्टम फ़िल्टर बनाएँ
banned_user_filter = filters.create(banned_users)

async def disabled_chat(_, __, message: Message):
    """चेक करता है कि ग्रुप temp.BANNED_CHATS लिस्ट में है या नहीं"""
    return message.chat.id in temp.BANNED_CHATS

# कस्टम फ़िल्टर बनाएँ
disabled_group_filter = filters.create(disabled_chat)


@Client.on_message(filters.private & banned_user_filter & filters.incoming)
async def is_user_banned(bot, message):
    """बैन किए गए यूजर को हैंडल करता है"""
    
    # DB से बैन का कारण प्राप्त करें
    ban_info = await db.get_ban_status(message.from_user.id)
    reason = ban_info.get("ban_reason", "No reason provided")
    
    buttons = [[
        InlineKeyboardButton('Support Group', url=SUPPORT_LINK)
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    try:
        await message.reply(
            f'Sorry {message.from_user.mention},\nMy owner has banned you from using me!\n\n'
            f'If you think this is a mistake, contact the support group.\n'
            f'<b>Reason:</b> <code>{reason}</code>',
            reply_markup=reply_markup,
            quote=True
        )
    except Exception as e:
        logger.warning(f"Failed to reply to banned user {message.from_user.id}: {e}")

    # महत्वपूर्ण: मैसेज को आगे प्रोसेस होने से रोकें (ताकि ऑटो-फ़िल्टर न चले)
    message.stop_propagation()


@Client.on_message(filters.group & disabled_group_filter & filters.incoming)
async def is_group_disabled(bot, message):
    """बैन किए गए ग्रुप को हैंडल करता है"""
    
    # DB से ग्रुप बैन का कारण प्राप्त करें
    chat_info = await db.get_chat(message.chat.id)
    reason = chat_info.get('reason', "No reason provided") if chat_info else "Unknown"
    
    buttons = [[
        InlineKeyboardButton('Support Group', url=SUPPORT_LINK)
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    try:
        k = await message.reply(
            text=f"<b><u>🚫 Chat Not Allowed 🚫</u></b>\n\n"
                 f"My owner has restricted me from working here!\n"
                 f"<b>Reason:</b> <code>{reason}</code>\n\n"
                 f"I am leaving now. Bye!",
            reply_markup=reply_markup
        )
        # मैसेज को पिन करने की कोशिश करें
        try:
            await k.pin()
        except Exception:
            pass
            
        # ग्रुप छोड़ दें
        await bot.leave_chat(message.chat.id)
        
    except Exception as e:
        logger.error(f"Error handling disabled group {message.chat.id}: {e}")
        # अगर मैसेज नहीं भेज पाए, तो भी ग्रुप छोड़ने की कोशिश करें
        try:
            await bot.leave_chat(message.chat.id)
        except:
            pass

    # महत्वपूर्ण: मैसेज को आगे प्रोसेस होने से रोकें
    message.stop_propagation()
