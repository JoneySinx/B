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
    if not text: return ""
    return text.format(
        first=message.from_user.first_name,
        last=message.from_user.last_name or "",
        fullname=message.from_user.first_name + (f" {message.from_user.last_name}" if message.from_user.last_name else ""),
        username=f"@{message.from_user.username}" if message.from_user.username else "No Username",
        mention=message.from_user.mention,
        id=message.from_user.id,
        chat_name=message.chat.title
    )

def parse_buttons(text):
    """
    Extracts buttons from text. Format: [Button Name](url)
    """
    buttons = []
    regex = r"\[([^\[]+?)\]\((.+?)\)"
    matches = re.findall(regex, text)
    if not matches: return None, text
    new_text = re.sub(regex, "", text).strip()
    for name, url in matches:
        if "://" in url or "t.me" in url:
            buttons.append([InlineKeyboardButton(name, url=url.strip())])
    return InlineKeyboardMarkup(buttons) if buttons else None, new_text

# ==============================================================================
# 💾 SAVE NOTE (/save)
# ==============================================================================
@Client.on_message(filters.command("save") & filters.group)
async def save_note(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Aᴄᴄᴇss Dᴇɴɪᴇᴅ!</b>\nOnly Admins can save notes.")

    # Logic to handle both reply and direct text
    # Case 1: Reply to message
    if message.reply_to_message:
        if len(message.command) < 2:
            return await message.reply("<b>⚠️ Usᴀɢᴇ:</b> Reply with <code>/save [name]</code>")
        name = message.text.split(None, 1)[1].strip().lower()
        reply = message.reply_to_message
        note_data = {}

        if reply.text:
            note_data['type'] = 'text'
            note_data['text'] = reply.text.markdown
        elif reply.media:
            note_data['type'] = 'media'
            media_obj = getattr(reply, reply.media.value)
            note_data['file_id'] = media_obj.file_id
            note_data['media_type'] = str(reply.media.value)
            note_data['caption'] = reply.caption.markdown if reply.caption else ""
        else:
            return await message.reply("<b>❌ Uɴsᴜᴘᴘᴏʀᴛᴇᴅ Mᴇssᴀɢᴇ Tʏᴘᴇ!</b>")
    
    # Case 2: Direct text (/save name content...)
    elif len(message.command) >= 3:
        name = message.command[1].strip().lower()
        content = message.text.split(None, 2)[2]
        note_data = {'type': 'text', 'text': content}
    else:
        return await message.reply(
            "<b>⚠️ Usᴀɢᴇ:</b>\n"
            "1. Reply: <code>/save rules</code>\n"
            "2. Text: <code>/save rules Don't spam!</code>\n\n"
            "<b>💡 Pro Tips:</b>\n"
            "• Use <code>{mention}</code> for user tagging.\n"
            "• Use <code>[Button](url)</code> for buttons.\n"
            "• Add <code>{del}</code> to delete user msg."
        )

    await db.save_note(message.chat.id, name, note_data)
    await message.reply(f"<b>✅ Nᴏᴛᴇ Sᴀᴠᴇᴅ!</b>\n\n<b>🔖 Nᴀᴍᴇ:</b> <code>{name}</code>\n<i>You can use it via #{name} or /get {name}</i>")

# ==============================================================================
# 📨 GET NOTE (/get or #note)
# ==============================================================================
@Client.on_message(filters.command("get") & filters.group)
async def get_note_cmd(client, message):
    if len(message.command) < 2: return
    name = message.text.split(None, 1)[1].strip().lower()
    await send_note(client, message, name)

@Client.on_message(filters.regex(r"^#\w+") & filters.group)
async def get_note_hashtag(client, message):
    name = message.text.replace("#", "").split()[0].strip().lower()
    await send_note(client, message, name)

async def send_note(client, message, name):
    note = await db.get_note(message.chat.id, name)
    if not note: return 

    # Smart Processing
    text = note.get('text', '') if note['type'] == 'text' else note.get('caption', '')
    
    # 1. Variables
    final_text = replace_text(text, message)
    
    # 2. Special Flags
    if "{admin}" in final_text and not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Admin Only Note!</b>", quote=True)
    
    if "{del}" in final_text:
        final_text = final_text.replace("{del}", "")
        try: await message.delete()
        except: pass
    
    final_text = final_text.replace("{admin}", "")
    
    # 3. Buttons
    keyboard, clean_text = parse_buttons(final_text)

    # 4. Send
    try:
        if note['type'] == 'text':
            await message.reply(clean_text, reply_markup=keyboard, disable_web_page_preview=True, parse_mode=enums.ParseMode.MARKDOWN)
        elif note['type'] == 'media':
            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=note['file_id'],
                caption=clean_text,
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Note Error: {e}")

# ==============================================================================
# 📝 LIST NOTES
# ==============================================================================
@Client.on_message(filters.command("notes") & filters.group)
async def list_notes(client, message):
    notes = await db.get_all_notes(message.chat.id)
    
    note_list = []
    async for n in notes:
        note_list.append(n['name'])
    
    if not note_list:
        return await message.reply("<b>📂 Nᴏ Nᴏᴛᴇs Fᴏᴜɴᴅ!</b>")
    
    text = f"<b>📝 <u>Sᴀᴠᴇᴅ Nᴏᴛᴇs ({len(note_list)})</u></b>\n\n"
    for name in note_list:
        text += f"• <code>#{name}</code>\n"
    
    await message.reply(text)

# ==============================================================================
# 🗑️ DELETE NOTE (/clear)
# ==============================================================================
@Client.on_message(filters.command(["delete", "clear"]) & filters.group)
async def delete_note(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Aᴅᴍɪɴ Oɴʟʏ!</b>")
        
    if len(message.command) < 2:
        return await message.reply("<b>⚠️ Usᴀɢᴇ:</b> <code>/clear name</code>")
    
    name = message.text.split(None, 1)[1].strip().lower()
    
    if await db.delete_note(message.chat.id, name):
        await message.reply(f"<b>🗑️ Nᴏᴛᴇ Dᴇʟᴇᴛᴇᴅ:</b> <code>{name}</code>")
    else:
        await message.reply("<b>❌ Nᴏᴛᴇ Nᴏᴛ Fᴏᴜɴᴅ!</b>")

# ==============================================================================
# ♻️ CLEAR ALL NOTES
# ==============================================================================
@Client.on_message(filters.command("clearall") & filters.group)
async def clear_all_notes(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>🛑 Aᴅᴍɪɴ Oɴʟʏ!</b>")
        
    btn = [[InlineKeyboardButton("✅ YES, DELETE ALL", callback_data="confirm_clearall_notes")], [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]]
    await message.reply("<b>⚠️ Are you sure you want to delete ALL notes?</b>", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex("confirm_clearall_notes"))
async def confirm_clearall(client, query):
    if not await is_check_admin(client, query.message.chat.id, query.from_user.id):
        return await query.answer("🛑 Only Admins!", show_alert=True)
        
    await db.delete_all_notes(query.message.chat.id)
    await query.message.edit("<b>♻️ Aʟʟ Nᴏᴛᴇs Hᴀᴠᴇ Bᴇᴇɴ Cʟᴇᴀɴᴇᴅ!</b>")
