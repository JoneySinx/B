import logging
from hydrogram import Client, filters, enums
from info import INDEX_CHANNELS
from database.ia_filterdb import save_file
from database.users_chats_db import db

logger = logging.getLogger(__name__)

# मीडिया फिल्टर (Document, Video, Audio)
media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.channel & media_filter)
async def media_handler(bot, message):
    """
    Foolproof Auto-Indexing:
    Checks EVERY channel message, validates ID, then saves.
    """
    # 1. Get Chat ID
    chat_id = message.chat.id
    
    # 2. Check Permissions (Optional but good for debug)
    # अगर बोट लिख नहीं सकता तो शायद वह इंडेक्स भी न करे, लेकिन हम इसे स्किप कर रहे हैं ताकि लॉग्स दिखें।

    # 3. Check if this Channel is in Config (info.py) OR Database
    is_indexed = False
    
    # A. Check Config
    if chat_id in INDEX_CHANNELS:
        is_indexed = True
    else:
        # B. Check Database (Dynamic Channels)
        try:
            db_channels = await db.get_index_channels_db()
            if chat_id in db_channels:
                is_indexed = True
        except Exception as e:
            logger.error(f"DB Channel Check Error: {e}")

    # अगर यह इंडेक्स चैनल नहीं है, तो तुरंत रिटर्न हो जाएं (Ignore)
    if not is_indexed:
        return

    # --- JUNK FILTER (Size Check) ---
    media = getattr(message, message.media.value, None)
    if not media:
        return

    # 2MB से कम है तो इग्नोर करें और Trash भेजें
    if media.file_size < 2 * 1024 * 1024: 
        try: await message.react(emoji="🗑️")
        except: pass
        return

    media.file_type = message.media.value
    media.caption = message.caption
    
    try:
        # Save to DB
        sts = await save_file(media)
        
        # --- VISUAL UI ---
        if sts == 'suc':
            try: await message.react(emoji="💖")
            except: pass
            logger.info(f"✅ Auto Indexed: {getattr(media, 'file_name', 'Unknown')} from {message.chat.title}")
            
        elif sts == 'dup':
            try: await message.react(emoji="🦄")
            except: pass
            
        elif sts == 'err':
            try: await message.react(emoji="💔")
            except: pass
            logger.error(f"❌ Error Saving: {getattr(media, 'file_name', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"Channel Handler Error: {e}")

@Client.on_edited_message(filters.channel & media_filter)
async def media_edit_handler(bot, message):
    """
    Update Database when file is Edited (Direct Logic)
    """
    chat_id = message.chat.id
    
    # Validation Logic
    is_indexed = False
    if chat_id in INDEX_CHANNELS:
        is_indexed = True
    else:
        try:
            db_channels = await db.get_index_channels_db()
            if chat_id in db_channels:
                is_indexed = True
        except: pass
        
    if not is_indexed:
        return

    media = getattr(message, message.media.value, None)
    if not media:
        return

    if media.file_size < 2 * 1024 * 1024:
        return

    media.file_type = message.media.value
    media.caption = message.caption
    
    try:
        await save_file(media)
        try: await message.react(emoji="✍️")
        except: pass
        logger.info(f"📝 File Updated: {getattr(media, 'file_name', 'Unknown')}")
    except Exception as e:
        logger.error(f"Channel Edit Error: {e}")
