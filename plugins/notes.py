from hydrogram import Client, filters, enums
from database.users_chats_db import db
from utils import is_check_admin
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("save") & filters.group)
async def save_note(client, message):
    # Check Admin Permissions
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only Admins can save notes!")
    
    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply("Reply to a message with <code>/save name</code> to save it.")
    
    # Get Note Name
    try:
        name = message.text.split(None, 1)[1]
    except IndexError:
        return await message.reply("Please provide a name for the note.\nExample: <code>/save rules</code>")
    
    # Get Note Data (Text or Media)
    note_data = {}
    reply = message.reply_to_message
    
    if reply:
        if reply.text:
            note_data['type'] = 'text'
            note_data['text'] = reply.text
        elif reply.media:
            note_data['type'] = 'media'
            note_data['file_id'] = getattr(reply, reply.media.value).file_id
            note_data['media_type'] = str(reply.media.value)
            note_data['caption'] = reply.caption or ""
        else:
            return await message.reply("Unsupported message type!")
    else:
        # If not reply, treat as text note
        # This part handles "/save name Some text content" (future update if needed)
        return await message.reply("Please reply to a message to save it.")

    await db.save_note(message.chat.id, name, note_data)
    await message.reply(f"<b>✅ Note Saved:</b> <code>{name}</code>")


@Client.on_message(filters.command(["get", "note"]) & filters.group)
async def get_note(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/get name</code>")
    
    name = message.text.split(None, 1)[1]
    note = await db.get_note(message.chat.id, name)
    
    if not note:
        return await message.reply("No such note found!")
    
    if note['type'] == 'text':
        await message.reply(note['text'], disable_web_page_preview=True)
    elif note['type'] == 'media':
        await client.send_cached_media(
            chat_id=message.chat.id,
            file_id=note['file_id'],
            caption=note['caption']
        )


@Client.on_message(filters.command("notes") & filters.group)
async def list_notes(client, message):
    notes_cursor = await db.get_all_notes(message.chat.id)
    notes_list = []
    async for n in notes_cursor:
        notes_list.append(n['name'])
    
    if not notes_list:
        return await message.reply("No notes saved in this group.")
    
    text = "<b>📝 Saved Notes:</b>\n\n"
    for note in notes_list:
        text += f"• <code>{note}</code>\n"
    
    await message.reply(text)


@Client.on_message(filters.command(["delete", "clear"]) & filters.group)
async def delete_note(client, message):
    # Check Admin Permissions
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only Admins can delete notes!")
        
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/delete name</code>")
    
    name = message.text.split(None, 1)[1]
    
    if not await db.get_note(message.chat.id, name):
        return await message.reply("No such note found!")
        
    await db.delete_note(message.chat.id, name)
    await message.reply(f"<b>🗑 Note Deleted:</b> <code>{name}</code>")
