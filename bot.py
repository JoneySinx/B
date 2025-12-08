import logging
import logging.config
import os
import time
import asyncio
from hydrogram import Client, __version__
from hydrogram.raw.all import layer
from hydrogram.enums import ParseMode
from hydrogram.errors import FloodWait
from aiohttp import web
from web import web_app
from info import (
    API_ID, API_HASH, BOT_TOKEN, LOG_CHANNEL, 
    PORT, ADMINS, FILES_DATABASE_URL, DATA_DATABASE_URL
)
from utils import temp, check_premium
from database.users_chats_db import db
from typing import Union, Optional, AsyncGenerator
from hydrogram import types

# लॉगिंग कॉन्फ़िगरेशन
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("hydrogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Auto_Filter_Bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"},
            workers=50,
            sleep_threshold=10
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        temp.BOT = self
        
        # Banned Users/Chats Load करें
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        
        # Restart Message Logic (पुराने मैसेज को एडिट करना)
        if os.path.exists('restart.txt'):
            try:
                with open('restart.txt', 'r') as file:
                    chat_id, msg_id = map(int, file.read().split())
                await self.edit_message_text(chat_id=chat_id, message_id=msg_id, text="<b>✅ Successfully Restarted!</b>")
            except Exception as e:
                logger.error(f"Failed to edit restart message: {e}")
            finally:
                os.remove('restart.txt')

        # Web Server शुरू करें
        app = web.AppRunner(web_app)
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()
        logger.info(f"Web Server Started on Port {PORT}")

        # Premium Check Task शुरू करें
        asyncio.create_task(check_premium(self))

        # --- NEW: Send Startup Message to Admins ---
        startup_msg = (
            f"<b>🤖 Bot Started!</b>\n\n"
            f"<b>Name:</b> {me.mention}\n"
            f"<b>Username:</b> @{me.username}\n"
            f"<b>Hydrogram:</b> v{__version__}\n"
            f"<b>Time:</b> {time.strftime('%I:%M %p %d/%m/%Y')}"
        )
        
        # सभी एडमिन को मैसेज भेजें
        for admin in ADMINS:
            try:
                await self.send_message(chat_id=admin, text=startup_msg)
            except Exception:
                pass

        # Log Channel पर मैसेज
        try:
            await self.send_message(
                chat_id=LOG_CHANNEL,
                text=f"<b>🔥 {me.mention} Bot Restarted!</b>\n\n<b>Hydrogram Version:</b> <code>v{__version__}</code>\n<b>Layer:</b> <code>{layer}</code>"
            )
        except Exception as e:
            logger.error(f"Bot failed to send message to LOG_CHANNEL: {e}")

        logger.info(f"@{me.username} Started Successfully! 🚀")

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot Stopped. Bye!")

# -------------------------------------------------------------
# FINAL FIX FOR PYTHON 3.11 EVENT LOOP
# -------------------------------------------------------------
if __name__ == "__main__":
    try:
        # 1. नया लूप बनाएँ
        loop = asyncio.new_event_loop()
        
        # 2. इस लूप को ग्लोबल सेट करें
        asyncio.set_event_loop(loop)
        
        # 3. अब बॉट बनाएँ
        app = Bot()
        
        # 4. बॉट चलाएँ
        app.run()
        
    except Exception as e:
        logger.error(f"Runtime Error: {e}")
