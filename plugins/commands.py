import os
import random
import string
import asyncio
import logging # Logging जोड़ा गया
from time import time as time_now
from time import monotonic
# timezone इम्पोर्ट किया गया
from datetime import datetime, timedelta, timezone 
from Script import script
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto # InputMediaPhoto जोड़ा गया
# DB functions को async माना गया
from database.ia_filterdb import db_count_documents, second_db_count_documents, get_file_details, delete_files
from database.users_chats_db import db
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, URL, BIN_CHANNEL, 
    SECOND_FILES_DATABASE_URL, STICKERS, INDEX_CHANNELS, ADMINS, IS_VERIFY, 
    VERIFY_TUTORIAL, VERIFY_EXPIRE, SHORTLINK_API, SHORTLINK_URL, DELETE_TIME, 
    SUPPORT_LINK, UPDATES_LINK, LOG_CHANNEL, PICS, IS_STREAM, REACTIONS, PM_FILE_DELETE_TIME
)
from utils import (
    is_premium, upload_image, get_settings, get_size, is_subscribed, 
    is_check_admin, get_shortlink, get_verify_status, update_verify_status, 
    save_group_settings, temp, get_readable_time, get_wish, get_seconds
)
# get_grp_stg को commands/utils से import किया गया माना जाता है

logger = logging.getLogger(__name__)

async def del_stk(s):
    await asyncio.sleep(3)
    try:
        await s.delete()
    except Exception:
        pass # Ignore errors if sticker already deleted

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id): # AWAIT जोड़ा गया
            total = await client.get_chat_members_count(message.chat.id)
            username = f'@{message.chat.username}' if message.chat.username else 'Private'
            await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))       
            await db.add_chat(message.chat.id, message.chat.title) # AWAIT जोड़ा गया
        # ... (rest of group message logic is fine)
        # ... (group message reply)
        return 
        
    try:
        await message.react(emoji=random.choice(REACTIONS), big=True)
    except:
        await message.react(emoji="⚡️", big=True)

    d = await client.send_sticker(message.chat.id, random.choice(STICKERS))
    asyncio.create_task(del_stk(d))

    if not await db.is_user_exist(message.from_user.id): # AWAIT जोड़ा गया
        await db.add_user(message.from_user.id, message.from_user.first_name) # AWAIT जोड़ा गया
        await client.send_message(LOG_CHANNEL, script.NEW_USER_TXT.format(message.from_user.mention, message.from_user.id))

    verify_status = await get_verify_status(message.from_user.id) # AWAIT जोड़ा गया
    
    # Timezone-aware comparison
    if verify_status['is_verified'] and verify_status['expire_time'] and datetime.now(timezone.utc) > verify_status['expire_time']:
        await update_verify_status(message.from_user.id, is_verified=False) # AWAIT जोड़ा गया

    if (len(message.command) != 2) or (len(message.command) == 2 and message.command[1] == 'start'):
        # ... (start command buttons and reply logic is fine)
        return

    mc = message.command[1]

    if mc == 'premium':
        return await plan(client, message)
    
    if mc.startswith('settings'):
        _, group_id = message.command[1].split("_")
        if not await is_check_admin(client, (int(group_id)), message.from_user.id): # AWAIT जोड़ा गया
            return await message.reply("You not admin in this group.")
        btn = await get_grp_stg(int(group_id)) # AWAIT जोड़ा गया
        chat = await client.get_chat(int(group_id))
        return await message.reply(f"Change your settings for <b>'{chat.title}'</b> as your wish. ⚙", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)


    if mc.startswith('verify'):
        _, token = mc.split("_", 1)
        verify_status = await get_verify_status(message.from_user.id) # AWAIT जोड़ा गया
        if verify_status['verify_token'] != token:
            return await message.reply("Your verify token is invalid.")
            
        expiry_time = datetime.now(timezone.utc) + timedelta(seconds=VERIFY_EXPIRE) # Timezone-aware
        await update_verify_status(message.from_user.id, is_verified=True, expire_time=expiry_time) # AWAIT जोड़ा गया
        
        # ... (rest of verification success logic is fine)
        
        return
    
    verify_status = await get_verify_status(message.from_user.id) # AWAIT जोड़ा गया
    is_prem = await is_premium(message.from_user.id, client)
    
    if IS_VERIFY and not verify_status['is_verified'] and not is_prem:
        # ... (verification required logic is fine)
        await update_verify_status(message.from_user.id, verify_token=token, link="" if mc == 'inline_verify' else mc) # AWAIT जोड़ा गया
        return

    btn = await is_subscribed(client, message) # AWAIT जोड़ा गया
    if btn:
        # ... (force subscribe logic is fine)
        return 
        
    if mc.startswith('all'):
        _, grp_id, key = mc.split("_", 2)
        files = temp.FILES.get(key)
        if not files:
            return await message.reply('No Such All Files Exist!')
        settings = await get_settings(int(grp_id)) # AWAIT जोड़ा गया
        file_ids = []
        
        # files list is temporary, delete messages in batches of 100
        all_ids_to_delete = []
        total_files = await message.reply(f"<b><i>🗂 Total files - <code>{len(files)}</code></i></b>", parse_mode=enums.ParseMode.HTML)
        all_ids_to_delete.append(total_files.id)
        
        for file in files:
            # ... (caption formatting and button creation logic is fine)

            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file['_id'],
                caption=f_caption,
                protect_content=False,
                reply_markup=InlineKeyboardMarkup(btn)
            )
            all_ids_to_delete.append(msg.id)

        time = get_readable_time(PM_FILE_DELETE_TIME)
        vp = await message.reply(f"Nᴏᴛᴇ: Tʜɪs ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇ ɪɴ {time} ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛs. Sᴀᴠᴇ ᴛʜᴇ ғɪʟᴇs ᴛᴏ sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ")
        all_ids_to_delete.append(vp.id)
        
        await asyncio.sleep(PM_FILE_DELETE_TIME)
        buttons = [[InlineKeyboardButton('ɢᴇᴛ ғɪʟᴇs ᴀɢᴀɪɴ', callback_data=f"get_del_send_all_files#{grp_id}#{key}")]] 
        
        # Delete in batches of 100
        for i in range(0, len(all_ids_to_delete), 100):
            batch = all_ids_to_delete[i:i + 100]
            try:
                await client.delete_messages(
                    chat_id=message.chat.id,
                    message_ids=batch
                )
            except Exception as e:
                logger.warning(f"Batch delete failed: {e}")
                
        # Send follow up message
        await message.reply_text("Tʜᴇ ғɪʟᴇ ʜᴀs ʙᴇᴇɴ ɢᴏɴᴇ ! Cʟɪᴄᴋ ɢɪᴠᴇɴ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ɪᴛ ᴀɢᴀɪɴ.", reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Single file handling
    type_, grp_id, file_id = mc.split("_", 2)
    files_ = await get_file_details(file_id) # AWAIT जोड़ा गया
    if not files_:<br>        return await message.reply('No Such File Exist!')
    settings = await get_settings(int(grp_id)) # AWAIT जोड़ा गया
    if type_ != 'shortlink' and settings['shortlink'] and not is_prem:
        # ... (shortlink logic is fine)
        return
            
    # ... (caption formatting, button creation, and file sending logic is fine)
    
    # Auto delete logic for single file
    time = get_readable_time(PM_FILE_DELETE_TIME)
    msg = await vp.reply(f"Nᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇ ɪɴ {time} ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛs. Sᴀᴠᴇ ᴛʜᴇ ғɪʟᴇ ᴛᴏ sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ")
    
    await asyncio.sleep(PM_FILE_DELETE_TIME)
    btns = [[InlineKeyboardButton('ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ', callback_data=f"get_del_file#{grp_id}#{file_id}")]]
    
    # Safer deletion of messages vp and msg
    try:
        await msg.delete()
        await vp.delete()
    except Exception as e:
        logger.warning(f"Failed to delete single file messages: {e}")
        
    await vp.reply("Tʜᴇ ғɪʟᴇ ʜᴀs ʙᴇᴇɴ ɢᴏɴᴇ ! Cʟɪᴄᴋ ɢɪᴠᴇɴ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ɪᴛ ᴀɢᴀɪɴ.", reply_markup=InlineKeyboardMarkup(btns))


@Client.on_message(filters.command('link'))
async def link(bot, message):
    # ... (link command logic is fine)
    pass


@Client.on_message(filters.command('index_channels'))
async def channels_info(bot, message):
    # ... (channels_info logic is fine)
    pass


@Client.on_message(filters.command('stats'))
async def stats(bot, message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.delete()
        return
        
    # Await DB calls
    files = await db_count_documents()
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    prm = await db.get_premium_count()
    used_files_db_size = get_size(await db.get_files_db_size())
    used_data_db_size = get_size(await db.get_data_db_size())

    if SECOND_FILES_DATABASE_URL:
        secnd_files_db_used_size = get_size(await db.get_second_files_db_size())
        secnd_files = await second_db_count_documents()
    else:
        secnd_files_db_used_size = '-'
        secnd_files = '-'

    uptime = get_readable_time(time_now() - temp.START_TIME)
    await message.reply_text(script.STATUS_TXT.format(users, prm, chats, used_data_db_size, files, used_files_db_size, secnd_files, secnd_files_db_used_size, uptime))    


# ... (rest of the command handlers)

@Client.on_message(filters.command('myplan') & filters.private)
async def myplan(client, message):
    if not IS_PREMIUM:
        return await message.reply('Premium feature was disabled by admin')
    mp = await db.get_plan(message.from_user.id) # AWAIT जोड़ा गया
    if not await is_premium(message.from_user.id, client):
        # ... (not premium logic)
        return
    await message.reply(f"You activated {mp['plan']} plan\nExpire: {mp['expire'].strftime('%Y.%m.%d %H:%M:%S')}")


@Client.on_message(filters.command('plan') & filters.private)
async def plan(client, message):
    # ... (plan logic is fine)
    pass


@Client.on_message(filters.command('add_prm') & filters.user(ADMINS))
async def add_prm(bot, message):
    # ... (input validation)
    
    if not await is_premium(user.id, bot):
        mp = await db.get_plan(user.id) # AWAIT जोड़ा गया
        ex = datetime.now(timezone.utc) + timedelta(days=d) # Timezone-aware
        mp['expire'] = ex
        mp['plan'] = f'{d} days'
        mp['premium'] = True
        await db.update_plan(user.id, mp) # AWAIT जोड़ा गया
        # ... (rest of success logic)
    # ... (else logic is fine)


@Client.on_message(filters.command('rm_prm') & filters.user(ADMINS))
async def rm_prm(bot, message):
    # ... (input validation)
    
    if not await is_premium(user.id, bot):
        # ... (not premium logic)
        pass
    else:
        mp = await db.get_plan(user.id) # AWAIT जोड़ा गया
        mp['expire'] = ''
        mp['plan'] = ''
        mp['premium'] = False
        await db.update_plan(user.id, mp) # AWAIT जोड़ा गया
        # ... (rest of removal logic is fine)


# ... (prm_list, set_fsub, set_req_fsub, off/on_auto_filter/pm_search)
# इन सभी एडमिन कमांड्स में db.update_bot_sttgs() को await db.update_bot_sttgs() होना चाहिए।
