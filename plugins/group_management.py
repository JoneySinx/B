import logging
import asyncio
from time import time
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions, CallbackQuery
from hydrogram.errors import FloodWait, MessageDeleteForbidden, RPCError, ListenerTimeout
from utils import is_check_admin, save_group_settings, temp, get_settings

logger = logging.getLogger(__name__)

# --- 🛠️ HELPER: GROUP SETTINGS BUTTONS (Re-defined here to fix ImportError) ---
# NOTE: This function was missing from commands.py, so we put the logic here.
async def get_grp_stg(group_id):
    settings = await get_settings(group_id)
    btn = [[
        InlineKeyboardButton('📝 Caption', callback_data=f'caption_setgs#{group_id}'),
        InlineKeyboardButton('👋 Welcome', callback_data=f'welcome_setgs#{group_id}')
    ],[
        InlineKeyboardButton(f'Spell Check {"✅" if settings["spell_check"] else "❌"}', callback_data=f'bool_setgs#spell_check#{settings.get("spell_check", True)}#{group_id}'),
        InlineKeyboardButton(f'Auto Delete {"✅" if settings.get("auto_delete", False) else "❌"}', callback_data=f'bool_setgs#auto_delete#{settings.get("auto_delete", False)}#{group_id}')
    ],[
        InlineKeyboardButton('🔙 Back to Manage', callback_data=f'mng_back_to_menu#{group_id}')
    ]]
    return btn

# ==============================================================================
# 🛡️ MANAGE PANEL (GOD DASHBOARD)
# ==============================================================================
@Client.on_message(filters.command('manage') & filters.group)
async def manage_panel(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id):
        return await message.reply("<b>❌ Access Denied! You are not an Admin.</b>")
        
    chat_id = message.chat.id
    
    btn = [
        [
            InlineKeyboardButton('🔇 Mute Chat', callback_data=f'mng_mute_all#{chat_id}'),
            InlineKeyboardButton('🔊 Unmute Chat', callback_data=f'mng_unmute_all#{chat_id}')
        ],
        [
            InlineKeyboardButton('🧹 Clean Menu', callback_data=f'mng_clean_menu#{chat_id}'),
            InlineKeyboardButton('🧟 Kick Zombies', callback_data=f'mng_kick_del#{chat_id}')
        ],
        [
            InlineKeyboardButton('⚙️ Group Settings', callback_data=f'open_group_settings#{chat_id}') # Passing ID
        ],
        [
            InlineKeyboardButton('❌ Close', callback_data='close_data')
        ]
    ]
    
    await message.reply_text(
        f"<b>🛡️ <u>GROUP COMMANDER</u></b>\n\n"
        f"<b>🏷️ Group:</b> {message.chat.title}\n"
        f"<b>🆔 ID:</b> <code>{chat_id}</code>\n"
        f"<b>👑 Commander:</b> {message.from_user.mention}\n\n"
        f"<i>Select an action to execute:</i>", 
        reply_markup=InlineKeyboardMarkup(btn)
    )

# ==============================================================================
# 🗑️ ULTRA PURGE (SELECTIVE & SMART)
# ==============================================================================
# Purge logic is fine, no changes needed here unless further optimization is requested.
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
            # Note: client.get_messages is not an async generator, use manual iteration or client.get_chat_history
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
            
    # 2. SELECTIVE PURGE (Arguments)
    if len(message.command) > 1:
        mode = message.command[1].lower()
        limit = 100 # Default check limit
        
        # Check for limit arg (e.g., /purge links 200)
        if len(message.command) > 2 and message.command[2].isdigit():
            limit = int(message.command[2])
            
        if mode.isdigit(): # /purge 50 (Delete last N messages)
            limit = int(mode)
            # Need to fetch messages in reverse order to delete last N
            msg_ids = [m.id async for m in client.get_chat_history(message.chat.id, limit=limit+1)]
            # We delete the command message as well, so +1
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
            
            if is_match: ids_to_del.append(msg.id)
            if len(ids_to_del) >= 100:
                try:
                    await client.delete_messages(message.chat.id, ids_to_del)
                    deleted += len(ids_to_del)
                    ids_to_del = []
                except: pass
                
        if ids_to_del:
            try:
                await client.delete_messages(message.chat.id, ids_to_del)
                deleted += len(ids_to_del)
            except: pass
            
        await sts.edit(f"<b>✅ Selective Purge Complete!</b>\n\n🗑️ Deleted: {deleted} {types_map[mode]}")
        await asyncio.sleep(5); await sts.delete()

# ==============================================================================
# 📌 ADVANCED PIN & UNPIN (No changes needed)
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
@Client.on_callback_query(filters.regex(r"^(mng_|clean_do|mng_back_to_menu|open_group_settings)"))
async def manage_callbacks(client, query: CallbackQuery):
    data = query.data
    
    if data.startswith("open_group_settings"):
        _, chat_id = data.split("#")
        chat_id = int(chat_id)
        if not await is_check_admin(client, chat_id, query.from_user.id): return await query.answer("🛑 Access Denied!", show_alert=True)
        
        btn = await get_grp_stg(chat_id)
        await query.message.edit_text(f"<b>⚙️ Group Settings for:</b> {query.message.chat.title}", reply_markup=InlineKeyboardMarkup(btn))
        return

    if data.startswith("mng_back_to_menu"):
        # This handles back navigation from settings menu
        _, chat_id = data.split("#")
        chat_id = int(chat_id)
        # Re-trigger the manage panel display logic (can be simplified by editing)
        
        # Simulating the main manage panel for back button
        btn = [
            [
                InlineKeyboardButton('🔇 Mute Chat', callback_data=f'mng_mute_all#{chat_id}'),
                InlineKeyboardButton('🔊 Unmute Chat', callback_data=f'mng_unmute_all#{chat_id}')
            ],
            [
                InlineKeyboardButton('🧹 Clean Menu', callback_data=f'mng_clean_menu#{chat_id}'),
                InlineKeyboardButton('🧟 Kick Zombies', callback_data=f'mng_kick_del#{chat_id}')
            ],
            [
                InlineKeyboardButton('⚙️ Group Settings', callback_data=f'open_group_settings#{chat_id}')
            ],
            [
                InlineKeyboardButton('❌ Close', callback_data='close_data')
            ]
        ]
        await query.message.edit_text(
            f"<b>🛡️ <u>GROUP COMMANDER</u></b>\n\n"
            f"<b>🏷️ Group:</b> {query.message.chat.title}\n"
            f"<i>Select an action to execute:</i>", 
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return

    # Handle all other mng_ actions
    if data.startswith("mng_") or data.startswith("clean_do"):
        try:
            # Try splitting mng_action#chat_id or clean_do#type#chat_id
            parts = data.split("#")
            action = parts[0] if data.startswith("mng_") else parts[1]
            chat_id = int(parts[-1])
        except:
            return await query.answer("❌ Invalid Callback Data.")

        if not await is_check_admin(client, chat_id, query.from_user.id):
            return await query.answer("🛑 Access Denied!", show_alert=True)

        # 1. UNMUTE/MUTE ALL
        if action == "unmute_all":
            # ... (Unmute logic remains same)
            await query.message.edit("<b>🔊 Unmuting Chat...</b>")
            try:
                await client.set_chat_permissions(chat_id, ChatPermissions(
                    can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True,
                    can_send_polls=True, can_add_web_page_previews=True, can_invite_users=True
                ))
                await query.message.edit("<b>✅ Chat Unmuted Successfully!</b>")
            except Exception as e: await query.message.edit(f"❌ Error: {e}")

        elif action == "mute_all":
            # ... (Mute logic remains same)
            await query.message.edit("<b>🔇 Muting Chat...</b>")
            try:
                await client.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
                await query.message.edit("<b>✅ Chat Muted Successfully!</b>")
            except Exception as e: await query.message.edit(f"❌ Error: {e}")

        # 2. ZOMBIE CLEANER
        elif action == "kick_del":
            # ... (Zombie cleaner logic remains same)
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
                [InlineKeyboardButton('🔙 Back', callback_data=f'mng_back_to_menu#{chat_id}')] # Corrected back button
            ]
            await query.message.edit(f"<b>🧹 Advanced Cleaner</b>\n\n<i>Select what to delete (Last 100 Msgs):</i>", reply_markup=InlineKeyboardMarkup(btn))
        
        # 4. PERFORM CLEAN (FROM BUTTON)
        elif action in ['links', 'photos', 'files', 'bots']:
            type_ = action
            limit = 100
            types_map = {'links': "🔗 Links", 'photos': "🖼️ Photos", 'files': "📂 Documents", 'bots': "🤖 Bot Messages"}
            
            await query.message.edit(f"<b>🧹 Cleaning {types_map[type_]}...</b>")
            
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
                    try:
                        await client.delete_messages(chat_id, ids_to_del)
                        deleted += len(ids_to_del)
                        ids_to_del = []
                    except: pass
            
            if ids_to_del:
                try:
                    await client.delete_messages(chat_id, ids_to_del)
                    deleted += len(ids_to_del)
                except: pass
                
            await query.message.edit(f"<b>✅ Cleaned {deleted} {types_map[type_]}!</b>")

# ==============================================================================
# ⚙️ LIVE SETTINGS EDITOR
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(caption_setgs|welcome_setgs|tutorial_setgs|bool_setgs)"))
async def settings_wizard(client, query):
    data = query.data
    
    if data.startswith("bool_setgs"):
        # Handles toggle buttons (Spell Check, Auto Delete)
        _, key, current_val, group_id = data.split("#")
        group_id = int(group_id)
        
        if not await is_check_admin(client, group_id, query.from_user.id): return await query.answer("🛑 Admin Only!", show_alert=True)
        
        new_val = current_val.lower() == 'false' # Toggle logic
        
        settings = await get_settings(group_id)
        settings[key] = new_val
        await save_group_settings(group_id, key, new_val)
        
        # Refresh menu
        btn = await get_grp_stg(group_id)
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btn))
        return

    action, group_id = data.split("#")
    group_id = int(group_id)
    if not await is_check_admin(client, group_id, query.from_user.id): return await query.answer("🛑 Admin Only!", show_alert=True)
    
    prompts = {
        "caption_setgs": ("caption", "📝 <b>Send new File Caption:</b>\n\nVars: `{file_name}`, `{file_size}`"),
        "welcome_setgs": ("welcome", "👋 <b>Send new Welcome Message:</b>\n\nVars: `{mention}`, `{title}`"),
        "tutorial_setgs": ("tutorial", "🎥 <b>Send new Tutorial Link:</b>")
    }
    
    if action not in prompts: return await query.answer("❌ Invalid Action.")

    db_key, text = prompts[action]
    await query.message.delete()
    
    ask = await client.send_message(query.message.chat.id, text)
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        
        if not msg or not msg.text:
            await client.send_message(query.message.chat.id, "❌ Invalid Input or Timeout.")
            return

        # Save the setting
        await save_group_settings(group_id, db_key, msg.text)
        
        # Display success and refresh settings menu
        ok = await client.send_message(query.message.chat.id, "<b>✅ Updated!</b>")
        await asyncio.sleep(2); await ok.delete()
        
        # Go back to settings menu after successful update
        btn = await get_grp_stg(group_id)
        await client.send_message(query.message.chat.id, f"<b>⚙️ Settings Updated!</b>", reply_markup=InlineKeyboardMarkup(btn))
        
    except ListenerTimeout: 
        await client.send_message(query.message.chat.id, "⏳ Timeout.")
        
    finally:
        try: await ask.delete()
        except: pass
