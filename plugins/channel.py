
import logging
from hydrogram import Client, filters
from info import INDEX_CHANNELS
# 🔥 IMPORT get_target_db TO CHECK ROUTING RULES
from database.ia_filterdb import save_file, update_file, get_target_db
from database.users_chats_db import db

logger = logging.getLogger(__name__)

@Client.on_message(filters.channel & filters.incoming)
async def index_handler(bot, message):
    # 1. Check Media
    if not message.media:
        return 

    # 2. Chat ID Check
    chat_id = message.chat.id
    
    is_indexed = False
    # Check Environment Variables
    if chat_id in INDEX_CHANNELS:
        is_indexed = True
    else:
        # Check Database Channels
        try:
            db_channels = await db.get_index_channels_db()
            if chat_id in db_channels:
                is_indexed = True
        except:
            pass

    if not is_indexed:
        return

    # 3. Media Extract
    try:
        media = getattr(message, message.media.value)
    except:
        return

    # 4. Junk Filter (2MB Check)
    if media.file_size < 2 * 1024 * 1024:
        return 

    # 5. Save to DB with ROUTING LOGIC
    media.file_type = message.media.value
    media.caption = message.caption

    # 🔥 NEW: चेक करो कि फाइल किस DB (Primary/Backup) में जानी चाहिए
    target_db = await get_target_db(chat_id)

    try:
        # Pass target_db to save_file
        sts = await save_file(media, target_db=target_db)
        
        if sts == 'suc':
            try: await message.react(emoji="💖")
            except: pass
            logger.info(f"✅ Auto-Indexed to [{target_db.upper()}]: {getattr(media, 'file_name', 'Unknown')}")
            
        elif sts == 'dup':
            try: await message.react(emoji="🦄")
            except: pass
            
        elif sts == 'err':
            try: await message.react(emoji="💔")
            except: pass
            
    except Exception as e:
        logger.error(f"Channel Index Error: {e}")

# --- EDIT HANDLER ---
@Client.on_edited_message(filters.channel)
async def edit_handler(bot, message):
    if not message.media: return
    
    # ID Check logic
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
    
    try: media = getattr(message, message.media.value)
    except: return
    
    if media.file_size < 2 * 1024 * 1024: return

    media.file_type = message.media.value
    media.caption = message.caption
    
    # 🔥 UPDATE BOTH DATABASES (Managed internally by update_file)
    try:
        await update_file(media)
        try: await message.react(emoji="✍️")
        except: pass
        logger.info(f"📝 File Updated: {getattr(media, 'file_name', 'Unknown')}")
    except Exception as e:
        logger.error(f"Edit Error: {e}")
