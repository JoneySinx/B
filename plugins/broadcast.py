import time
import asyncio
import logging
import datetime
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from database.users_chats_db import db
from info import ADMINS
from utils import temp, get_readable_time

logger = logging.getLogger(__name__)

# --- 🎨 PROGRESS BAR STYLE ---
def get_progress_bar_string(current, total):
    filled_symbol = "■"
    empty_symbol = "□"
    completed = int(current * 10 / total)
    remainder = 10 - completed
    return filled_symbol * completed + empty_symbol * remainder

# --- 📢 BROADCAST COMMAND (ENTRY POINT) ---
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_command(bot, message):
    # 1. Save Message temporarily
    temp.BROADCAST_MSG = message.reply_to_message
    
    # 2. Default Settings
    if not hasattr(temp, 'BROADCAST_SETTINGS'):
        temp.BROADCAST_SETTINGS = {
            'mode': 'copy',       # copy / forward
            'target': 'users',    # users / groups / premium / free
            'pin': False,         # True / False
            'notification': True  # True (Loud) / False (Silent)
        }
    
    # 3. Open Control Panel
    await open_broadcast_panel(message)

# --- 🎛️ CONTROL PANEL UI ---
async def open_broadcast_panel(message, is_edit=False):
    s = temp.BROADCAST_SETTINGS
    
    # Status Icons
    mode_icon = "📝 Copy" if s['mode'] == 'copy' else "⏩ Forward"
    pin_icon = "📌 Pin: ON" if s['pin'] else "📌 Pin: OFF"
    notif_icon = "🔔 Loud" if s['notification'] else "🔕 Silent"
    
    # Target Text
    targets = {
        'users': '👤 All Users',
        'groups': '👥 All Groups',
        'premium': '💎 Premium Users',
        'free': '🆓 Free Users'
    }
    target_txt = targets.get(s['target'], 'Unknown')

    text = (
        f"<b>📢 <u>BROADCAST STUDIO</u></b>\n\n"
        f"<b>🎯 Target:</b> {target_txt}\n"
        f"<b>⚙️ Mode:</b> {mode_icon}\n"
        f"<b>📌 Options:</b> {pin_icon} | {notif_icon}\n\n"
        f"<i>Configure settings and click Start.</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton(f"Target: {target_txt}", callback_data="bc_cycle_target"),
            InlineKeyboardButton(f"Mode: {mode_icon}", callback_data="bc_toggle_mode")
        ],
        [
            InlineKeyboardButton(pin_icon, callback_data="bc_toggle_pin"),
            InlineKeyboardButton(notif_icon, callback_data="bc_toggle_notif")
        ],
        [
            InlineKeyboardButton("🚀 START BROADCAST", callback_data="bc_start"),
            InlineKeyboardButton("❌ Cancel", callback_data="close_data")
        ]
    ]
    
    if is_edit:
        await message.edit(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- 🖱️ CALLBACK HANDLER ---
@Client.on_callback_query(filters.regex(r^bc_'))
async def broadcast_callbacks(bot, query):
    data = query.data
    s = temp.BROADCAST_SETTINGS
    
    if data == "bc_cycle_target":
        modes = ['users', 'groups', 'premium', 'free']
        current_index = modes.index(s['target'])
        next_index = (current_index + 1) % len(modes)
        s['target'] = modes[next_index]
        await open_broadcast_panel(query.message, is_edit=True)
        
    elif data == "bc_toggle_mode":
        s['mode'] = 'forward' if s['mode'] == 'copy' else 'copy'
        await open_broadcast_panel(query.message, is_edit=True)
        
    elif data == "bc_toggle_pin":
        s['pin'] = not s['pin']
        await open_broadcast_panel(query.message, is_edit=True)
        
    elif data == "bc_toggle_notif":
        s['notification'] = not s['notification']
        await open_broadcast_panel(query.message, is_edit=True)
        
    elif data == "bc_start":
        await start_broadcast_engine(bot, query)

# --- 🚀 BROADCAST ENGINE (CORE LOGIC) ---
async def start_broadcast_engine(bot, query):
    s = temp.BROADCAST_SETTINGS
    msg = temp.BROADCAST_MSG
    
    if not msg:
        return await query.answer("❌ Message expired! Please reply again.", show_alert=True)
        
    await query.message.edit(f"<b>🔄 Fetching Target Database ({s['target']})...</b>")
    
    # 1. Fetch Targets
    cursor = None
    if s['target'] == 'users':
        cursor = await db.get_all_users()
    elif s['target'] == 'groups':
        cursor = await db.get_all_chats()
    elif s['target'] == 'premium':
        cursor = await db.get_premium_users() # Ensure this function exists in users_chats_db
    elif s['target'] == 'free':
        # Logic for free users (All - Premium) is complex in NoSQL, 
        # for safety usually we iterate all and check locally or use a specific query if available.
        # For now, using all users and filtering in loop for robustness
        cursor = await db.get_all_users()

    # Convert cursor to list (for count) or use count logic
    # Note: For huge DBs, converting to list is slow. We will use iterator.
    total_targets = await db.total_users_count() if 'users' in s['target'] else await db.total_chat_count()
    
    if total_targets == 0:
        return await query.message.edit("<b>❌ No targets found!</b>")

    # 2. Initialize Stats
    start_time = time.time()
    done, success, failed, blocked, deleted = 0, 0, 0, 0, 0
    temp.CANCEL_BROADCAST = False
    
    await query.message.edit(f"<b>🚀 Broadcast Started!</b>\nTarget: {s['target'].upper()}\nTotal: ~{total_targets}")
    
    # 3. The Loop
    async for target in cursor:
        if temp.CANCEL_BROADCAST:
            break
            
        # Determine ID
        chat_id = target.get('id') or target.get('_id')
        if not chat_id: continue

        # Filter for Free/Premium inside loop (Safe Fallback)
        if s['target'] == 'free':
            from utils import is_premium
            if await is_premium(chat_id, bot): continue
        
        try:
            # Send Logic
            sent_msg = None
            if s['mode'] == 'copy':
                sent_msg = await msg.copy(chat_id, disable_notification=not s['notification'])
            else:
                sent_msg = await msg.forward(chat_id, disable_notification=not s['notification'])
            
            # Pin Logic
            if s['pin'] and sent_msg:
                try: await sent_msg.pin(disable_notification=not s['notification'])
                except: pass
            
            success += 1
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
            # Retry once
            try:
                if s['mode'] == 'copy': await msg.copy(chat_id)
                else: await msg.forward(chat_id)
                success += 1
            except: failed += 1
            
        except InputUserDeactivated:
            deleted += 1
            await db.delete_user(chat_id) # Cleanup
        except UserIsBlocked:
            blocked += 1
            # Optional: await db.delete_user(chat_id)
        except PeerIdInvalid:
            failed += 1
        except Exception as e:
            failed += 1
            # logger.error(f"Broadcast Error: {e}")
            
        done += 1
        
        # 4. Progress Update UI (Every 20 users)
        if done % 20 == 0:
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 1
            eta = get_readable_time((total_targets - done) / speed)
            percentage = (done / total_targets) * 100 if total_targets > 0 else 0
            prog_bar = get_progress_bar_string(done, total_targets)
            
            btn = [[InlineKeyboardButton("⛔ STOP BROADCAST", callback_data="bc_cancel")]]
            
            try:
                await query.message.edit(
                    f"<b>📢 Broadcasting ({s['mode'].upper()})...</b>\n\n"
                    f"{prog_bar} <b>{percentage:.2f}%</b>\n\n"
                    f"<b>✅ Sent:</b> {success}\n"
                    f"<b>🚫 Blocked:</b> {blocked}\n"
                    f"<b>🗑️ Deleted:</b> {deleted}\n"
                    f"<b>⏳ ETA:</b> {eta}",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
            except: pass

    # 5. Final Report
    time_taken = get_readable_time(time.time() - start_time)
    await query.message.edit(
        f"<b>✅ Broadcast Completed!</b>\n\n"
        f"<b>🎯 Target:</b> {s['target'].upper()}\n"
        f"<b>⏱️ Time:</b> {time_taken}\n"
        f"<b>👥 Total Processed:</b> {done}\n"
        f"<b>✅ Success:</b> {success}\n"
        f"<b>🚫 Blocked:</b> {blocked}\n"
        f"<b>🗑️ Deleted Accounts:</b> {deleted}"
    )

@Client.on_callback_query(filters.regex(r^bc_cancel'))
async def cancel_broadcast(bot, query):
    temp.CANCEL_BROADCAST = True
    await query.answer("🛑 Stopping Broadcast...", show_alert=True)
