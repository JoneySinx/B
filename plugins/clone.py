import os
import logging
import asyncio
from hydrogram import Client, filters, enums
from hydrogram.errors import PeerIdInvalid, AccessTokenInvalid, FloodWait
from database.users_chats_db import db
from info import API_ID, API_HASH, LOG_CHANNEL, ADMINS

logger = logging.getLogger(__name__)

# --- 🧠 GLOBAL MEMORY ---
# Stores live client instances: {bot_id: Client}
CLONE_SESSIONS = {} 
# Stores ownership: {bot_id: owner_id}
CLONE_OWNERS = {}

# --- 🚦 SEMAPHORE (Traffic Control) ---
# Limit concurrent startups to prevent server overload
START_SEMAPHORE = asyncio.Semaphore(5)

# ==============================================================================
# 🛠️ HELPER: START A CLONE (THE ENGINE)
# ==============================================================================
async def start_clone_bot(token):
    async with START_SEMAPHORE: 
        try:
            client = Client(
                name=f":memory:{token}", 
                api_id=API_ID, 
                api_hash=API_HASH, 
                bot_token=token, 
                plugins={"root": "plugins"}, 
                in_memory=True
            )
            await client.start()
            me = await client.get_me()
            
            # Save Session
            CLONE_SESSIONS[me.id] = client
            return client, me
            
        except AccessTokenInvalid:
            # Auto-Cleanup: If token revoked, remove from DB
            logger.warning(f"❌ Invalid Token Found & Removed: {token}")
            await db.db.clones.delete_one({'token': token})
            return None, None
            
        except Exception as e:
            logger.error(f"❌ Clone Error: {token} | {e}")
            return None, None

# ==============================================================================
# 🚀 COMMAND: /clone [TOKEN]
# ==============================================================================
@Client.on_message(filters.command("clone") & filters.private)
async def clone_handler(bot, message):
    # 1. Check Admin Permission (Mood System)
    config = await db.get_config()
    if config.get('disable_clone', False):
        return await message.reply("<b>🚫 Clone creation is currently Disabled by Admin.</b>")

    # 2. Check Input
    if len(message.command) < 2:
        return await message.reply(
            "<b>⚠️ Usage:</b>\n"
            "`/clone [Bot Token]`\n\n"
            "<i>Get your bot token from @BotFather</i>"
        )
    
    token = message.command[1]
    msg = await message.reply("<b>♻️ Creating your Clone... Please wait.</b>")
    
    # 3. Check Duplicate
    is_exist = await db.db.clones.find_one({'token': token})
    if is_exist:
        return await msg.edit(f"<b>⚠️ This bot is already cloned!</b>\n\nUserName: @{is_exist['username']}")

    # 4. Start Client
    client, me = await start_clone_bot(token)
    
    if not client:
        return await msg.edit("<b>❌ Invalid Bot Token!</b>\nPlease check and try again.")
    
    # 5. Save to DB
    await db.db.clones.insert_one({
        'user_id': message.from_user.id,
        'token': token,
        'username': me.username,
        'bot_id': me.id,
        'name': me.first_name
    })
    
    # 6. Update Owner Memory
    CLONE_OWNERS[me.id] = message.from_user.id
    
    text = (
        f"<b>✅ Clone Created Successfully!</b>\n\n"
        f"<b>🤖 Bot:</b> @{me.username}\n"
        f"<b>👤 Owner:</b> {message.from_user.mention}\n\n"
        f"<i>My database files are now available in your bot! 🚀</i>"
    )
    await msg.edit(text)
    
    # Log to Admin Channel
    try:
        await bot.send_message(LOG_CHANNEL, f"<b>#New_Clone 🤖</b>\nUser: {message.from_user.mention}\nBot: @{me.username}")
    except: pass

# ==============================================================================
# 🛑 COMMAND: /delete_clone
# ==============================================================================
@Client.on_message(filters.command("delete_clone") & filters.private)
async def delete_clone_handler(bot, message):
    if len(message.command) < 2:
        return await message.reply("<b>⚠️ Usage:</b> `/delete_clone [Bot Token]`")
    
    token = message.command[1]
    clone_data = await db.db.clones.find_one({'user_id': message.from_user.id, 'token': token})
    
    if not clone_data:
        return await message.reply("<b>❌ Clone not found!</b>")
        
    # Stop Running Client
    bot_id = clone_data.get('bot_id')
    if bot_id and bot_id in CLONE_SESSIONS:
        try:
            await CLONE_SESSIONS[bot_id].stop()
            del CLONE_SESSIONS[bot_id]
        except: pass
        
    # Remove from DB
    await db.db.clones.delete_one({'_id': clone_data['_id']})
    await message.reply(f"<b>✅ Clone @{clone_data['username']} deleted and stopped!</b>")

# ==============================================================================
# 📡 CLONE SPECIFIC HANDLERS
# ==============================================================================
# These handlers only run inside clone bots to prevent main bot conflicts

@Client.on_message(filters.command("broadcast") & filters.private)
async def clone_broadcast_handler(client, message):
    """
    Allows Clone Owners to broadcast (Placeholder logic).
    """
    my_id = client.me.id
    
    # Check if this is a Clone Bot
    if my_id in CLONE_OWNERS:
        owner_id = CLONE_OWNERS[my_id]
        
        # Security Check: Only Owner can broadcast
        if message.from_user.id != owner_id:
            return 
            
        if not message.reply_to_message:
            return await message.reply("<b>Reply to a message to broadcast!</b>")
            
        # Since Clones share Main DB, actual broadcasting requires specific filtering.
        # For now, we inform the user.
        await message.reply("<b>⚠️ Broadcast Feature:</b>\n\nCurrently, clones share the main database. This feature will be enabled in future updates to prevent spamming the main user base.")

# ==============================================================================
# 🔁 RESTART ENGINE (AUTO-STARTUP)
# ==============================================================================
async def restart_all_clones():
    """
    Restarts all clones when the main bot starts.
    """
    logger.info("♻️ Initializing Clone Engine (Advanced Mode)...")
    clones = await db.db.clones.find().to_list(length=None)
    
    tasks = []
    for clone in clones:
        token = clone['token']
        if 'bot_id' in clone:
            CLONE_OWNERS[clone['bot_id']] = clone['user_id']
        tasks.append(start_clone_bot(token))
        
    # Run concurrently (Semaphore limits load)
    if tasks:
        results = await asyncio.gather(*tasks)
        successful = [r for r, m in results if r is not None]
        logger.info(f"✅ {len(successful)} Clones Restarted Successfully!")
    else:
        logger.info("✅ No Clones Found.")

# Start Engine on Load
asyncio.create_task(restart_all_clones())
