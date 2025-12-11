import os
import time
import asyncio
import logging
import datetime
from hydrogram import Client, filters
from hydrogram.errors import FloodWait
from database.users_chats_db import db
from info import ADMINS
from utils import broadcast_messages, groups_broadcast_messages, temp, get_readable_time

logger = logging.getLogger(__name__)

# --- 📢 BROADCAST COMMAND ---
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def broadcast_handler(bot, message):
    """
    Broadcasts a message to Users or Groups.
    Usage: Reply to a message with /broadcast users OR /broadcast groups
    """
    try:
        mode = message.command[1].lower()
    except IndexError:
        return await message.reply("<b>❌ Usage:</b>\nReply to a message with:\n<code>/broadcast users</code>\n<code>/broadcast groups</code>")

    if mode not in ["users", "groups"]:
        return await message.reply("<b>❌ Invalid Mode!</b> Use <code>users</code> or <code>groups</code>.")

    sts = await message.reply(f"<b>🚀 Starting Broadcast to {mode.capitalize()}...</b>")
    
    start_time = time.time()
    done = 0
    failed = 0
    success = 0
    
    # Get Target List
    if mode == "users":
        total_targets = await db.total_users_count()
        target_list = await db.get_all_users()
    else:
        total_targets = await db.total_chat_count()
        target_list = await db.get_all_chats()

    if total_targets == 0:
        return await sts.edit("<b>❌ No targets found in database.</b>")

    # Broadcast Loop
    async for target in target_list:
        try:
            # Send Message
            if mode == "users":
                status, msg = await broadcast_messages(target['_id'], message.reply_to_message)
            else:
                status, msg = await groups_broadcast_messages(target['id'], message.reply_to_message)
            
            if status:
                success += 1
            else:
                failed += 1
                
            done += 1
            
            # Update Progress every 20 users
            if done % 20 == 0:
                # Calculate ETA
                elapsed = time.time() - start_time
                speed = done / elapsed if elapsed > 0 else 1
                eta = get_readable_time((total_targets - done) / speed)
                percentage = (done / total_targets) * 100
                
                # Progress Bar UI
                filled = int(done * 10 / total_targets)
                bar = "■" * filled + "□" * (10 - filled)
                
                await sts.edit(
                    f"<b>📢 Broadcast in Progress...</b>\n\n"
                    f"{bar} <b>{percentage:.2f}%</b>\n\n"
                    f"<b>✅ Success:</b> {success}\n"
                    f"<b>❌ Failed:</b> {failed}\n"
                    f"<b>📂 Total:</b> {total_targets}\n"
                    f"<b>⏳ ETA:</b> {eta}"
                )
                
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

    time_taken = get_readable_time(time.time() - start_time)
    await sts.edit(
        f"<b>✅ Broadcast Completed!</b>\n\n"
        f"<b>⏱️ Time Taken:</b> {time_taken}\n"
        f"<b>👥 Total Targets:</b> {total_targets}\n"
        f"<b>✅ Success:</b> {success}\n"
        f"<b>❌ Failed:</b> {failed}"
    )
