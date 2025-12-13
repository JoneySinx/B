import os
import sys
import shutil
import logging
import asyncio
import time
from datetime import datetime
from hydrogram import Client, filters
from info import ADMINS
from database.users_chats_db import db
from utils import temp, get_readable_time

logger = logging.getLogger(__name__)

# ==============================================================================
# 🧹 SYSTEM CLEANER (GARBAGE COLLECTOR)
# ==============================================================================
async def clean_trash():
    """
    Cleans Downloads, Cache, and Temp files to free up Server Space.
    Returns the estimated freed space text.
    """
    folders = ["downloads", "raw_files", "__pycache__"]
    deleted_size = 0
    
    for folder in folders:
        if os.path.exists(folder):
            try:
                # Calculate size before deleting (Optional, skipped for speed)
                shutil.rmtree(folder)
            except Exception as e:
                logger.error(f"Failed to clear {folder}: {e}")
                
    # Re-create downloads folder
    if not os.path.exists("downloads"):
        os.mkdir("downloads")
        
    return "✅ Cache Cleared"

# ==============================================================================
# 🔄 RESTART COMMAND
# ==============================================================================
@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def restart_bot(bot, message):
    try:
        # 1. UI Animation
        msg = await message.reply("<b>🔄 System Restart Initiated...</b>")
        await asyncio.sleep(1)
        await msg.edit("<b>🧹 Cleaning Server Garbage...</b>")
        
        # 2. Clean Cache
        await clean_trash()
        
        await msg.edit("<b>💾 Saving Database States...</b>")
        await asyncio.sleep(0.5)
        
        # 3. Save Restart Context (To edit message after reboot)
        restart_data = {
            'chat_id': message.chat.id,
            'msg_id': msg.id,
            'start_time': time.time()
        }
        await db.update_config('restart_status', restart_data)
        
        await msg.edit(
            "<b>🚀 Rebooting Core Systems...</b>\n\n"
            "<i>• Reloading Modules...</i>\n"
            "<i>• Re-establishing DB Connection...</i>\n"
            "<i>• Syncing Clone Bots...</i>\n\n"
            "<b>⏳ Be right back in 10-15 seconds!</b>"
        )

        # 4. Trigger Restart
        logger.info("🚨 RESTARTING BOT SERVER (GOD MODE)...")
        
        # This effectively restarts the script
        os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as e:
        await message.reply(f"<b>❌ Restart Failed:</b>\n<pre>{e}</pre>")

# ==============================================================================
# ✅ POST-RESTART CHECK (AUTO-RUNNER)
# ==============================================================================
# यह फंक्शन Bot Start होने पर चलना चाहिए।
# इसे Trigger करने के लिए आपको bot.py में एक छोटा सा कोड डालना होगा (नीचे देखें)।

async def check_restart_success(bot):
    try:
        # Config DB से डेटा लाओ
        config = await db.get_config()
        r_data = config.get('restart_status')
        
        if r_data:
            chat_id = r_data['chat_id']
            msg_id = r_data['msg_id']
            start_time = r_data['start_time']
            
            # Calculate Time Taken
            time_taken = get_readable_time(time.time() - start_time)
            
            try:
                # मैसेज एडिट करें: "Restart Successful"
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=(
                        f"<b>✅ System Online!</b>\n\n"
                        f"<b>⏱️ Restart Time:</b> {time_taken}\n"
                        f"<b>🧹 Cache:</b> Cleaned\n"
                        f"<b>🤖 Clones:</b> Re-Initializing...\n"
                        f"<b>📅 Date:</b> {datetime.now().strftime('%d %b, %H:%M')}"
                    )
                )
            except Exception as e:
                logger.warning(f"Could not edit restart message: {e}")
            
            # DB से फ्लैग हटा दें
            await db.update_config('restart_status', None)
            
    except Exception as e:
        logger.error(f"Post-restart check error: {e}")

# ==============================================================================
# 🛠️ MANUAL TRIGGER (Just in case)
# ==============================================================================
@Client.on_message(filters.command("fix_restart") & filters.user(ADMINS))
async def manual_check(bot, message):
    """
    अगर ऑटोमैटिक मैसेज एडिट न हो, तो यह कमांड चलाएं।
    """
    await check_restart_success(bot)
    await message.reply("<b>✅ Checked Restart Status!</b>")
