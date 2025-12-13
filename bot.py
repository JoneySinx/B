import sys
import glob
import importlib
import logging
import logging.config
import asyncio
import platform
from pathlib import Path
from time import time
from datetime import datetime, timezone
import pytz
from aiohttp import web
from hydrogram import Client, idle, __version__ as hydro_ver
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Performance Booster (Optional but Recommended)
try:
    import uvloop
    uvloop.install()
except:
    pass

# Local Imports
from info import API_ID, API_HASH, BOT_TOKEN, PORT, LOG_CHANNEL, TIME_ZONE, ADMINS
from utils import temp, load_temp_config
from Script import script
from web import web_app
from database.users_chats_db import db

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
# Reduce Noise
logging.getLogger("hydrogram").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="FastFinderBot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=10,
        )

    async def start(self):
        # 1. Set Start Time
        temp.START_TIME = time()
        temp.BOT = self 
        
        # 2. Load Dynamic Config (Memory Cache) 🚀
        # यह बहुत जरूरी है ताकि हर रिक्वेस्ट पर DB कॉल न हो
        logging.info("⏳ Loading Dynamic Configurations...")
        await load_temp_config()
        
        # 3. Load Banned List
        try:
            b_users, b_chats = await db.get_banned()
            temp.BANNED_USERS = b_users
            temp.BANNED_CHATS = b_chats
        except Exception as e:
            logging.error(f"Error loading banned list: {e}")

        # 4. Start Client
        await super().start()
        me = await self.get_me()
        
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        temp.B_ID = me.id
        
        # 5. Start Web Server
        app = web.AppRunner(web_app)
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()
        logging.info(f"🌍 Web Server Started on Port {PORT}")
        logging.info(f"🚀 @{me.username} Started Successfully!")
        
        # 6. Start Premium Checker
        self.loop.create_task(self.check_premium_expiry())

        # 7. 🔥 SMART RESTART CHECKER 🔥
        # अगर आपने /restart कमांड दिया था, तो यह उसे कन्फर्म करेगा
        await self.check_pending_restart()

        # 8. Send Startup Log
        await self.send_startup_log(me)

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped. Bye!")

    # --- 🛠️ HELPER: CHECK RESTART STATUS ---
    async def check_pending_restart(self):
        try:
            conf = await db.get_config()
            r_data = conf.get('restart_status')
            
            if r_data:
                chat_id = r_data['chat_id']
                msg_id = r_data['msg_id']
                
                try:
                    await self.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=(
                            "<b>✅ System Restarted Successfully!</b>\n\n"
                            "🔹 <i>All Modules Reloaded.</i>\n"
                            "🔹 <i>Cache Cleared.</i>\n"
                            "🔹 <i>Dual DB Connected.</i>\n"
                            "🔹 <i>Clone Engine Active.</i>"
                        )
                    )
                except Exception as e:
                    logging.warning(f"Could not edit restart msg: {e}")
                
                # फ्लैग हटा दें
                await db.update_config('restart_status', None)
        except Exception as e:
            logging.error(f"Restart check failed: {e}")

    # --- 📝 HELPER: STARTUP LOG ---
    async def send_startup_log(self, me):
        try:
            tz = pytz.timezone(TIME_ZONE)
            now = datetime.now(tz)
            date_str = now.strftime("%d %b %Y")
            time_str = now.strftime("%I:%M %p")
        except:
            date_str, time_str = "Unknown", "Unknown"

        if LOG_CHANNEL:
            try:
                # DB Counts
                from database.ia_filterdb import db_count_documents
                pri, bak, tot = await db_count_documents()
                
                txt = (
                    f"<b>🚀 Bᴏᴛ Sᴛᴀʀᴛᴇᴅ Sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
                    f"<b>🤖 Bᴏᴛ:</b> @{me.username}\n"
                    f"<b>🐍 Pʏᴛʜᴏɴ:</b> <code>{platform.python_version()}</code>\n"
                    f"<b>📡 Hʏᴅʀᴏɢʀᴀᴍ:</b> <code>{hydro_ver}</code>\n"
                    f"<b>🗄️ Pʀɪᴍᴀʀʏ Dʙ:</b> <code>{pri}</code>\n"
                    f"<b>🗄️ Bᴀᴄᴋᴜᴘ Dʙ:</b> <code>{bak}</code>\n"
                    f"<b>📅 Dᴀᴛᴇ:</b> <code>{date_str}</code>\n"
                    f"<b>⌚ Tɪᴍᴇ:</b> <code>{time_str}</code>"
                )
                await self.send_message(chat_id=LOG_CHANNEL, text=txt)
            except Exception as e:
                logging.error(f"Failed to send log: {e}")

        if ADMINS:
            for admin_id in ADMINS:
                try:
                    await self.send_message(
                        chat_id=admin_id,
                        text=f"<b>✅ {me.mention} is now Online!</b>\n📅 <code>{date_str} • {time_str}</code>"
                    )
                except: pass

    # --- 💎 PREMIUM EXPIRY CHECKER TASK ---
    async def check_premium_expiry(self):
        logging.info("💎 Premium Expiry Checker Started...")
        while True:
            try:
                # अगर प्रीमियम फीचर बंद है तो चेक मत करो
                if not temp.CONFIG.get('is_premium_active', True): # Default True
                    await asyncio.sleep(600)
                    continue

                async for user in await db.get_premium_users():
                    try:
                        user_id = user['id']
                        plan_status = user.get('status', {})
                        expiry_date = plan_status.get('expire')
                        
                        if not plan_status.get('premium') or not isinstance(expiry_date, datetime):
                            continue
                        
                        # Fix Timezone Offset
                        if expiry_date.tzinfo is None:
                            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

                        now = datetime.now(timezone.utc)
                        delta = expiry_date - now
                        seconds = delta.total_seconds()
                        
                        # Readable Date
                        try:
                            tz = pytz.timezone(TIME_ZONE)
                            expiry_ist = expiry_date.astimezone(tz)
                            expiry_str = expiry_ist.strftime("%d %b %Y, %I:%M %p")
                        except:
                            expiry_str = expiry_date.strftime("%d %b %Y, %I:%M %p")
                        
                        btn = InlineKeyboardMarkup([[InlineKeyboardButton("💎 Renew Now", callback_data="activate_plan")]])
                        msg_text = None
                        
                        # --- REMINDER LOGIC ---
                        if 43200 <= seconds < 43260: # 12 Hours
                            msg_text = f"<b>🕛 Pʀᴇᴍɪᴜᴍ Exᴘɪʀɪɴɢ Sᴏᴏɴ!</b>\n\nYour premium plan expires in <b>12 Hours</b>.\n📅 <b>Expiry:</b> <code>{expiry_str}</code>"
                        elif 21600 <= seconds < 21660: # 6 Hours
                            msg_text = f"<b>🕕 Pʀᴇᴍɪᴜᴍ Exᴘɪʀɪɴɢ Sᴏᴏɴ!</b>\n\nYour premium plan expires in <b>6 Hours</b>.\n📅 <b>Expiry:</b> <code>{expiry_str}</code>"
                        elif 3600 <= seconds < 3660: # 1 Hour
                            msg_text = f"<b>🕐 Pʀᴇᴍɪᴜᴍ Exᴘɪʀɪɴɢ Sᴏᴏɴ!</b>\n\nYour premium plan expires in <b>1 Hour</b>.\n📅 <b>Expiry:</b> <code>{expiry_str}</code>"
                        elif seconds <= 0: # Expired
                            msg_text = f"<b>🚫 Pʀᴇᴍɪᴜᴍ Exᴘɪʀᴇᴅ!</b>\n\nYour plan expired on <b>{expiry_str}</b>.\n<i>Renew now to continue enjoying exclusive features.</i>"
                            await db.update_plan(user_id, {'expire': '', 'trial': False, 'plan': '', 'premium': False})
                        
                        if msg_text:
                            # Old Reminder Delete
                            old_msg_id = temp.PREMIUM_REMINDERS.get(user_id)
                            if old_msg_id:
                                try: await self.delete_messages(user_id, old_msg_id)
                                except: pass 
                            
                            # Send New
                            try:
                                sent_msg = await self.send_message(chat_id=user_id, text=msg_text, reply_markup=btn)
                                temp.PREMIUM_REMINDERS[user_id] = sent_msg.id
                                if seconds <= 0: temp.PREMIUM_REMINDERS.pop(user_id, None)
                            except: pass
                                
                    except Exception as e:
                        logging.error(f"Error checking user {user.get('id')}: {e}")
                        
            except Exception as e:
                logging.error(f"Error in premium checker loop: {e}")
            
            await asyncio.sleep(60)

if __name__ == "__main__":
    Bot().run()
