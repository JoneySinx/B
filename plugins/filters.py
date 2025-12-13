import re
import logging
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import is_check_admin

logger = logging.getLogger(__name__)

# ==============================================================================
# 🛠️ HELPER: SMART VARIABLES & BUTTON PARSER
# ==============================================================================

def replace_text(text, message):
    """
    Replaces variables like {mention}, {id} with real values.
    """
    if not text:
        return ""
    
    return text.format(
        first=message.from_user.first_name,
        last=message.from_user.last_name or "",
        fullname=message.from_user.first_name + (f" {message.from_user.last_name}" if message.from_user.last_name else ""),
        username=f"@{message.from_user.username}" if message.from_user.username else "No Username",
        mention=message.from_user.mention,
        id=message.from_user.id,
        chat_name=message.chat.title,
        query=message.text
    )

def parse_buttons(text):
    """
    Extracts buttons from text.
    Format: [Button Name](url)
    """
    buttons = []
    regex = r"\[([^\[]+?)\]\((.+?)\)"
    matches = re.findall(regex, text)
    
    if not matches:
        return None, text
        
    new_text = re.sub(regex, "", text).strip()
    
    for name, url in matches:
        # Simple URL check
        if "://" in url or "t.me" in url:
            buttons.append([InlineKeyboardButton(name, url=url.strip())])
    
    return InlineKeyboardMarkup(buttons) if buttons else None, new_text

# ==============================================================================
# ➕ ADD FILTER (/filter or /add)
# ==============================================================================
@Client.on_message(filters.command(["filter", "add"]) & filters.group)
async def add_filter(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Aᴄᴄᴇss Dᴇɴɪᴇᴅ!</b>\nOnly Admins can save filters.")
    
    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply(
            "<b>⚠️ Usᴀɢᴇ:</b>\n"
            "Reply to a message with <code>/filter name</code>\n\n"
            "<b>💡 Pro Tips:</b>\n"
            "• Use <code>{mention}</code> for user tagging.\n"
            "• Use <code>[Button](url)</code> for buttons.\n"
            "• Add <code>{del}</code> to delete user msg."
        )
    
    try:
        name = message.text.split(None, 1)[1].lower().strip()
    except IndexError:
        return await message.reply("<b>❌ Eʀʀᴏʀ:</b> Please provide a name!\nExample: <code>/filter rules</code>")
    
    reply = message.reply_to_message
    filter_data = {}
    
    if reply:
        # 1. Text Filter
        if reply.text:
            filter_data['type'] = 'text'
            filter_data['text'] = reply.text.markdown # Save markdown for buttons
        
        # 2. Media Filter
        elif reply.media:
            filter_data['type'] = 'media'
            media_obj = getattr(reply, reply.media.value)
            filter_data['file_id'] = media_obj.file_id
            filter_data['media_type'] = str(reply.media.value)
            filter_data['caption'] = reply.caption.markdown if reply.caption else ""
        else:
            return await message.reply("<b>❌ Uɴsᴜᴘᴘᴏʀᴛᴇᴅ Mᴇssᴀɢᴇ Tʏᴘᴇ!</b>")
    else:
        return await message.reply("<b>⚠️ Pʟᴇᴀsᴇ Rᴇᴘʟʏ ᴛᴏ ᴀ Mᴇssᴀɢᴇ!</b>")

    # Save to DB
    await db.add_filter(message.chat.id, name, filter_data)
    await message.reply(f"<b>✅ Fɪʟᴛᴇʀ Sᴀᴠᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n<b>🔖 Nᴀᴍᴇ:</b> <code>{name}</code>")

# ==============================================================================
# 🗑️ DELETE FILTER (/stop or /del)
# ==============================================================================
@Client.on_message(filters.command(["stop", "del"]) & filters.group)
async def stop_filter(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Aᴄᴄᴇss Dᴇɴɪᴇᴅ!</b>\nOnly Admins can delete filters.")
        
    if len(message.command) < 2:
        return await message.reply("<b>⚠️ Usᴀɢᴇ:</b> <code>/stop name</code>")
    
    name = message.text.split(None, 1)[1].lower().strip()
    
    deleted = await db.delete_filter(message.chat.id, name)
    if deleted:
        await message.reply(f"<b>🗑️ Fɪʟᴛᴇʀ Dᴇʟᴇᴛᴇᴅ:</b> <code>{name}</code>")
    else:
        await message.reply("<b>❌ Fɪʟᴛᴇʀ Nᴏᴛ Fᴏᴜɴᴅ!</b>")

# ==============================================================================
# ♻️ DELETE ALL FILTERS
# ==============================================================================
@Client.on_message(filters.command(["stopall", "delall"]) & filters.group)
async def stop_all_filters(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Aᴅᴍɪɴ Oɴʟʏ!</b>")
    
    # Verification
    btn = [[InlineKeyboardButton("✅ YES, DELETE ALL", callback_data="confirm_delall_filters")], [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]]
    await message.reply("<b>⚠️ Are you sure you want to delete ALL filters?</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex("confirm_delall_filters"))
async def confirm_delall(client, query):
    if not await is_check_admin(client, query.message.chat.id, query.from_user.id):
        return await query.answer("🛑 Only Admins!", show_alert=True)
        
    await db.delete_all_filters(query.message.chat.id)
    await query.message.edit("<b>♻️ Aʟʟ Fɪʟᴛᴇʀs Hᴀᴠᴇ Bᴇᴇɴ Cʟᴇᴀɴᴇᴅ!</b>")

# ==============================================================================
# 📑 LIST FILTERS
# ==============================================================================
@Client.on_message(filters.command("filters") & filters.group)
async def list_filters(client, message):
    filters_list = await db.get_filters(message.chat.id)
    
    if not filters_list:
        return await message.reply("<b>📂 Nᴏ Aᴄᴛɪᴠᴇ Fɪʟᴛᴇʀs ɪɴ ᴛʜɪs Gʀᴏᴜᴘ.</b>")
    
    text = f"<b>📑 <u>Sᴀᴠᴇᴅ Fɪʟᴛᴇʀs ({len(filters_list)})</u></b>\n\n"
    for f in filters_list:
        text += f"🔹 <code>{f}</code>\n"
    
    await message.reply(text)

# ==============================================================================
# 🤖 AUTO REPLY HANDLER (THE BRAIN)
# ==============================================================================
@Client.on_message(filters.group & filters.text & filters.incoming, group=1)
async def filter_check(client, message):
    if not message.text or message.text.startswith("/"):
        return
        
    name = message.text.lower().strip()
    
    # Check Database
    filter_data = await db.get_filter(message.chat.id, name)
    
    if filter_data:
        try:
            # 1. Variables Replacement
            text = filter_data.get('text') if filter_data['type'] == 'text' else filter_data.get('caption', '')
            final_text = replace_text(text, message)
            
            # 2. Check Special Flags ({del}, {admin})
            if "{admin}" in final_text and not await is_check_admin(client, message.chat.id, message.from_user.id):
                return # Ignore if not admin
                
            if "{del}" in final_text:
                final_text = final_text.replace("{del}", "")
                try: await message.delete() # Delete User Msg
                except: pass

            if "{admin}" in final_text:
                final_text = final_text.replace("{admin}", "")

            # 3. Parse Buttons
            keyboard, clean_text = parse_buttons(final_text)

            # 4. Send Response
            if filter_data['type'] == 'text':
                await message.reply(
                    clean_text, 
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            elif filter_data['type'] == 'media':
                await client.send_cached_media(
                    chat_id=message.chat.id,
                    file_id=filter_data['file_id'],
                    caption=clean_text,
                    reply_markup=keyboard
                )
            
            # 🛑 STOP PROPAGATION
            # Filter found -> Stop processing -> Don't search movie
            message.stop_propagation()
            
        except Exception as e:
            logger.error(f"Filter Error: {e}")
