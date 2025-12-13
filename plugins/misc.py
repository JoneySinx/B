import logging
import os
import io
import json
from hydrogram import Client, filters, enums
from hydrogram.types import Message
from info import ADMINS

logger = logging.getLogger(__name__)

# ==============================================================================
# 🆔 ID & MEDIA DETECTOR (ADVANCED)
# ==============================================================================
@Client.on_message(filters.command("id"))
async def show_id(client, message):
    """
    God Level ID: Detects Chat, User, Reply, Forward, AND Media/Sticker IDs.
    """
    chat = message.chat
    your_id = message.from_user.id if message.from_user else 0
    reply = message.reply_to_message

    # Header
    text = f"<b>🆔 <u>Iᴅᴇɴᴛɪᴛʏ Iɴᴛᴇʟʟɪɢᴇɴᴄᴇ</u></b>\n\n"
    
    # Chat Info
    text += f"<b>💬 Cʜᴀᴛ Iᴅ:</b> <code>{chat.id}</code>\n"
    text += f"<b>📛 Tʏᴘᴇ:</b> <code>{chat.type}</code>\n"
    if chat.username:
        text += f"<b>🔗 Uɴᴀᴍᴇ:</b> @{chat.username}\n"
    
    # User Info
    text += f"<b>👤 Yᴏᴜʀ Iᴅ:</b> <code>{your_id}</code>\n"

    # Reply Info
    if reply:
        text += f"\n<b>🔄 Rᴇᴘʟɪᴇᴅ Oʙᴊᴇᴄᴛ:</b>\n"
        text += f" • <b>👤 Usᴇʀ Iᴅ:</b> <code>{reply.from_user.id}</code>\n"
        if reply.forward_from_chat:
            text += f" • <b>⏩ Fᴡᴅ Cʜᴀɴɴᴇʟ:</b> <code>{reply.forward_from_chat.id}</code>\n"
        
        # 👑 GOD MODE: MEDIA ID DETECTION
        # Sticker, Photo, or File ID fetching for developers
        if reply.sticker:
            text += f" • <b>🎭 Sᴛɪᴄᴋᴇʀ Iᴅ:</b> <code>{reply.sticker.file_id}</code>\n"
        elif reply.photo:
            text += f" • <b>🖼️ Pʜᴏᴛᴏ Iᴅ:</b> <code>{reply.photo.file_id}</code>\n"
        elif reply.document:
            text += f" • <b>📂 Fɪʟᴇ Iᴅ:</b> <code>{reply.document.file_id}</code>\n"
            
    await message.reply(text, quote=True)

# ==============================================================================
# 🕵️ USER PROFILER (BIO & PIC FETCH)
# ==============================================================================
@Client.on_message(filters.command("info"))
async def show_info(client, message):
    """
    God Level Info: Fetches Bio, Profile Pic, Status & Premium Check.
    Usage: Reply or /info [UserID]
    """
    # 1. Determine Target
    if len(message.command) > 1:
        try:
            target = message.command[1]
            if target.startswith("@"): target = target[1:]
            user = await client.get_users(target)
        except Exception as e:
            return await message.reply(f"<b>❌ User Not Found!</b>\nError: {e}")
    elif message.reply_to_message:
        user = message.reply_to_message.from_user
    else:
        user = message.from_user

    if not user:
        return await message.reply("<b>❌ Could not identify user!</b>")

    # 2. Fetch Full Chat Details (For Bio & Photo)
    # get_users doesn't give Bio, get_chat does.
    try:
        full_user = await client.get_chat(user.id)
        bio = full_user.bio if full_user.bio else "No Bio Set"
        photo_id = full_user.photo.big_file_id if full_user.photo else None
    except:
        bio = "Unknown"
        photo_id = None

    # 3. Format Data
    username = f"@{user.username}" if user.username else "None"
    is_bot = "🤖 Yes" if user.is_bot else "👤 No"
    is_prem = "💎 Yes" if user.is_premium else "🆓 No"
    dc_id = f"{user.dc_id}" if user.dc_id else "Unknown"
    status = f"{user.status}".replace("UserStatus.", "").title() if user.status else "Offline"
    
    # 4. Advanced UI Text
    text = (
        f"<b>🪪 <u>Usᴇʀ Pʀᴏғɪʟᴇ Iɴsᴘᴇᴄᴛᴏʀ</u></b>\n\n"
        f"<b>🆔 Iᴅ:</b> <code>{user.id}</code>\n"
        f"<b>👤 Nᴀᴍᴇ:</b> {user.mention}\n"
        f"<b>📛 Usᴇʀɴᴀᴍᴇ:</b> {username}\n\n"
        f"<b>💎 Pʀᴇᴍɪᴜᴍ:</b> {is_prem}\n"
        f"<b>🤖 Is Bᴏᴛ:</b> {is_bot}\n"
        f"<b>🌐 Dᴀᴛᴀ Cᴇɴᴛᴇʀ:</b> DC {dc_id}\n"
        f"<b>💤 Sᴛᴀᴛᴜs:</b> {status}\n\n"
        f"<b>📝 Bɪᴏ:</b>\n<code>{bio}</code>"
    )

    # 5. Send (With Photo if available)
    if photo_id:
        await message.reply_photo(photo_id, caption=text, quote=True)
    else:
        await message.reply(text, quote=True, disable_web_page_preview=True)

# ==============================================================================
# ⚙️ SMART JSON DUMPER
# ==============================================================================
@Client.on_message(filters.command("json") & filters.user(ADMINS))
async def show_json(client, message):
    """
    Dump raw update. Auto-converts to file if too long.
    """
    target_msg = message.reply_to_message or message
    
    # Convert object to string
    json_data = str(target_msg)
    
    # 👑 GOD MODE: LIMIT HANDLER
    if len(json_data) > 4000:
        # Save to memory file
        bio = io.BytesIO(json_data.encode('utf-8'))
        bio.name = "message_update.json"
        
        await message.reply_document(
            document=bio,
            caption=f"<b>⚙️ JSON Too Large!</b>\n\nSent as file.",
            quote=True
        )
    else:
        await message.reply(
            f"<b>⚙️ <u>Rᴀᴡ Mᴇssᴀɢᴇ Dᴀᴛᴀ</u></b>\n\n<code>{json_data}</code>",
            quote=True
        )

# ==============================================================================
# 📜 SYSTEM LOGS (NEW FEATURE)
# ==============================================================================
@Client.on_message(filters.command("logs") & filters.user(ADMINS))
async def get_logs(client, message):
    """
    Instantly sends the log file to Admin.
    """
    log_file = "log.txt" # Ensure your logging config saves to this file
    
    if os.path.exists(log_file):
        await message.reply_document(
            document=log_file,
            caption="<b>📜 System Logs</b>\n\n<i>Here is the internal brain activity of your bot.</i>",
            quote=True
        )
    else:
        await message.reply("<b>❌ No Log File Found!</b>", quote=True)
