import logging
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import QueryIdInvalid
from hydrogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton

from database.ia_filterdb import get_search_results
from database.users_chats_db import db
from utils import get_size, temp, is_subscribed
from info import IS_PREMIUM, MAX_BTN

logger = logging.getLogger(__name__)

# ==============================================================================
# 🔍 INLINE SEARCH HANDLER (GOD MODE)
# ==============================================================================
@Client.on_inline_query()
async def answer(client, query):
    """
    Handles Inline Searches with Dual DB support, Google Fallback & Deep Links.
    """
    text = query.query.lower().strip()
    user_id = query.from_user.id
    
    # 1. Initialize Bot Username (For Deep Links)
    if not temp.U_NAME:
        temp.U_NAME = (await client.get_me()).username

    # 2. Empty Query Handler
    if not text:
        await client.answer_inline_query(
            query.id,
            results=[],
            switch_pm_text="🔎 Type to Search Movies/Series...",
            switch_pm_parameter="help",
            cache_time=0
        )
        return

    # 3. Fetch Config (Admin Mood Check: Primary/Backup/Hybrid)
    conf = await db.get_config()
    mode = conf.get('search_mode', 'hybrid') 
    
    # 4. Search Engine (Hybrid)
    offset = int(query.offset) if query.offset else 0
    
    files, next_offset, total = await get_search_results(
        text, 
        offset=offset, 
        max_results=MAX_BTN, 
        mode=mode # 🔥 Passing Admin's Mode Preference
    )
    
    results = []
    
    # 5. Result Formatting (Deep Links)
    if files:
        for file in files:
            # File Details
            f_name = file['file_name']
            f_size = get_size(file['file_size'])
            f_caption = file.get('caption', '')
            
            # 🔗 Deep Link Generator
            # यह लिंक यूजर को PM में भेजेगा जहाँ Ads/Verify सिस्टम काम करेगा
            deep_link = f"https://t.me/{temp.U_NAME}?start=file_{user_id}_{file['file_id']}"
            
            # Dynamic Thumbnail (Visuals)
            thumb = "https://cdn-icons-png.flaticon.com/512/2885/2885461.png" # Default Video
            if "mkv" in f_name.lower(): thumb = "https://cdn-icons-png.flaticon.com/512/2666/2666453.png"
            elif "mp4" in f_name.lower(): thumb = "https://cdn-icons-png.flaticon.com/512/2666/2666506.png"
            
            # Description Text
            desc = f"💾 Size: {f_size} | 📂 DB: {mode.title()}"
            
            results.append(
                InlineQueryResultArticle(
                    title=f_name,
                    description=desc,
                    thumb_url=thumb,
                    input_message_content=InputTextMessageContent(
                        message_text=f"<b>📂 Fɪʟᴇ:</b> {f_name}\n<b>💾 Sɪᴢᴇ:</b> {f_size}\n\n<b>👇 Cʟɪᴄᴋ Bᴇʟᴏᴡ ᴛᴏ Dᴏᴡɴʟᴏᴀᴅ:</b>",
                        parse_mode=enums.ParseMode.HTML
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🚀 Gᴇᴛ Fɪʟᴇ (Fᴀsᴛ)", url=deep_link)]
                    ])
                )
            )
    else:
        # 👑 GOD MODE: GOOGLE FALLBACK
        # अगर फाइल नहीं मिली, तो Google Search का बटन दिखाओ
        google_url = f"https://www.google.com/search?q={text.replace(' ', '+')}"
        
        results.append(
            InlineQueryResultArticle(
                title="😕 No Results Found!",
                description=f"Click here to search '{text}' on Google.",
                thumb_url="https://cdn-icons-png.flaticon.com/512/2965/2965363.png", # Search Icon
                input_message_content=InputTextMessageContent(
                    message_text=f"<b>❌ No files found for:</b> <code>{text}</code>\n\n<i>Try checking the spelling or request the admin.</i>",
                    parse_mode=enums.ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Search on Google", url=google_url)],
                    [InlineKeyboardButton("👨‍💻 Request to Admin", url=f"https://t.me/{temp.U_NAME}?start=help")]
                ])
            )
        )

    # 6. Send Answers
    # Cache: 0 for Admins (Live Testing), 60 for Users (Performance)
    cache = 0 if user_id in conf.get('admins', []) else 60
    
    try:
        await client.answer_inline_query(
            query.id,
            results=results,
            cache_time=cache,
            next_offset=str(next_offset) if next_offset else ""
        )
    except QueryIdInvalid:
        pass
    except Exception as e:
        logger.error(f"Inline Error: {e}")
