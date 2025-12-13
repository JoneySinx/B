import os
import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from time import time as time_now
from time import monotonic

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from hydrogram.errors import MessageTooLong, ChatAdminRequired, FloodWait

from Script import script
# Updated imports for new DB functions
from database.ia_filterdb import db_count_documents, delete_files, save_file, get_file_details
from database.users_chats_db import db
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, URL, BIN_CHANNEL, 
    STICKERS, INDEX_CHANNELS, ADMINS, DELETE_TIME, 
    SUPPORT_LINK, UPDATES_LINK, LOG_CHANNEL, PICS, IS_STREAM, REACTIONS, PM_FILE_DELETE_TIME
)
from utils import (
    is_premium, upload_image, get_settings, get_size, is_subscribed, 
    is_check_admin, get_shortlink, get_verify_status, update_verify_status, 
    get_readable_time, get_wish, temp, save_group_settings
)

logger = logging.getLogger(__name__)
TIME_FMT = "%d/%m/%Y %I:%M %p"

# --- HELPER FUNCTIONS ---

async def get_grp_stg(group_id):
    settings = await get_settings(group_id)
    btn = [[
        InlineKeyboardButton('📝 File Caption', callback_data=f'caption_setgs#{group_id}'),
        InlineKeyboardButton('👋 Welcome Msg', callback_data=f'welcome_setgs#{group_id}')
    ],[
        InlineKeyboardButton('📚 Tutorial Link', callback_data=f'tutorial_setgs#{group_id}')
    ],[
        InlineKeyboardButton(f'Spell Check {"✅" if settings["spell_check"] else "❌"}', callback_data=f'bool_setgs#spell_check#{settings["spell_check"]}#{group_id}'),
        InlineKeyboardButton(f'Welcome {"✅" if settings["welcome"] else "❌"}', callback_data=f'bool_setgs#welcome#{settings["welcome"]}#{group_id}')
    ],[
        InlineKeyboardButton(f"🗑️ Auto Delete: {get_readable_time(DELETE_TIME)}" if settings["auto_delete"] else "Auto Delete: ❌", callback_data=f'bool_setgs#auto_delete#{settings["auto_delete"]}#{group_id}')
    ],[
        InlineKeyboardButton(f"Mode: {'Link 🔗' if settings['links'] else 'Button 🔘'}", callback_data=f'bool_setgs#links#{settings["links"]}#{group_id}')
    ]]
    return btn

# --- START COMMAND ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    # 1. Group Handling
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            username = f'@{message.chat.username}' if message.chat.username else 'Private'
            await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))       
            await db.add_chat(message.chat.id, message.chat.title)
        
        wish = get_wish()
        user = message.from_user.mention if message.from_user else "Friend"
        
        btn = [[InlineKeyboardButton('⚡️ Jᴏɪɴ Uᴘᴅᴀᴛᴇs', url=UPDATES_LINK)]]
        await message.reply(text=f"<b>👋 Hᴇʏ {user}, {wish}\n\nI'ᴍ Rᴇᴀᴅʏ Tᴏ Hᴇʟᴘ ɪɴ ᴛʜɪs Gʀᴏᴜᴘ! 🚀</b>", reply_markup=InlineKeyboardMarkup(btn))
        return 
        
    # 2. React (Safe)
    try: await message.react(emoji=random.choice(REACTIONS), big=True)
    except: pass

    if not message.from_user:
        return

    # 3. User Registration
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.NEW_USER_TXT.format(message.from_user.mention, message.from_user.id))

    # 4. Normal Start Message
    if (len(message.command) != 2) or (len(message.command) == 2 and message.command[1] == 'start'):
        buttons = [
            [InlineKeyboardButton('👨‍🚒 Hᴇʟᴘ', callback_data='help'), InlineKeyboardButton('📊 Sᴛᴀᴛs', callback_data='stats')], 
            [InlineKeyboardButton('💎 Gᴏ Pʀᴇᴍɪᴜᴍ : Rᴇᴍᴏᴠᴇ Aᴅs', url=f"https://t.me/{temp.U_NAME}?start=premium")]
        ]
        await message.reply_photo(photo=random.choice(PICS), caption=script.START_TXT.format(message.from_user.mention, get_wish()), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
        return

    mc = message.command[1]
    if mc == 'premium': return await plan(client, message)
    
    # 5. Settings Menu
    if mc.startswith('settings'):
        _, group_id = message.command[1].split("_")
        if not await is_check_admin(client, int(group_id), message.from_user.id): return await message.reply("<b>❌ Aᴄᴄᴇss Dᴇɴɪᴇᴅ! Yᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ Aᴅᴍɪɴ.</b>")
        btn = await get_grp_stg(int(group_id))
        return await message.reply(f"<b>⚙️ Sᴇᴛᴛɪɴɢs Mᴇɴᴜ ғᴏʀ:</b> <code>{group_id}</code>", reply_markup=InlineKeyboardMarkup(btn))

    # 6. Subscription Check
    btn = await is_subscribed(client, message)
    if btn:
        btn.append([InlineKeyboardButton("🔁 Tʀʏ Aɢᴀɪɴ", callback_data=f"checksub#{mc}")])
        await message.reply_photo(photo=random.choice(PICS), caption=f"<b>👋 Hᴇʟʟᴏ {message.from_user.mention},</b>\n\n<i>Pʟᴇᴀsᴇ Jᴏɪɴ Mʏ Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ Tᴏ Usᴇ Mᴇ!</i>", reply_markup=InlineKeyboardMarkup(btn))
        return 
        
    # 7. "Get All" Files Handler
    if mc.startswith('all'):
        try: _, grp_id, key = mc.split("_", 2)
        except ValueError: return await message.reply("❌ Invalid Link")
        
        files = temp.FILES.get(key)
        if not files: return await message.reply('<b>⚠️ Fɪʟᴇs Nᴏ Lᴏɴɢᴇʀ Exɪsᴛ!</b>')
        
        settings = await get_settings(int(grp_id))
        total_files = await message.reply(f"<b>⚡ Pʀᴏᴄᴇssɪɴɢ {len(files)} Fɪʟᴇs...</b>", parse_mode=enums.ParseMode.HTML)
        
        file_ids = [total_files.id]
        
        for file in files:
            CAPTION = settings['caption']
            f_caption = CAPTION.format(file_name=file['file_name'].title(), file_size=get_size(file['file_size']), file_caption=file['caption'])      
            btn = [[InlineKeyboardButton('❌ Cʟᴏsᴇ', callback_data='close_data')]]
            if IS_STREAM:
                btn.insert(0, [InlineKeyboardButton("🚀 Fᴀsᴛ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ", callback_data=f"stream#{file['_id']}")])

            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file['_id'],
                caption=f_caption,
                protect_content=False,
                reply_markup=InlineKeyboardMarkup(btn)
            )
            file_ids.append(msg.id)

        time = get_readable_time(PM_FILE_DELETE_TIME)
        vp = await message.reply(f"<b>⚠️ Nᴏᴛᴇ:</b> <i>Tʜᴇsᴇ ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {time} ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ.</i>")
        file_ids.append(vp.id)
        
        await asyncio.sleep(PM_FILE_DELETE_TIME)
        buttons = [[InlineKeyboardButton('♻️ Gᴇᴛ Fɪʟᴇs Aɢᴀɪɴ', callback_data=f"get_del_send_all_files#{grp_id}#{key}")]] 
        
        for i in range(0, len(file_ids), 100):
            try: await client.delete_messages(chat_id=message.chat.id, message_ids=file_ids[i:i+100])
            except: pass
            
        gone_msg = await message.reply("<b>🗑️ Fɪʟᴇs Dᴇʟᴇᴛᴇᴅ!</b>\n<i>Click below to get them again.</i>", reply_markup=InlineKeyboardMarkup(buttons))
        
        await asyncio.sleep(43200) # 12 Hours
        try: await gone_msg.delete()
        except: pass
        return

    # 8. Single File Handler
    try: type_, grp_id, file_id = mc.split("_", 2)
    except ValueError: return await message.reply("❌ Invalid Link")
    
    files_ = await get_file_details(file_id)
    if not files_: return await message.reply('<b>⚠️ Fɪʟᴇ Nᴏᴛ Fᴏᴜɴᴅ!</b>')
        
    settings = await get_settings(int(grp_id))
    CAPTION = settings['caption']
    f_name = files_['file_name'].title().replace(" L ", " l ")
    f_caption = CAPTION.format(file_name=f_name, file_size=get_size(files_['file_size']), file_caption=files_['caption'])
    
    btn = [[InlineKeyboardButton('❌ Cʟᴏsᴇ', callback_data='close_data')]]
    if IS_STREAM:
        btn.insert(0, [InlineKeyboardButton("🚀 Fᴀsᴛ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ", callback_data=f"stream#{file_id}")])
    
    vp = await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=False,
        reply_markup=InlineKeyboardMarkup(btn)
    )
    
    time = get_readable_time(PM_FILE_DELETE_TIME)
    msg = await vp.reply(f"<b>⚠️ Nᴏᴛᴇ:</b> <i>Tʜɪs ғɪʟᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ {time}.</i>")

    new_btn = [[InlineKeyboardButton('❌ Cʟᴏsᴇ', callback_data=f'close_data#{msg.id}')]]
    if IS_STREAM:
        new_btn.insert(0, [InlineKeyboardButton("🚀 Fᴀsᴛ Dᴏᴡɴʟᴏᴀᴅ / Wᴀᴛᴄʜ", callback_data=f"stream#{file_id}")])
    
    try:
        await vp.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_btn))
    except: pass

    await asyncio.sleep(PM_FILE_DELETE_TIME)
    try:
        await msg.delete()
        await vp.delete()
    except: pass

    btns = [[InlineKeyboardButton('♻️ Gᴇᴛ Fɪʟᴇ Aɢᴀɪɴ', callback_data=f"get_del_file#{grp_id}#{file_id}")]]
    gone_msg = await message.reply("<b>🗑️ Fɪʟᴇ Dᴇʟᴇᴛᴇᴅ!</b>\n<i>Click below to get it again.</i>", reply_markup=InlineKeyboardMarkup(btns))
    
    await asyncio.sleep(43200)
    try: await gone_msg.delete()
    except: pass

# --- ⚙️ ADMIN PANEL ENTRY POINT (NEW) ---
@Client.on_message(filters.command(["admin", "settings"]) & filters.user(ADMINS))
async def admin_panel(client, message):
    config = await db.get_config()
    
    mode = config.get('search_mode', 'hybrid').upper()
    shortner = "🟢 ON" if config.get('shortlink_enable') else "🔴 OFF"
    
    text = (
        f"<b>⚙️ <u>ADVANCED BOT CONTROL PANEL</u></b>\n\n"
        f"<b>🔍 Search Mode:</b> {mode}\n"
        f"<b>🔗 Shortlink:</b> {shortner}\n"
        f"<b>🛡️ Maintenance:</b> {'ON' if config.get('is_maintenance') else 'OFF'}\n\n"
        f"<i>Select a category to manage:</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("🗄️ Database Manager", callback_data="admin_db_menu"),
            InlineKeyboardButton("📺 Channel Config", callback_data="admin_channel_menu")
        ],
        [
            InlineKeyboardButton("🔗 Shortner Settings", callback_data="admin_shortner_menu"),
            InlineKeyboardButton("🤖 Clone Bot Manager", callback_data="admin_clone_menu")
        ],
        [InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# --- 📂 INDEXING COMMAND (DUAL DB SUPPORT) ---
@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_handler(client, message):
    if len(message.command) != 2:
        return await message.reply("<b>❌ Invalid Format!</b>\nUse: `/index [Channel ID]`")
    
    try:
        channel_id = int(message.command[1])
    except ValueError:
        return await message.reply("<b>❌ Error:</b> Channel ID must be an integer.")

    try:
        chat = await client.get_chat(channel_id)
    except Exception as e:
        return await message.reply(f"<b>❌ Error:</b> Could not access channel.\n`{e}`")

    # 🔥 CHOICE: Admin chooses target DB
    text = (
        f"<b>📂 INDEXING MANAGER</b>\n\n"
        f"<b>📢 Channel:</b> {chat.title}\n"
        f"<b>🆔 ID:</b> <code>{channel_id}</code>\n\n"
        f"<i>Select the target database for files from this channel:</i>"
    )
    
    buttons = [
        [
            InlineKeyboardButton("📂 Save to Primary DB", callback_data=f"index_start#primary#{channel_id}"),
            InlineKeyboardButton("🗄️ Save to Backup DB", callback_data=f"index_start#backup#{channel_id}")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="close_data")]
    ]
    
    await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons))


# --- 📥 INDEXING CALLBACK (ACTUAL PROCESS) ---
@Client.on_callback_query(filters.regex(r"^index_start"))
async def index_process_start(bot, query):
    _, target_db, channel_id = query.data.split("#")
    channel_id = int(channel_id)
    
    await query.message.edit(
        f"<b>🔄 Processing Started...</b>\n\n"
        f"<b>🎯 Target:</b> {target_db.upper()} Database\n"
        f"<i>Please wait while I fetch messages...</i>"
    )
    
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    
    # Run in background
    asyncio.create_task(index_files_to_db(bot, query.message, channel_id, target_db, total_files, duplicate, errors, deleted, no_media))


# --- 🔄 INDEXING BACKGROUND TASK ---
async def index_files_to_db(client, message, chat_id, target_db, total_files, duplicate, errors, deleted, no_media):
    try:
        msg = await message.reply("<b>📥 Initializing Indexing...</b>")
        
        async for message in client.get_chat_history(chat_id):
            if message.media:
                media = getattr(message, message.media.value)
                # Save with Target DB (New Feature)
                sts = await save_file(media, target_db=target_db)
                
                if sts == 'suc':
                    total_files += 1
                elif sts == 'dup':
                    duplicate += 1
                elif sts == 'err':
                    errors += 1
            else:
                no_media += 1

            if total_files % 20 == 0:
                try:
                    await msg.edit(
                        f"<b>🔄 Indexing in Progress...</b>\n\n"
                        f"<b>🎯 Target DB:</b> {target_db.upper()}\n"
                        f"<b>✅ Saved:</b> {total_files}\n"
                        f"<b>♻️ Duplicates:</b> {duplicate}\n"
                        f"<b>⚠️ Errors:</b> {errors}"
                    )
                except: pass
        
        await msg.edit(
            f"<b>✅ Indexing Completed!</b>\n\n"
            f"<b>🎯 Target DB:</b> {target_db.upper()}\n"
            f"<b>📂 Total Saved:</b> {total_files}\n"
            f"<b>♻️ Duplicates:</b> {duplicate}\n"
            f"<b>🗑️ Skipped:</b> {no_media + errors}"
        )
        
    except Exception as e:
        await message.reply(f"<b>❌ Critical Error during indexing:</b>\n`{e}`")


# --- ADMIN COMMANDS (EXISTING) ---

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete_file(bot, message):
    try: query = message.text.split(" ", 1)[1]
    except: return await message.reply_text("<b>Usage:</b> `/delete query`")
    btn = [[InlineKeyboardButton("✅ YES", callback_data=f"delete_{query}")],[InlineKeyboardButton("❌ NO", callback_data="close_data")]]
    await message.reply_text(f"<b>🗑️ Dᴇʟᴇᴛᴇ Fɪʟᴇs</b>\n\nMatch: <b>{query}</b>\n<i>Are you sure?</i>", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command('delete_all') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    btn = [[InlineKeyboardButton("🗑️ DESTROY ALL", callback_data="delete_all")],[InlineKeyboardButton("❌ CANCEL", callback_data="close_data")]]
    await message.reply_text("<b>⚠️ Dᴀɴɢᴇʀ Zᴏɴᴇ</b>\n\nThis will delete <b>ALL FILES</b> from the database.\n<i>This action cannot be undone.</i>", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command('stats'))
async def stats(bot, message):
    if message.from_user.id not in ADMINS: return await message.delete()
    
    files = await db_count_documents()
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    prm = await db.get_premium_count()
    used_bytes, free_bytes = await db.get_db_size()
    used = get_size(used_bytes)
    free = get_size(free_bytes)
    uptime = get_readable_time(time_now() - temp.START_TIME)
    
    text = (
        f"<b>📊 <u>Sʏsᴛᴇᴍ Sᴛᴀᴛɪsᴛɪᴄs</u></b>\n\n"
        f"<b>📂 Tᴏᴛᴀʟ Fɪʟᴇs:</b> {files}\n"
        f"<b>👥 Usᴇʀs:</b> {users}\n"
        f"<b>🏘️ Gʀᴏᴜᴘs:</b> {chats}\n"
        f"<b>💎 Pʀᴇᴍɪᴜᴍ:</b> {prm}\n\n"
        f"<b>💾 Dᴀᴛᴀʙᴀsᴇ:</b> {used} / {free}\n"
        f"<b>⚡ Uᴘᴛɪᴍᴇ:</b> {uptime}"
    )
    await message.reply_text(text)    

@Client.on_message(filters.command('link'))
async def link(bot, message):
    msg = message.reply_to_message
    if not msg: return await message.reply('<b>Reply to a File!</b>')
    try:
        media = getattr(msg, msg.media.value)
        msg = await bot.send_cached_media(chat_id=BIN_CHANNEL, file_id=media.file_id)
        from info import URL as SITE_URL
        base_url = SITE_URL[:-1] if SITE_URL.endswith('/') else SITE_URL
        watch = f"{base_url}/watch/{msg.id}"
        download = f"{base_url}/download/{msg.id}"
        btn=[[InlineKeyboardButton("🎬 Wᴀᴛᴄʜ Oɴʟɪɴᴇ", url=watch), InlineKeyboardButton("⚡ Dᴏᴡɴʟᴏᴀᴅ", url=download)],[InlineKeyboardButton('❌ Cʟᴏsᴇ', callback_data='close_data')]]
        f_name = media.file_name.title().replace(" L ", " l ")
        await message.reply(f'<b>🔗 Fɪʟᴇ Lɪɴᴋ Gᴇɴᴇʀᴀᴛᴇᴅ!</b>\n\n<b>📂 Nᴀᴍᴇ:</b> {f_name}', reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await message.reply(f'Error: {e}')

@Client.on_message(filters.command('index_channels'))
async def channels_info(bot, message):
    if message.from_user.id not in ADMINS: return
    env_ids = INDEX_CHANNELS
    db_ids = await db.get_index_channels_db()
    all_ids = list(set(env_ids + db_ids))
    if not all_ids: return await message.reply("<b>❌ No Index Channels Found.</b>")
    text = '<b>📑 <u>Iɴᴅᴇxᴇᴅ Cʜᴀɴɴᴇʟs</u></b>\n\n'
    for id in all_ids:
        try:
            chat = await bot.get_chat(id)
            text += f'🔹 <b>{chat.title}</b>\n   ID: `{id}`\n'
        except: text += f'🔸 <b>Unknown</b>\n   ID: `{id}`\n'
    text += f'\n<b>📊 Total:</b> {len(all_ids)}'
    await message.reply(text)

@Client.on_message(filters.command('add_channel') & filters.user(ADMINS))
async def add_index_channel_cmd(client, message):
    if len(message.command) < 2: return await message.reply("<b>Usage:</b> `/add_channel -100xxxxxx`")
    try: chat_id = int(message.command[1])
    except: return await message.reply("<b>❌ Invalid Chat ID!</b>")
    try:
        chat = await client.get_chat(chat_id)
        if chat.type != enums.ChatType.CHANNEL: return await message.reply("<b>❌ I can only index Channels.</b>")
    except: return await message.reply("<b>⚠️ Error:</b> Make me Admin in that channel first!")
    
    await db.add_index_channel(chat_id)
    await message.reply(f"<b>✅ Cʜᴀɴɴᴇʟ Aᴅᴅᴇᴅ:</b> {chat.title}")

@Client.on_message(filters.command('remove_channel') & filters.user(ADMINS))
async def remove_index_channel_cmd(client, message):
    if len(message.command) < 2: return await message.reply("<b>Usage:</b> `/remove_channel -100xxxxxx`")
    try: chat_id = int(message.command[1])
    except: return await message.reply("<b>❌ Invalid ID</b>")
    await db.remove_index_channel(chat_id)
    await message.reply(f"<b>🗑️ Rᴇᴍᴏᴠᴇᴅ:</b> `{chat_id}`")

@Client.on_message(filters.command('img_2_link'))
async def img_2_link(bot, message):
    reply_to_message = message.reply_to_message
    if not reply_to_message: return await message.reply('<b>Reply to an Image!</b>')
    file = reply_to_message.photo
    if file is None: return await message.reply('<b>❌ Invalid Media.</b>')
    text = await message.reply_text(text="<b>⚡ Pʀᴏᴄᴇssɪɴɢ...</b>")   
    path = await reply_to_message.download()  
    response = upload_image(path)
    try: os.remove(path)
    except: pass
    if not response: return await text.edit_text(text="<b>❌ Upload Failed!</b>")
    await text.edit_text(f"<b>✅ Iᴍᴀɢᴇ Uᴘʟᴏᴀᴅᴇᴅ!</b>\n\n<code>{response}</code>", disable_web_page_preview=True)

@Client.on_message(filters.command('ping'))
async def ping(client, message):
    start_time = monotonic()
    msg = await message.reply("🏓")
    end_time = monotonic()
    await msg.edit(f'<b>🏓 Pᴏɴɢ!</b> <code>{round((end_time - start_time) * 1000)} ms</code>')

# --- PREMIUM COMMANDS ---

@Client.on_message(filters.command('plan') & filters.private)
async def plan(client, message):
    if not IS_PREMIUM: return await message.reply('<b>⚠️ Premium Mode Disabled.</b>')
    btn = [[InlineKeyboardButton('💳 Bᴜʏ Pʀᴇᴍɪᴜᴍ Nᴏᴡ', callback_data='activate_plan')]]
    await message.reply(script.PLAN_TXT.format(PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME), reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command('myplan') & filters.private)
async def myplan(client, message):
    if not IS_PREMIUM: 
        return await message.reply('<b>⚠️ Premium Mode Disabled.</b>')
    if message.from_user.id in ADMINS: 
        return await message.reply(f"<b>👑 Hᴇʟʟᴏ Aᴅᴍɪɴ {message.from_user.mention}!</b>\n\n<i>You have infinite power!</i> ⚡")
    
    mp = await db.get_plan(message.from_user.id)
    is_prem = await is_premium(message.from_user.id, client)
    
    if not is_prem:
        btn = [[InlineKeyboardButton('💳 Uᴘɢʀᴀᴅᴇ Tᴏ Pʀᴇᴍɪᴜᴍ', callback_data='activate_plan')]]
        return await message.reply("<b>❌ Nᴏ Aᴄᴛɪᴠᴇ Pʟᴀɴ!</b>\n\n<i>Upgrade now to remove ads & restrictions.</i>", reply_markup=InlineKeyboardMarkup(btn))
    
    expire_date = mp.get('expire')
    readable_date = expire_date.strftime(TIME_FMT) if isinstance(expire_date, datetime) else "Unlimited"
        
    await message.reply(
        f"<b>💎 <u>VIP Mᴇᴍʙᴇʀ Cᴀʀᴅ</u></b>\n\n"
        f"<b>👤 Usᴇʀ:</b> {message.from_user.mention}\n"
        f"<b>🆔 ID:</b> <code>{message.from_user.id}</code>\n"
        f"<b>🗓 Pʟᴀɴ:</b> {mp.get('plan', 'Custom')}\n"
        f"<b>⏳ Exᴘɪʀᴇs:</b> <code>{readable_date}</code>"
    )

@Client.on_message(filters.command('add_prm') & filters.user(ADMINS))
async def add_prm(bot, message):
    if not IS_PREMIUM: return await message.reply('Premium disabled')
    try: _, user_id, d = message.text.split(' ')
    except: return await message.reply('<b>Usage:</b> `/add_prm user_id days`')
    try: d = int(d[:-1]) if d.endswith('d') else int(d)
    except: return await message.reply('❌ Invalid Days')
    try: user = await bot.get_users(user_id)
    except Exception as e: return await message.reply(f'Error: {e}')
    
    mp = await db.get_plan(user.id)
    ex = datetime.now(timezone.utc) + timedelta(days=d)
    mp['expire'] = ex
    mp['plan'] = f'{d} days'
    mp['premium'] = True
    await db.update_plan(user.id, mp)
    
    await bot.send_message(LOG_CHANNEL, f"<b>💎 Pʀᴇᴍɪᴜᴍ Aᴅᴅᴇᴅ (Mᴀɴᴜᴀʟ)</b>\n\n👤 <b>Usᴇʀ:</b> {user.mention}\n🆔 <b>ID:</b> <code>{user.id}</code>\n🗓 <b>Dᴜʀᴀᴛɪᴏɴ:</b> {d} Days\n👮‍♂️ <b>Aᴅᴍɪɴ:</b> {message.from_user.mention}")
    await message.reply(f"<b>✅ Pʀᴇᴍɪᴜᴍ Aᴄᴛɪᴠᴀᴛᴇᴅ!</b>\nUser: {user.mention}\nExpires: {ex.strftime(TIME_FMT)}")
    try: await bot.send_message(user.id, f"<b>🎉 Cᴏɴɢʀᴀᴛᴜʟᴀᴛɪᴏɴs!</b>\n\nYour Premium Plan for <b>{d} Days</b> has been activated by Admin.")
    except: pass

@Client.on_message(filters.command('rm_prm') & filters.user(ADMINS))
async def rm_prm(bot, message):
    if not IS_PREMIUM: return await message.reply('Premium disabled')
    try: _, user_id = message.text.split(' ')
    except: return await message.reply('<b>Usage:</b> `/rm_prm user_id`')
    try: user = await bot.get_users(user_id)
    except: return await message.reply('User not found')
    
    mp = await db.get_plan(user.id)
    mp['expire'] = ''
    mp['plan'] = ''
    mp['premium'] = False
    await db.update_plan(user.id, mp)
    
    await bot.send_message(LOG_CHANNEL, f"<b>🔻 Pʀᴇᴍɪᴜᴍ Rᴇᴍᴏᴠᴇᴅ</b>\n\n👤 <b>Usᴇʀ:</b> {user.mention}\n🆔 <b>ID:</b> <code>{user.id}</code>\n👮‍♂️ <b>Aᴅᴍɪɴ:</b> {message.from_user.mention}")
    await message.reply(f"<b>🗑️ Pʀᴇᴍɪᴜᴍ Rᴇᴍᴏᴠᴇᴅ ғʀᴏᴍ {user.mention}</b>")
    try: await bot.send_message(user.id, "<b>⚠️ Yᴏᴜʀ Pʀᴇᴍɪᴜᴍ Pʟᴀɴ ʜᴀs ʙᴇᴇɴ ʀᴇᴠᴏᴋᴇᴅ!</b>")
    except: pass

@Client.on_message(filters.command('prm_list') & filters.user(ADMINS))
async def prm_list(bot, message):
    tx = await message.reply('<b>🔄 Fᴇᴛᴄʜɪɴɢ Dᴀᴛᴀ...</b>')
    out = "<b>💎 <u>Pʀᴇᴍɪᴜᴍ Usᴇʀs Lɪsᴛ</u></b>\n\n"
    count = 0
    async for user in await db.get_premium_users():
        if user['status']['premium']:
            count += 1
            try: u = await bot.get_users(user['id']); mention = u.mention
            except: mention = "Unknown"
            
            expiry = user['status']['expire']
            exp_str = expiry.strftime(TIME_FMT) if isinstance(expiry, datetime) else "Unlimited"
            out += f"<b>{count}.</b> {mention} (`{user['id']}`
) | ⏳ {exp_str}\n"
            
    if count == 0: await tx.edit_text("<b>❌ Nᴏ Pʀᴇᴍɪᴜᴍ Usᴇʀs Fᴏᴜɴᴅ.</b>")
    else:
        try: await tx.edit_text(out)
        except MessageTooLong:
            with open('premium_users.txt', 'w+') as f: f.write(out.replace('<b>', '').replace('</b>', '').replace('`', ''))
            await message.reply_document('premium_users.txt', caption="💎 Premium Users List")
