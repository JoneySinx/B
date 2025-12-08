import re
from hydrogram import Client, filters
from database.users_chats_db import db
from utils import is_check_admin

@Client.on_message(filters.command("filter") & filters.group)
async def add_filter(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only Admins can save filters!")
    
    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply("Reply to a message with <code>/filter name</code> to save it.")
    
    try:
        name = message.text.split(None, 1)[1]
    except IndexError:
        return await message.reply("Please provide a name for the filter.\nExample: <code>/filter rules</code>")
    
    reply = message.reply_to_message
    filter_data = {}
    
    if reply:
        if reply.text:
            filter_data['type'] = 'text'
            filter_data['text'] = reply.text
        elif reply.media:
            filter_data['type'] = 'media'
            filter_data['file_id'] = getattr(reply, reply.media.value).file_id
            filter_data['media_type'] = str(reply.media.value)
            filter_data['caption'] = reply.caption or ""
        else:
            return await message.reply("Unsupported message type!")
    else:
        return await message.reply("Please reply to a message to save it.")

    await db.add_filter(message.chat.id, name, filter_data)
    await message.reply(f"<b>✅ Filter Saved:</b> <code>{name}</code>")

@Client.on_message(filters.command(["stop", "stopall"]) & filters.group)
async def stop_filter(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("Only Admins can delete filters!")
        
    if len(message.command) < 2:
        return await message.reply("Usage: <code>/stop name</code>")
    
    name = message.text.split(None, 1)[1]
    
    await db.delete_filter(message.chat.id, name)
    await message.reply(f"<b>🗑 Filter Deleted:</b> <code>{name}</code>")

@Client.on_message(filters.command("filters") & filters.group)
async def list_filters(client, message):
    filters_cursor = await db.get_all_filters(message.chat.id)
    filters_list = []
    async for f in filters_cursor:
        filters_list.append(f['name'])
    
    if not filters_list:
        return await message.reply("No filters saved in this group.")
    
    text = "<b>📝 Saved Filters:</b>\n\n"
    for f in filters_list:
        text += f"• <code>{f}</code>\n"
    
    await message.reply(text)

# --- AUTO REPLY HANDLER ---
# यह ग्रुप के हर मैसेज को चेक करेगा (Priority Group=1 ताकि मूवी सर्च से पहले चेक हो)
@Client.on_message(filters.group & filters.text & filters.incoming, group=1)
async def filter_check(client, message):
    if not message.text:
        return
        
    name = message.text.lower().strip()
    # Check if this text matches any saved filter
    filter_data = await db.get_filter(message.chat.id, name)
    
    if filter_data:
        if filter_data['type'] == 'text':
            await message.reply(filter_data['text'], disable_web_page_preview=True)
        elif filter_data['type'] == 'media':
            await client.send_cached_media(
                chat_id=message.chat.id,
                file_id=filter_data['file_id'],
                caption=filter_data['caption']
            )
        # अगर फिल्टर मिल गया, तो आगे Movie Search को रोक दो
        message.stop_propagation()
