import time
import asyncio
import datetime
import logging
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from hydrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

# Local imports
from database.users_chats_db import db
from info import ADMINS
from utils import broadcast_messages, groups_broadcast_messages, temp, get_readable_time

logger = logging.getLogger(__name__)
lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^broadcast_cancel'))
async def broadcast_cancel(bot, query):
    _, ident = query.data.split("#")
    if ident == 'users':
        await query.message.edit("Trying to cancel users broadcasting...")
        temp.USERS_CANCEL = True
    elif ident == 'groups':
        temp.GROUPS_CANCEL = True
        await query.message.edit("Trying to cancel groups broadcasting...")

@Client.on_message(filters.command(["broadcast", "pin_broadcast"]) & filters.user(ADMINS) & filters.reply)
async def users_broadcast(bot, message):
    if lock.locked():
        return await message.reply('Currently broadcast processing, Wait for complete.')

    pin = message.command[0] == 'pin_broadcast'
    
    # DB calls should be awaited
    total_users = await db.total_users_count()
    b_msg = message.reply_to_message
    b_sts = await message.reply_text(text='Broadcasting your users messages...')
    
    start_time = time.time()
    done = 0
    failed = 0
    success = 0
    last_update_time = time.time()

    async with lock:
        # मोटर (Motor) कर्सर का उपयोग करें (मेमोरी बचाने के लिए)
        # यह मानता है कि db.get_all_users() एक मोटर कर्सर देता है
        users_cursor = await db.get_all_users() 
        
        async for user in users_cursor:
            # चेक करें कि क्या यूजर ने कैंसिल किया है
            if temp.USERS_CANCEL:
                temp.USERS_CANCEL = False
                time_taken = get_readable_time(time.time()-start_time)
                await b_sts.edit(f"Users broadcast Cancelled!\nCompleted in {time_taken}\n\nTotal Users: <code>{total_users}</code>\nCompleted: <code>{done} / {total_users}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")
                return

            try:
                sts = await broadcast_messages(int(user['id']), b_msg, pin)
                if sts == 'Success':
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            
            done += 1
            
            # हर 20 यूजर की जगह, हर 5 सेकंड में अपडेट करें (FloodWait से बचने के लिए)
            if time.time() - last_update_time > 5:
                time_taken = get_readable_time(time.time()-start_time)
                btn = [[InlineKeyboardButton('CANCEL', callback_data='broadcast_cancel#users')]]
                try:
                    await b_sts.edit(
                        f"Users broadcast in progress...\n\nTotal Users: <code>{total_users}</code>\nCompleted: <code>{done} / {total_users}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>\nTime Taken: {time_taken}", 
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                    last_update_time = time.time()
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    pass

        time_taken = get_readable_time(time.time()-start_time)
        await b_sts.edit(f"Users broadcast completed.\nCompleted in {time_taken}\n\nTotal Users: <code>{total_users}</code>\nCompleted: <code>{done} / {total_users}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")


@Client.on_message(filters.command(["grp_broadcast", "pin_grp_broadcast"]) & filters.user(ADMINS) & filters.reply)
async def groups_broadcast(bot, message):
    if lock.locked():
        return await message.reply('Currently broadcast processing, Wait for complete.')

    pin = message.command[0] == 'pin_grp_broadcast'

    total_chats = await db.total_chat_count()
    b_msg = message.reply_to_message
    b_sts = await message.reply_text(text='Broadcasting your groups messages...')
    
    start_time = time.time()
    done = 0
    failed = 0
    success = 0
    last_update_time = time.time()

    async with lock:
        # मोटर (Motor) कर्सर का उपयोग करें
        chats_cursor = await db.get_all_chats()
        
        async for chat in chats_cursor:
            if temp.GROUPS_CANCEL:
                temp.GROUPS_CANCEL = False
                time_taken = get_readable_time(time.time()-start_time)
                await b_sts.edit(f"Groups broadcast Cancelled!\nCompleted in {time_taken}\n\nTotal Groups: <code>{total_chats}</code>\nCompleted: <code>{done} / {total_chats}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")
                return

            try:
                sts = await groups_broadcast_messages(int(chat['id']), b_msg, pin)
                if sts == 'Success':
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            
            done += 1
            
            # समय आधारित अपडेट (Time based update)
            if time.time() - last_update_time > 5:
                time_taken = get_readable_time(time.time()-start_time)
                btn = [[InlineKeyboardButton('CANCEL', callback_data='broadcast_cancel#groups')]]
                try:
                    await b_sts.edit(
                        f"Groups broadcast in progress...\n\nTotal Groups: <code>{total_chats}</code>\nCompleted: <code>{done} / {total_chats}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>\nTime Taken: {time_taken}", 
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                    last_update_time = time.time()
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    pass

        time_taken = get_readable_time(time.time()-start_time)
        await b_sts.edit(f"Groups broadcast completed.\nCompleted in {time_taken}\n\nTotal Groups: <code>{total_chats}</code>\nCompleted: <code>{done} / {total_chats}</code>\nSuccess: <code>{success}</code>\nFailed: <code>{failed}</code>")
