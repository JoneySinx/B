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
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from typing import Union, Optional, AsyncGenerator

# Performance Booster
try:
    import uvloop
    uvloop.install()
except:
    pass

# Local Imports
from info import API_ID, API_HASH, BOT_TOKEN, PORT, LOG_CHANNEL, TIME_ZONE, ADMINS, DATABASE_NAME
from utils import temp, load_temp_config
from Script import script
from web import web_app
from database.users_chats_db import db

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("hydrogram").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name=DATABASE_NAME,
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
        
        # 2. Load Config
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
        app_runner = web.AppRunner(web_app)
        await app_runner.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app_runner, bind_address, PORT).start()
        logging.info(f"🌍 Web Server Started on Port {PORT}")
        logging.info(f"🚀 @{me.username} Started Successfully!")
        
        # 6. Start Background Tasks
        self.loop.create_task(self.check_premium_expiry())
        await self.check_pending_restart()
        await self.send_startup_log(me)

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped. Bye!")

    # ==========================================================================
    # 📺 STREAMING METHODS (THIS WAS MISSING)
    # ==========================================================================
    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["Message", None]]:
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                yield message
                current += 1

    async def stream_media(self, message, limit=0, offset=0):
        """
        Custom generator to stream media chunks for Web Player.
        Required by web/route.py
        """
        try:
            from web.utils.custom_dl import TGCustomYield, chunk_size, offset_fix
            
            file_id = getattr(message, "file_id", None)
            if not file_id:
                media = getattr(message, message.media.value, None)
                file_id = media.file_id

            file_size = getattr(media, "file_size", 0)
            
            # Smart Chunking for smooth playback
            c_size = await chunk_size(file_size)
            offset = await offset_fix(offset, c_size)
            
            first_part_cut = offset % c_size
            last_part_cut = (limit % c_size) + first_part_cut
            part_count = (limit - last_part_cut + first_part_cut) // c_size
            
            loader = TGCustomYield()
            async for chunk in loader.yield_file(message, offset, first_part_cut, last_part_cut, part_count, c_size):
                yield chunk
                
        except Exception as e:
            logging.error(f"Streaming Error: {e}")
            raise e

    # ==========================================================================
    # 🛠️ HELPER FUNCTIONS
    # ==========================================================================
    async def check_pending_restart(self):
        try:
            conf = await db.get_config()
            r_data = conf.get('restart_status')
            if r_data:
                try:
                    await self.edit_message_text(
                        chat_id=r_data['chat_id'],
                        message_id=r_data['msg_id'],
                        text="<b>✅ System Restarted Successfully!</b>\n\n🔹 <i>All Modules Reloaded.</i>\n🔹 <i>Cache Cleared.</i>"
                    )
                except: pass
                await db.update_config('restart_status', None)
        except: pass

    async def send_startup_log(self, me):
        if LOG_CHANNEL:
            try:
                from database.ia_filterdb import db_count_documents
                pri, bak, tot = await db_count_documents()
                txt = f"<b>🚀 Bᴏᴛ Sᴛᴀʀᴛᴇᴅ!</b>\n@{me.username}\n\n<b>💾 Pri DB:</b> {pri}\n<b>💾 Bak DB:</b> {bak}"
                await self.send_message(chat_id=LOG_CHANNEL, text=txt)
            except: pass

    async def check_premium_expiry(self):
        logging.info("💎 Premium Expiry Checker Started...")
        while True:
            try:
                if not temp.CONFIG.get('is_premium_active', True):
                    await asyncio.sleep(600)
                    continue

                async for user in await db.get_premium_users():
                    try:
                        user_id = user['id']
                        plan_status = user.get('status', {})
                        expiry_date = plan_status.get('expire')
                        
                        if not plan_status.get('premium') or not isinstance(expiry_date, datetime):
                            continue
                        
                        if expiry_date.tzinfo is None:
                            expiry_date = expiry_date.replace(tzinfo=timezone.utc)

                        now = datetime.now(timezone.utc)
                        delta = expiry_date - now
                        seconds = delta.total_seconds()
                        
                        if seconds <= 0:
                            await db.update_plan(user_id, {'expire': '', 'trial': False, 'plan': '', 'premium': False})
                            await self.send_message(user_id, "<b>🚫 Your Premium Plan has Expired!</b>")
                            
                    except: pass
            except: pass
            await asyncio.sleep(60)

if __name__ == "__main__":
    # 🔥 CRITICAL FIX FOR KOYEB / DOCKER
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    Bot().run()
