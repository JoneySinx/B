import logging
from hydrogram import Client, filters, enums
from info import INDEX_CHANNELS
from database.ia_filterdb import save_file

logger = logging.getLogger(__name__)

# मीडिया फिल्टर
media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.chat(INDEX_CHANNELS) & media_filter)
async def media_handler(bot, message):
    """
    Auto-Index with 2MB Limit & Smart Reactions
    """
    media = getattr(message, message.media.value, None)
    if not media:
        return

    # --- 1. JUNK FILTER (Reaction Added) ---
    # अगर फाइल 2MB से छोटी है, तो उसे इग्नोर करें और 🗑️ दें
    if media.file_size < 2 * 1024 * 1024: 
        try: await message.react(emoji="🗑️")
        except: pass
        return

    media.file_type = message.media.value
    media.caption = message.caption
    
    try:
        sts = await save_file(media)
        
        # --- 2. VISUAL UI (Smart Reactions) ---
        if sts == 'suc':
            # नई फाइल सेव होने पर 'Sparkling Heart'
            try: await message.react(emoji="💖")
            except: pass
            logger.info(f"Auto Indexed: {getattr(media, 'file_name', 'Unknown')}")
            
        elif sts == 'dup':
            # डुप्लीकेट फाइल पर 'Unicorn'
            try: await message.react(emoji="🦄")
            except: pass
            logger.info(f"File Already Exists: {getattr(media, 'file_name', 'Unknown')}")
            
        elif sts == 'err':
            # एरर आने पर 'Broken Heart'
            try: await message.react(emoji="💔")
            except: pass
            logger.error(f"Error Saving File: {getattr(media, 'file_name', 'Unknown')}")
            
    except Exception as e:
        logger.error(f"Channel Handler Error: {e}")

@Client.on_edited_message(filters.chat(INDEX_CHANNELS) & media_filter)
async def media_edit_handler(bot, message):
    """
    Update Database when file is Edited
    """
    media = getattr(message, message.media.value, None)
    if not media:
        return

    # 2MB Limit for Edits too
    if media.file_size < 2 * 1024 * 1024:
        try: await message.react(emoji="🗑️")
        except: pass
        return

    media.file_type = message.media.value
    media.caption = message.caption
    
    try:
        await save_file(media)
        # एडिट होने पर 'Writing Hand' रिएक्शन
        try: await message.react(emoji="✍️")
        except: pass
        logger.info(f"File Updated (Edited): {getattr(media, 'file_name', 'Unknown')}")
    except Exception as e:
        logger.error(f"Channel Edit Error: {e}")
