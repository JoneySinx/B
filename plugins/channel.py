import asyncio
import logging
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from info import INDEX_CHANNELS, IS_STREAM
from database.ia_filterdb import save_file
from database.users_chats_db import db
from utils import temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 📥 MEDIA HANDLER (NEW POSTS)
# ==============================================================================
@Client.on_message(filters.incoming & (filters.video | filters.document | filters.audio))
async def media_process(bot, message):
    """
    Automatically indexes files.
    Features: Dual Save, Hybrid Channel Check, Auto-Buttons, Smart Reactions.
    """
    # 1. Check if Media Exists
    if not message.media: return

    # 2. Hybrid Channel Check (Env + DB)
    chat_id = message.chat.id
    is_indexed = False
    
    if chat_id in INDEX_CHANNELS:
        is_indexed = True
    else:
        try:
            db_channels = await db.get_index_channels_db()
            if chat_id in db_channels:
                is_indexed = True
        except: pass

    if not is_indexed: return

    # 3. Junk Check (Ignore files < 2MB) (Optional)
    # if message.document and message.document.file_size < 2 * 1024 * 1024: return

    media = getattr(message, message.media.value)
    
    # 4. SAVE TO PRIMARY DB
    try:
        status = await save_file(media, target_db="primary")
        
        # 👑 GOD MODE: DUAL SAVE CHECK
        # अगर एडमिन ने Dual Save ऑन किया है, तो Backup में भी सेव करो
        conf = await db.get_config()
        if conf.get('dual_save_mode', True): # Default ON
            await save_file(media, target_db="backup")
            
        if status == 'suc':
            logger.info(f"✅ Indexed: {message.id} | {message.chat.title}")
            try: await message.react(emoji="🔥")
            except: pass

            # 🔘 AUTO-BUTTONER (Magic Feature)
            # पोस्ट के नीचे डायरेक्ट डाउनलोड बटन लगाना
            if conf.get('auto_channel_buttons', True):
                await attach_button(bot, message, media)
                
        elif status == 'dup':
            logger.info(f"⚠️ Duplicate: {message.id} | {message.chat.title}")
            try: await message.react(emoji="👀")
            except: pass
            
        elif status == 'err':
            logger.error(f"❌ Error Saving: {message.id}")
            try: await message.react(emoji="💔")
            except: pass
            
    except Exception as e:
        logger.error(f"❌ Channel Handler Error: {e}")

# ==============================================================================
# ✏️ EDIT HANDLER (LIVE SYNC)
# ==============================================================================
@Client.on_edited_message(filters.incoming & (filters.video | filters.document | filters.audio))
async def edit_process(bot, message):
    """
    Updates the database if a file caption/name is edited in the channel.
    """
    if not message.media: return

    # 1. Hybrid Channel Check
    chat_id = message.chat.id
    is_indexed = False
    if chat_id in INDEX_CHANNELS:
        is_indexed = True
    else:
        try:
            db_channels = await db.get_index_channels_db()
            if chat_id in db_channels: is_indexed = True
        except: pass
        
    if not is_indexed: return

    media = getattr(message, message.media.value)
    
    # 2. Update Primary (Re-save acts as update/check)
    await save_file(media, target_db="primary")
    
    # 3. Update Backup
    conf = await db.get_config()
    if conf.get('dual_save_mode', True):
        await save_file(media, target_db="backup")
        
    logger.info(f"🔄 Updated: {message.id} | {message.chat.title}")
    try: await message.react(emoji="✍️")
    except: pass
    
    # 4. Refresh Button (if caption changed)
    if conf.get('auto_channel_buttons', True):
        await attach_button(bot, message, media)

# ==============================================================================
# 🛠️ HELPER: ATTACH BUTTON TO CHANNEL POST
# ==============================================================================
async def attach_button(bot, message, media):
    """
    Edits the channel post to add a 'Get File' button.
    """
    try:
        from info import URL as SITE_URL
        
        # 1. Get Bot Username (Cached)
        if not temp.U_NAME:
            bot_info = await bot.get_me()
            temp.U_NAME = bot_info.username

        # 2. Create Links
        bot_link = f"https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{media.file_id}"
        
        # Stream Link (Optional)
        stream_link = f"{SITE_URL}watch/{message.id}" if SITE_URL else None
        
        # 3. Create Button Markup
        btn = []
        row1 = [InlineKeyboardButton("📂 Gᴇᴛ Fɪʟᴇ", url=bot_link)]
        
        if IS_STREAM and stream_link:
             row1.append(InlineKeyboardButton("▶️ Wᴀᴛᴄʜ", url=stream_link))
        
        btn.append(row1)
        
        # 4. Edit Message
        await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to add button: {e}")
