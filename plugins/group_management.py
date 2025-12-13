import logging
import asyncio
from time import time
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions
from hydrogram.errors import FloodWait, MessageDeleteForbidden, RPCError
from utils import is_check_admin, save_group_settings, temp, get_settings
from plugins.commands import get_grp_stg

logger = logging.getLogger(__name__)

# ==============================================================================
# 🛡️ MANAGE PANEL (GOD DASHBOARD)
# ==============================================================================
@Client.on_message(filters.command('manage') & filters.group)
async def manage_panel(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>❌ Access Denied! You are not an Admin.</b>")
        
    btn = [
        [
            InlineKeyboardButton('🔇 Mute Chat', callback_data=f'mng_mute_all#{message.chat.id}'),
            InlineKeyboardButton('🔊 Unmute Chat', callback_data=f'mng_unmute_all#{message.chat.id}')
        ],
        [
            InlineKeyboardButton('🧹 Clean Menu', callback_data=f'mng_clean_menu#{message.chat.id}'), # NEW MENU
            InlineKeyboardButton('🧟 Kick Zombies', callback_data=f'mng_kick_del#{message.chat.id}')
        ],
        [
            InlineKeyboardButton('⚙️ Group Settings', callback_data='open_group_settings')
        ],
        [
            InlineKeyboardButton('❌ Close', callback_data='close_data')
        ]
    ]
    
    await message.reply_text(
        f"<b>🛡️ <u>GROUP COMMANDER</u></b>\n\n"
        f"<b>🏷️ Group:</b> {message.chat.title}\n"
        f"<b>🆔 ID:</b> <code>{message.chat.id}</code>\n"
        f"<b>👑 Commander:</b> {message.from_user.mention}\n\n"
        f"<i>Select an action to execute:</i>", 
        reply_markup=InlineKeyboardMarkup(btn)
    )

# ==============================================================================
# 🗑️ ULTRA PURGE (SELECTIVE & SMART)
# ==============================================================================
@Client.on_message(filters.command("purge") & filters.group)
async def purge_func(client, message):
    """
    God Mode Purge: Handles Reply, Count, Links, Photos, Files, Bots, Users.
    """
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return

    # 1. TARGETED USER PURGE (Reply to User)
    if message.reply_to_message:
        # If no args, do standard purge from that message down
        if len(message.command) == 1:
            msg = await message.reply("<b>🗑️ Purging Started...</b>")
            message_ids = []
            count = 0
            for msg_id in range(message.reply_to_message.id, message.id + 1):
                message_ids.append(msg_id)
                if len(message_ids) == 100:
                    try:
                        await client.delete_messages(message.chat.id, message_ids)
                        count += len(message_ids)
                        message_ids = []
                    except: pass
            if message_ids:
                try: await client.delete_messages(message.chat.id, message_ids)
                except: pass
            await msg.edit(f"<b>✅ Purged {count} Messages!</b>")
            await asyncio.sleep(3); await msg.delete()
            return
            
        # If args present (e.g. /purge user), perform specific logic if needed
        # For now, sticking to standard reply purge as default behavior for reply

    # 2. SELECTIVE PURGE (Arguments)
    if len(message.command) > 1:
        mode = message.command[1].lower()
        limit = 100 # Default check limit
        
        # Check for limit arg (e.g., /purge links 200)
        if len(message.command) > 2 and message.command[2].isdigit():
            limit = int(message.command[2])
            
        if mode.isdigit(): # /purge 50 (Delete last N messages)
            limit = int(mode)
            msg_ids = [m.id async for m in client.get_chat_history(message.chat.id, limit=limit)]
            await client.delete_messages(message.chat.id, msg_ids)
            sent = await message.reply(f"<b>✅ Deleted last {limit} messages.</b>")
            await asyncio.sleep(3); await sent.delete()
            return

        # SELECTIVE MODES
        types_map = {
            'links': "🔗 Links",
            'photos': "🖼️ Photos",
            'files': "📂 Documents",
            'videos': "🎞️ Videos",
            'audios': "🎵 Audios",
            'bots': "🤖 Bot Messages",
            'service': "🔔 Service Msgs (Joins/Pins)"
        }
        
        if mode not in types_map:
            return await message.reply(f"<b>⚠️ Unknown Type!</b>\nAvailable: `links`, `photos`, `files`, `videos`, `bots`, `service`\n\nEx: `/purge links 100`")

        sts = await message.reply(f"<b>🔍 Scanning last {limit} messages for {types_map[mode]}...</b>")
        deleted = 0
        ids_to_del = []
        
        async for msg in client.get_chat_history(message.chat.id, limit=limit):
            is_match = False
            
            if mode == 'links' and (msg.text or msg.caption):
                if any(x in (msg.text or msg.caption) for x in ['http', 't.me', 'www.']): is_match = True
                if msg.entities: # Check for text links
                    for ent in msg.entities:
                        if ent.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]: is_match = True

            elif mode == 'photos' and msg.photo: is_match = True
            elif mode == 'files' and msg.document: is_match = True
            elif mode == 'videos' and msg.video: is_match = True
            elif mode == 'audios' and (msg.audio or msg.voice): is_match = True
            elif mode == 'bots' and msg.from_user and msg.from_user.is_bot: is_match = True
            elif mode == 'service' and msg.service: is_match = True # User joined, Pinned, etc.
            
            if is_match:
                ids_to_del.append(msg.id)
                
            if len(ids_to_del) >= 100:
                await client.delete_messages(message.chat.id, ids_to_del)
                deleted += len(ids_to_del)
                ids_to_del = []
                
        if ids_to_del:
            await client.delete_messages(message.chat.id, ids_to_del)
            deleted += len(ids_to_del)
            
        await sts.edit(f"<b>✅ Selective Purge Complete!</b>\n\n🗑️ Deleted: {deleted} {types_map[mode]}")
        await asyncio.sleep(5); await sts.delete()

# ==============================================================================
# 📌 ADVANCED PIN
# ==============================================================================
@Client.on_message(filters.command("pin") & filters.group)
async def pin_func(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return await message.reply("<b>Reply to a message to Pin it.</b>")
    
    loud = len(message.command) > 1 and message.command[1].lower() == "loud"
    try:
        await message.reply_to_message.pin(disable_notification=not loud)
        txt = "<b>🔔 Message Pinned (Loud)!</b>" if loud else "<b>📌 Message Pinned (Silent).</b>"
        await message.reply(txt)
    except Exception as e: await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.command("unpin") & filters.group)
async def unpin_func(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return
    try:
        await message.reply_to_message.unpin()
        await message.reply("<b>✅ Message Unpinned.</b>")
    except: pass

# ==============================================================================
# 🔊 ACTION CALLBACKS (THE ENGINE)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mng_"))
async def manage_callbacks(client, query):
    _, action, chat_id = query.data.split("#")
    chat_id = int(chat_id)
    
    if not await is_check_admin(client, chat_id, query.from_user.id):
        return await query.answer("🛑 Access Denied!", show_alert=True)

    # 1. UNMUTE/MUTE ALL
    if action == "unmute_all":
        await query.message.edit("<b>🔊 Unmuting Chat...</b>")
        try:
            await client.set_chat_permissions(chat_id, ChatPermissions(
                can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True,
                can_send_polls=True, can_add_web_page_previews=True, can_invite_users=True
            ))
            await query.message.edit("<b>✅ Chat Unmuted Successfully!</b>")
        except Exception as e: await query.message.edit(f"❌ Error: {e}")

    elif action == "mute_all":
        await query.message.edit("<b>🔇 Muting Chat...</b>")
        try:
            await client.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
            await query.message.edit("<b>✅ Chat Muted Successfully!</b>")
        except Exception as e: await query.message.edit(f"❌ Error: {e}")

    # 2. ZOMBIE CLEANER
    elif action == "kick_del":
        await query.message.edit("<b>🧟 Scanning for Zombies...</b>")
        kicked = 0
        try:
            async for member in client.get_chat_members(chat_id):
                if member.user.is_deleted:
                    try:
                        await client.ban_chat_member(chat_id, member.user.id)
                        await client.unban_chat_member(chat_id, member.user.id)
                        kicked += 1
                        await asyncio.sleep(0.1)
                    except: pass
            await query.message.edit(f"<b>✅ Cleanup Complete!</b>\n\n🧟 Removed: {kicked} Zombies.")
        except Exception as e: await query.message.edit(f"❌ Error: {e}")

    # 3. CLEANER MENU (NEW) 🧹
    elif action == "clean_menu":
        btn = [
            [InlineKeyboardButton('🔗 Links', callback_data=f'clean_do#links#{chat_id}'), InlineKeyboardButton('🖼️ Photos', callback_data=f'clean_do#photos#{chat_id}')],
            [InlineKeyboardButton('📂 Documents', callback_data=f'clean_do#files#{chat_id}'), InlineKeyboardButton('🤖 Bots', callback_data=f'clean_do#bots#{chat_id}')],
            [InlineKeyboardButton('🔙 Back', callback_data=f'mng_back#{chat_id}')]
        ]
        await query.message.edit(f"<b>🧹 Advanced Cleaner</b>\n\n<i>Select what to delete (Last 100 Msgs):</i>", reply_markup=InlineKeyboardMarkup(btn))
    
    elif action == "back":
        # Re-open main menu logic (simplified)
        await query.message.delete()
        # Trigger /manage command virtually if needed or just show basics
        # Keeping it simple by just deleting. User can type /manage again.

    # 4. PERFORM CLEAN (FROM BUTTON)
    elif query.data.startswith("clean_do"):
        _, type_, chat_id = query.data.split("#")
        chat_id = int(chat_id)
        limit = 100
        
        await query.message.edit(f"<b>🧹 Cleaning {type_.upper()}...</b>")
        
        deleted = 0
        ids_to_del = []
        
        async for msg in client.get_chat_history(chat_id, limit=limit):
            is_match = False
            if type_ == 'links' and (msg.text or msg.caption):
                if any(x in (msg.text or msg.caption) for x in ['http', 't.me', 'www.']): is_match = True
            elif type_ == 'photos' and msg.photo: is_match = True
            elif type_ == 'files' and msg.document: is_match = True
            elif type_ == 'bots' and msg.from_user and msg.from_user.is_bot: is_match = True
            
            if is_match: ids_to_del.append(msg.id)
            
            if len(ids_to_del) >= 100:
                await client.delete_messages(chat_id, ids_to_del)
                deleted += len(ids_to_del)
                ids_to_del = []
        
        if ids_to_del:
            await client.delete_messages(chat_id, ids_to_del)
            deleted += len(ids_to_del)
            
        await query.message.edit(f"<b>✅ Cleaned {deleted} {type_}!</b>")

# ==============================================================================
# ⚙️ LIVE SETTINGS EDITOR
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(caption_setgs|welcome_setgs|tutorial_setgs)"))
async def settings_wizard(client, query):
    action, group_id = query.data.split("#")
    group_id = int(group_id)
    if not await is_check_admin(client, group_id, query.from_user.id): return await query.answer("🛑 Admin Only!", show_alert=True)
    
    prompts = {
        "caption_setgs": ("caption", "📝 <b>Send new File Caption:</b>\n\nVars: `{file_name}`, `{file_size}`"),
        "welcome_setgs": ("welcome", "👋 <b>Send new Welcome Message:</b>\n\nVars: `{mention}`, `{title}`"),
        "tutorial_setgs": ("tutorial", "🎥 <b>Send new Tutorial Link:</b>")
    }
    db_key, text = prompts[action]
    await query.message.delete()
    
    ask = await client.send_message(query.message.chat.id, text)
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            await save_group_settings(group_id, db_key, msg.text)
            ok = await client.send_message(query.message.chat.id, "<b>✅ Updated!</b>")
            await asyncio.sleep(2); await ok.delete()
        else: await client.send_message(query.message.chat.id, "❌ Invalid Input.")
    except: await client.send_message(query.message.chat.id, "⏳ Timeout.")
    finally:
        try: await ask.delete()
        except: pass
