import sys
import glob
import importlib
from pathlib import Path
from hydrogram import Client, idle
import logging
import logging.config
import asyncio
from aiohttp import web
from time import time

# Local Imports
from info import API_ID, API_HASH, BOT_TOKEN, PORT, LOG_CHANNEL
from utils import temp
from Script import script
from web import web_app

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("hydrogram").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)

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
        # Set Start Time
        temp.START_TIME = time()
        
        # --- CRITICAL FIX: Set Bot Instance for Web Server ---
        temp.BOT = self 
        
        # Start Client
        await super().start()
        me = await self.get_me()
        
        # Set Temp Variables
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        temp.B_ID = me.id
        
        # Start Web Server (For Streaming)
        app = web.AppRunner(web_app)
        await app.setup()
        await web.TCPSite(app, "0.0.0.0", PORT).start()
        logging.info(f"Web Server Started on Port {PORT}")
        
        logging.info(f"@{me.username} Started Successfully! 🚀")

        # Send Startup Log
        if LOG_CHANNEL:
            try:
                await self.send_message(
                    chat_id=LOG_CHANNEL,
                    text=f"<b>🚀 {me.mention} Is Online!</b>\n\n<b>📅 Date:</b> <code>{time()}</code>"
                )
            except Exception as e:
                logging.error(f"Failed to send log: {e}")

    async def stop(self, *args):
        await super().stop()
        logging.info("Bot Stopped. Bye!")

if __name__ == "__main__":
    # Event Loop Policy for Python 3.11+
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
        
    Bot().run()
