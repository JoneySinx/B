import random
import os
import sys
import logging # Logging जोड़ा गया
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatJoinRequest
from hydrogram.errors.exceptions.bad_request_400 import MessageTooLong
from info import ADMINS, LOG_CHANNEL, PICS, SUPPORT_LINK, UPDATES_LINK
from database.users_chats_db import db
from utils import temp, get_settings
from Script import script

logger = logging.getLogger(__name__) # Logger initialization

async def del_stk(s):
    await asyncio.sleep(3)
    try:
        await s.delete()
    except Exception:
        pass

@Client.on_chat_member_updated()
async def welcome(bot, message):
    if message.chat.type not in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        return
    
    if message.new_chat_member and not message.old_chat_member:
        if message.new_chat_member.user.id == temp.ME:
            # Bot added to group logic
            # ... (reply is fine)
            if not await db.get_chat(message.chat.id):
                total = await bot.get_chat_members_count(message.chat.id)
                username = f'@{message.chat.username}' if message.chat.username else 'Private'
                await bot.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))       
                await db.add_chat(message.chat.id, message.chat.title) # AWAIT DB call
            return
        
        settings = await get_settings(message.chat.id) # AWAIT DB call
        if settings["welcome"]:
            WELCOME = settings['welcome_text']
            welcome_msg = WELCOME.format(
                mention = message.new_chat_member.user.mention,
                title = message.chat.title
            )
            await bot.send_message(chat_id=message.chat.id, text=welcome_msg)


@Client.on_message(filters.command('restart') & filters.user(ADMINS))
async def restart_bot(bot, message):
    msg = await message.reply("Restarting...")
    with open('restart.txt', 'w+') as file:
        file.write(f"{msg.chat.id}\n{msg.id}")
    os.execl(sys.executable, sys.executable, "bot.py")

@Client.on_message(filters.command('leave') & filters.user(ADMINS))
async def leave_a_chat(bot, message):
    if len(message.command) == 1:
        return await message.reply('Give me a chat ID')
    r = message.text.split(None)
    # ... (reason parsing is fine)
    
    try:
        chat = int(chat)
    except ValueError:
        return await message.reply('Give me a valid chat ID')
    
    try:
        buttons = [[InlineKeyboardButton('Support Group', url=SUPPORT_LINK)]]
        reply_markup=InlineKeyboardMarkup(buttons)
        
        await bot.send_message(
            chat_id=chat,
            text=f'Hello Friends,\nMy owner has told me to leave from group so i go! If you need add me again contact my support group.\nReason - <code>{reason}</code>',
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await bot.leave_chat(chat)
        await message.reply(f"<b>✅️ Successfully bot left from this group - `{chat}`</b>", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error leaving chat {chat}: {e}")
        await message.reply(f'Error - {e}')

@Client.on_message(filters.command('ban_grp') & filters.user(ADMINS))
async def disable_chat(bot, message):
    # ... (argument parsing is fine)
    
    try:
        chat_ = int(chat)
    except ValueError:
        return await message.reply('Give me a valid chat ID')
    
    cha_t = await db.get_chat(int(chat_)) # AWAIT DB call
    if not cha_t:
        return await message.reply("Chat not found in database")
    if cha_t.get('is_disabled'):
        return await message.reply(f"This chat is already disabled.\nReason - <code>{cha_t.get('reason')}</code>", parse_mode=enums.ParseMode.HTML)
        
    await db.disable_chat(int(chat_), reason) # AWAIT DB call
    temp.BANNED_CHATS.append(int(chat_))
    await message.reply('Chat successfully disabled')
    
    # Attempt to leave and send message
    try:
        # ... (send message logic is fine)
        await bot.send_message(
            chat_id=chat_, 
            text=f'Hello Friends,\nMy owner has told me to leave from group so i go! If you need add me again contact my support group.\nReason - <code>{reason}</code>',
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        await bot.leave_chat(chat_)
    except Exception as e:
        logger.error(f"Error sending message/leaving disabled chat {chat_}: {e}")
        await message.reply(f"Error - {e}")

@Client.on_message(filters.command('unban_grp') & filters.user(ADMINS))
async def re_enable_chat(bot, message):
    # ... (argument parsing is fine)
    
    try:
        chat_ = int(chat)
    except ValueError:
        return await message.reply('Give me a valid chat ID')
    
    sts = await db.get_chat(int(chat)) # AWAIT DB call
    if not sts:
        return await message.reply("Chat not found in database")
    if not sts.get('is_disabled'):
        return await message.reply('This chat is not yet disabled.')
        
    await db.re_enable_chat(int(chat_)) # AWAIT DB call
    temp.BANNED_CHATS.remove(int(chat_))
    await message.reply("Chat successfully re-enabled")

# ... (gen_invite_link logic is fine)

@Client.on_message(filters.command('ban_user') & filters.user(ADMINS))
async def ban_a_user(bot, message):
    # ... (argument parsing is fine)
    
    try:
        k = await bot.get_users(chat)
    except Exception as e:
        return await message.reply(f'Error - {e}')
    else:
        if k.id in ADMINS:
            return await message.reply('You ADMINS')
        jar = await db.get_ban_status(k.id) # AWAIT DB call
        if jar['is_banned']:
            return await message.reply(f"{k.mention} is already banned.\nReason - <code>{jar['ban_reason']}</code>", parse_mode=enums.ParseMode.HTML)
        await db.ban_user(k.id, reason) # AWAIT DB call
        temp.BANNED_USERS.append(k.id)
        await message.reply(f"Successfully banned {k.mention}")
   
@Client.on_message(filters.command('unban_user') & filters.user(ADMINS))
async def unban_a_user(bot, message):
    # ... (argument parsing is fine)
    
    try:
        k = await bot.get_users(chat)
    except Exception as e:
        return await message.reply(f'Error - {e}')
    else:
        jar = await db.get_ban_status(k.id) # AWAIT DB call
        if not jar['is_banned']:
            return await message.reply(f"{k.mention} is not yet banned.")
        await db.remove_ban(k.id) # AWAIT DB call
        temp.BANNED_USERS.remove(k.id)
        await message.reply(f"Successfully unbanned {k.mention}")
    
@Client.on_message(filters.command('users') & filters.user(ADMINS))
async def list_users(bot, message):
    raju = await message.reply('Getting list of users')
    users = await db.get_all_users() # AWAIT DB call
    out = "Users saved in database are:\n\n"
    # ... (content creation is fine)
    
    # Improved list sending logic
    if len(out) > 4096:
        try:
            with open('users.txt', 'w+') as outfile:
                outfile.write(out)
            await message.reply_document('users.txt', caption="List of users")
            await raju.delete()
        except Exception as e:
            logger.error(f"Failed to send users list file: {e}")
            await message.reply("Failed to send user list as file.")
        finally:
            if os.path.exists('users.txt'):
                os.remove('users.txt')
    else:
        await raju.edit_text(out)

@Client.on_message(filters.command('chats') & filters.user(ADMINS))
async def list_chats(bot, message):
    raju = await message.reply('Getting list of chats')
    chats = await db.get_all_chats() # AWAIT DB call
    out = "Chats saved in database are:\n\n"
    # ... (content creation is fine)
    
    # Improved list sending logic
    if len(out) > 4096:
        try:
            with open('chats.txt', 'w+') as outfile:
                outfile.write(out)
            await message.reply_document('chats.txt', caption="List of chats")
            await raju.delete()
        except Exception as e:
            logger.error(f"Failed to send chats list file: {e}")
            await message.reply("Failed to send chat list as file.")
        finally:
            if os.path.exists('chats.txt'):
                os.remove('chats.txt')
    else:
        await raju.edit_text(out)

@Client.on_chat_join_request()
async def join_reqs(client, message: ChatJoinRequest):
    stg = await db.get_bot_sttgs() # AWAIT DB call
    if stg and message.chat.id == int(stg.get('REQUEST_FORCE_SUB_CHANNELS', 0)):
        if not await db.find_join_req(message.from_user.id): # AWAIT DB call
            await db.add_join_req(message.from_user.id) # AWAIT DB call

@Client.on_message(filters.command("delreq") & filters.private & filters.user(ADMINS))
async def del_requests(client, message):
    await db.del_join_req() # AWAIT DB call
    await message.reply('Deleted join requests')
