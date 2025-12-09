import os
import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from time import time as time_now
from time import monotonic

from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from hydrogram.errors import MessageTooLong

from Script import script
from database.ia_filterdb import db_count_documents, delete_files
from database.users_chats_db import db
from info import (
    IS_PREMIUM, PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME, URL, BIN_CHANNEL, 
    STICKERS, INDEX_CHANNELS, ADMINS, DELETE_TIME, 
    SUPPORT_LINK, UPDATES_LINK, LOG_CHANNEL, PICS, IS_STREAM, REACTIONS, PM_FILE_DELETE_TIME
)
from utils import (
    is_premium, upload_image, get_settings, get_size, is_subscribed, 
    is_check_admin, get_shortlink, get_verify_status, update_verify_status, 
    get_readable_time, get_wish, temp
)

logger = logging.getLogger(__name__)

async def get_grp_stg(group_id):
    settings = await get_settings(group_id)
    btn = [[
        InlineKeyboardButton('Edit File Caption', callback_data=f'caption_setgs#{group_id}')
    ],[
        InlineKeyboardButton('Edit Welcome', callback_data=f'welcome_setgs#{group_id}')
    ],[
        InlineKeyboardButton('Edit tutorial link', callback_data=f'tutorial_setgs#{group_id}')
    ],[
        InlineKeyboardButton(f'Spelling Check {"✅" if settings["spell_check"] else "❌"}', callback_data=f'bool_setgs#spell_check#{settings["spell_check"]}#{group_id}')
    ],[
        InlineKeyboardButton(f"Auto Delete - {get_readable_time(DELETE_TIME)}" if settings["auto_delete"] else "Auto Delete ❌", callback_data=f'bool_setgs#auto_delete#{settings["auto_delete"]}#{group_id}')
    ],[
        InlineKeyboardButton(f'Welcome {"✅" if settings["welcome"] else "❌"}', callback_data=f'bool_setgs#welcome#{settings["welcome"]}#{group_id}')
    ],[
        InlineKeyboardButton(f"Result Page - Link" if settings["links"] else "Result Page - Button", callback_data=f'bool_setgs#links#{settings["links"]}#{group_id}')
    ]]
    return btn

async def del_stk(s):
    await asyncio.sleep(3)
    try: await s.delete()
    except: pass

@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            username = f'@{message.chat.username}' if message.chat.username else 'Private'
            await client.send_message(LOG_CHANNEL, script.NEW_GROUP_TXT.format(message.chat.title, message.chat.id, username, total))       
            await db.add_chat(message.chat.id, message.chat.title)
        
        wish = get_wish()
        user = message.from_user.mention if message.from_user else "Dear"
        btn = [[
            InlineKeyboardButton('⚡️ ᴜᴘᴅᴀᴛᴇs ᴄʜᴀɴɴᴇʟ ⚡️', url=UPDATES_LINK),
            InlineKeyboardButton('💡 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ 💡', url=SUPPORT_LINK)
        ]]
        await message.reply(text=f"<b>ʜᴇʏ {user}, <i>{wish}</i>\nʜᴏᴡ ᴄᴀɴ ɪ ʜᴇʟᴘ ʏᴏᴜ??</b>", reply_markup=InlineKeyboardMarkup(btn))
        return 
        
    try: await message.react(emoji=random.choice(REACTIONS), big=True)
    except: pass

    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.NEW_USER_TXT.format(message.from_user.mention, message.from_user.id))

    if (len(message.command) != 2) or (len(message.command) == 2 and message.command[1] == 'start'):
        buttons = [[
            InlineKeyboardButton('👨‍🚒 Help', callback_data='help'),
            InlineKeyboardButton('📚 Status 📊', callback_data='stats')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, get_wish()),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return

    mc = message.command[1]

    if mc == 'premium':
        return await plan(client, message)
    
    if mc.startswith('settings'):
        _, group_id = message.command[1].split("_")
        if not await is_check_admin(client, int(group_id), message.from_user.id):
            return await message.reply("You not admin in this group.")
        btn = await get_grp_stg(int(group_id))
        chat = await client.get_chat(int(group_id))
        return await message.reply(f"Change your settings for <b>'{chat.title}'</b> as your wish. ⚙", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

    btn = await is_subscribed(client, message)
    if btn:
        btn.append([InlineKeyboardButton("🔁 Try Again 🔁", callback_data=f"checksub#{mc}")])
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=f"👋 Hello {message.from_user.mention},\n\nPlease join my 'Updates Channel' and try again. 😇",
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        return 
        
    if mc.startswith('all'):
        try: _, grp_id, key = mc.split("_", 2)
        except ValueError: return await message.reply("Invalid link format")
            
        files = temp.FILES.get(key)
        if not files: return await message.reply('No Such All Files Exist! (Link expired or bot restarted)')
            
        settings = await get_settings(int(grp_id))
        total_files = await message.reply(f"<b><i>🗂 Total files - <code>{len(files)}</code></i></b>", parse_mode=enums.ParseMode.HTML)
        
        file_ids = [total_files.id]
        
        for file in files:
            CAPTION = settings['caption']
            f_caption = CAPTION.format(file_name=file['file_name'], file_size=get_size(file['file_size']), file_caption=file['caption'])      
            btn = [[InlineKeyboardButton('🙅 Close', callback_data='close_data')]]
            if IS_STREAM:
                btn.insert(0, [InlineKeyboardButton("🚀 Watch And Download ⚡", callback_data=f"stream#{file['_id']}")])

            msg = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=file['_id'],
                caption=f_caption,
                protect_content=False,
                reply_markup=InlineKeyboardMarkup(btn)
            )
            file_ids.append(msg.id)

        time = get_readable_time(PM_FILE_DELETE_TIME)
        vp = await message.reply(f"Nᴏᴛᴇ: Tʜɪs ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇ ɪɴ {time} ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛs. Sᴀᴠᴇ ᴛʜᴇ ғɪʟᴇs ᴛᴏ sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ")
        file_ids.append(vp.id)
        
        await asyncio.sleep(PM_FILE_DELETE_TIME)
        buttons = [[InlineKeyboardButton('ɢᴇᴛ ғɪʟᴇs ᴀɢᴀɪɴ', callback_data=f"get_del_send_all_files#{grp_id}#{key}")]] 
        
        for i in range(0, len(file_ids), 100):
            try: await client.delete_messages(chat_id=message.chat.id, message_ids=file_ids[i:i+100])
            except: pass
            
        gone_msg = await message.reply("Tʜᴇ ғɪʟᴇ ʜᴀs ʙᴇᴇɴ ɢᴏɴᴇ ! Cʟɪᴄᴋ ɢɪᴠᴇɴ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ɪᴛ ᴀɢᴀɪɴ.", reply_markup=InlineKeyboardMarkup(buttons))
        
        # 12 Hours Delete
        await asyncio.sleep(43200)
        try: await gone_msg.delete()
        except: pass
        return

    try: type_, grp_id, file_id = mc.split("_", 2)
    except ValueError: return await message.reply("Invalid Command")
    
    from database.ia_filterdb import get_file_details
    files_ = await get_file_details(file_id)
    if not files_: return await message.reply('No Such File Exist!')
        
    settings = await get_settings(int(grp_id))
    CAPTION = settings['caption']
    f_caption = CAPTION.format(file_name = files_['file_name'], file_size = get_size(files_['file_size']), file_caption=files_['caption'])
    
    btn = [[InlineKeyboardButton('🙅 Close', callback_data='close_data')]]
    if IS_STREAM:
        btn.insert(0, [InlineKeyboardButton("🚀 Watch And Download ⚡", callback_data=f"stream#{file_id}")])
    
    vp = await client.send_cached_media(
        chat_id=message.from_user.id,
        file_id=file_id,
        caption=f_caption,
        protect_content=False,
        reply_markup=InlineKeyboardMarkup(btn)
    )
    
    time = get_readable_time(PM_FILE_DELETE_TIME)
    msg = await vp.reply(f"Nᴏᴛᴇ: Tʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇ ɪɴ {time} ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛs. Sᴀᴠᴇ ᴛʜᴇ ғɪʟᴇ ᴛᴏ sᴏᴍᴇᴡʜᴇʀᴇ ᴇʟsᴇ")

    await asyncio.sleep(PM_FILE_DELETE_TIME)
    try:
        await msg.delete()
        await vp.delete()
    except: pass

    btns = [[InlineKeyboardButton('ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ', callback_data=f"get_del_file#{grp_id}#{file_id}")]]
    gone_msg = await message.reply("Tʜᴇ ғɪʟᴇ ʜᴀs ʙᴇᴇɴ ɢᴏɴᴇ ! Cʟɪᴄᴋ ɢɪᴠᴇɴ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ɪᴛ ᴀɢᴀɪɴ.", reply_markup=InlineKeyboardMarkup(btns))
    
    # 12 Hours Delete
    await asyncio.sleep(43200)
    try: await gone_msg.delete()
    except: pass

@Client.on_message(filters.command('delete') & filters.user(ADMINS))
async def delete_file(bot, message):
    try: query = message.text.split(" ", 1)[1]
    except: return await message.reply_text("Command Incomplete!\nUsage: /delete query")
    btn = [[InlineKeyboardButton("YES", callback_data=f"delete_{query}")],[InlineKeyboardButton("CLOSE", callback_data="close_data")]]
    await message.reply_text(f"Do you want to delete all files matching: <b>{query}</b> ?", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command('delete_all') & filters.user(ADMINS))
async def delete_all_index(bot, message):
    btn = [[InlineKeyboardButton("YES", callback_data="delete_all")],[InlineKeyboardButton("CLOSE", callback_data="close_data")]]
    await message.reply_text("Do you want to delete <b>ALL</b> indexed files? This action cannot be undone.", reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command('stats'))
async def stats(bot, message):
    if message.from_user.id not in ADMINS:
        await message.delete()
        return
    files = await db_count_documents()
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    prm = await db.get_premium_count()
    used_bytes, free_bytes = await db.get_db_size()
    used = get_size(used_bytes)
    free = get_size(free_bytes)
    uptime = get_readable_time(time_now() - temp.START_TIME)
    await message.reply_text(script.STATUS_TXT.format(files, users, chats, prm, used, free, uptime))    

# ... (Include other commands: link, index_channels, img_2_link, ping, plan, myplan, add_prm, rm_prm, prm_list, set_fsub, off/on_auto_filter, off/on_pm_search, restart, leave, users, chats, ban_user, unban_user, ban, mute, unban/unmute) ...
# I will include the other commands below for a complete file.

@Client.on_message(filters.command('link'))
async def link(bot, message):
    msg = message.reply_to_message
    if not msg: return await message.reply('Reply to media')
    try:
        media = getattr(msg, msg.media.value)
        msg = await bot.send_cached_media(chat_id=BIN_CHANNEL, file_id=media.file_id)
        from info import URL as SITE_URL
        base_url = SITE_URL[:-1] if SITE_URL.endswith('/') else SITE_URL
        watch = f"{base_url}/watch/{msg.id}"
        download = f"{base_url}/download/{msg.id}"
        btn=[[InlineKeyboardButton("ᴡᴀᴛᴄʜ ᴏɴʟɪɴᴇ", url=watch), InlineKeyboardButton("ꜰᴀsᴛ ᴅᴏᴡɴʟᴏᴀᴅ", url=download)],[InlineKeyboardButton('🙅 Close', callback_data='close_data')]]
        await message.reply('Here is your link', reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await message.reply(f'Error: {e}')

@Client.on_message(filters.command('index_channels'))
async def channels_info(bot, message):
    if message.from_user.id not in ADMINS:
        await message.delete()
        return
    # Now uses the dynamic index channel logic from utils if implemented, or Env
    # For now, keeping env logic as utils.py doesn't have the dynamic getter unless we added it back
    ids = INDEX_CHANNELS
    if not ids: return await message.reply("Not set INDEX_CHANNELS")
    text = '**Indexed Channels:**\n\n'
    for id in ids:
        try:
            chat = await bot.get_chat(id)
            text += f'{chat.title}\n'
        except: text += f'{id} (Unknown)\n'
    text += f'\n**Total:** {len(ids)}'
    await message.reply(text)

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    group_id = message.chat.id
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        if not await is_check_admin(client, group_id, message.from_user.id):
            return await message.reply_text('You not admin in this group.')
        btn = [[InlineKeyboardButton("Open Here", callback_data='open_group_settings'), InlineKeyboardButton("Open In PM", callback_data='open_pm_settings')]]
        await message.reply_text('Where do you want to open the settings menu?', reply_markup=InlineKeyboardMarkup(btn))
    elif message.chat.type == enums.ChatType.PRIVATE:
        cons = await db.get_connections(message.from_user.id)
        if not cons: return await message.reply_text("No groups found! Use this command group and open in PM")
        buttons = []
        for con in cons:
            try:
                chat = await client.get_chat(con)
                buttons.append([InlineKeyboardButton(text=chat.title, callback_data=f'back_setgs#{chat.id}')])
            except: pass
        await message.reply_text('Select the group whose settings you want to change.', reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command('connect'))
async def connect(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        group_id = message.chat.id
        await db.add_connect(group_id, message.from_user.id)
        await message.reply_text('Successfully connected this group to PM.')
    elif message.chat.type == enums.ChatType.PRIVATE:
        if len(message.command) > 1:
            group_id = message.command[1]
            try:
                if not await is_check_admin(client, int(group_id), message.from_user.id):
                    return await message.reply_text('You not admin in this group.')
                chat = await client.get_chat(int(group_id))
                await db.add_connect(int(group_id), message.from_user.id)
                await message.reply_text(f'Successfully connected {chat.title} group to PM')
            except Exception as e: await message.reply_text(f'Error: {e}')
        else: await message.reply_text('Usage: /connect group_id\nor use /connect in group')

@Client.on_message(filters.command('img_2_link'))
async def img_2_link(bot, message):
    reply_to_message = message.reply_to_message
    if not reply_to_message: return await message.reply('Reply to any photo')
    file = reply_to_message.photo
    if file is None: return await message.reply('Invalid media.')
    text = await message.reply_text(text="ᴘʀᴏᴄᴇssɪɴɢ....")   
    path = await reply_to_message.download()  
    response = upload_image(path)
    try: os.remove(path)
    except: pass
    if not response: return await text.edit_text(text="Upload failed!")
    await text.edit_text(f"<b>❤️ Your link ready 👇\n\n{response}</b>", disable_web_page_preview=True)

@Client.on_message(filters.command('ping'))
async def ping(client, message):
    start_time = monotonic()
    msg = await message.reply("👀")
    end_time = monotonic()
    await msg.edit(f'{round((end_time - start_time) * 1000)} ms')

# --- PREMIUM COMMANDS ---
@Client.on_message(filters.command('plan') & filters.private)
async def plan(client, message):
    if not IS_PREMIUM: return await message.reply('Premium feature was disabled by admin')
    btn = [[InlineKeyboardButton('Activate Plan', callback_data='activate_plan')]]
    await message.reply(script.PLAN_TXT.format(PRE_DAY_AMOUNT, RECEIPT_SEND_USERNAME), reply_markup=InlineKeyboardMarkup(btn))

@Client.on_message(filters.command('myplan') & filters.private)
async def myplan(client, message):
    if not IS_PREMIUM: return await message.reply('Premium feature is currently disabled by Admin.')
    if message.from_user.id in ADMINS: return await message.reply(f"<b>👑 Hello Admin {message.from_user.mention}!</b>\n\nYou have <b>Lifetime Premium Access</b> because you are the owner. 😎")
    mp = await db.get_plan(message.from_user.id)
    is_prem = await is_premium(message.from_user.id, client)
    if not is_prem:
        btn = [[InlineKeyboardButton('💎 Activate Plan', callback_data='activate_plan')]]
        return await message.reply("<b>❌ No Active Plan</b>\n\nYou are currently a free user. Upgrade to Premium to remove ads and unlock features.", reply_markup=InlineKeyboardMarkup(btn))
    expire_date = mp.get('expire')
    readable_date = expire_date.strftime('%d %B %Y, %I:%M %p') if isinstance(expire_date, datetime) else "Unknown"
    await message.reply(f"<b>💎 Premium Status</b>\n\n👤 <b>User:</b> {message.from_user.mention}\n📅 <b>Plan:</b> {mp.get('plan', 'Custom')}\n⏳ <b>Expires on:</b> <code>{readable_date}</code>")

@Client.on_message(filters.command('add_prm') & filters.user(ADMINS))
async def add_prm(bot, message):
    if not IS_PREMIUM: return await message.reply('Premium feature was disabled')
    try: _, user_id, d = message.text.split(' ')
    except: return await message.reply('Usage: /add_prm user_id 1d')
    try: d = int(d[:-1])
    except: return await message.reply('Not valid days')
    try: user = await bot.get_users(user_id)
    except Exception as e: return await message.reply(f'Error: {e}')
    if user.id in ADMINS: return await message.reply('ADMINS is already premium')
    if not await is_premium(user.id, bot):
        mp = await db.get_plan(user.id)
        ex = datetime.now(timezone.utc) + timedelta(days=d)
        mp['expire'] = ex
        mp['plan'] = f'{d} days'
        mp['premium'] = True
        await db.update_plan(user.id, mp)
        await bot.send_message(LOG_CHANNEL, f"#Premium_Added\n\n👤 <b>User:</b> {user.mention} (`{user.id}`)\n🗓 <b>Plan:</b> {d} Days\n⏰ <b>Expires:</b> {ex.strftime('%d/%m/%Y')}\n👮‍♂️ <b>Added By:</b> {message.from_user.mention}")
        await message.reply(f"Given premium to {user.mention}\nExpire: {ex.strftime('%d/%m/%Y')}")
        try: await bot.send_message(user.id, f"Your now premium user\nExpire: {ex.strftime('%d/%m/%Y')}")
        except: pass
    else: await message.reply(f"{user.mention} is already premium user")

@Client.on_message(filters.command('rm_prm') & filters.user(ADMINS))
async def rm_prm(bot, message):
    if not IS_PREMIUM: return await message.reply('Premium feature was disabled')
    try: _, user_id = message.text.split(' ')
    except: return await message.reply('Usage: /rm_prm user_id')
    try: user = await bot.get_users(user_id)
    except Exception as e: return await message.reply(f'Error: {e}')
    if user.id in ADMINS: return await message.reply('ADMINS is already premium')
    if not await is_premium(user.id, bot): await message.reply(f"{user.mention} is not premium user")
    else:
        mp = await db.get_plan(user.id)
        mp['expire'] = ''
        mp['plan'] = ''
        mp['premium'] = False
        await db.update_plan(user.id, mp)
        await bot.send_message(LOG_CHANNEL, f"#Premium_Removed\n\n👤 <b>User:</b> {user.mention} (`{user.id}`)\n👮‍♂️ <b>Removed By:</b> {message.from_user.mention}")
        await message.reply(f"{user.mention} is no longer premium user")
        try: await bot.send_message(user.id, "Your premium plan was removed by admin")
        except: pass

@Client.on_message(filters.command('prm_list') & filters.user(ADMINS))
async def prm_list(bot, message):
    if not IS_PREMIUM: return await message.reply('Premium feature was disabled')
    tx = await message.reply('Getting list of premium users...')
    out = "<b>💎 Premium Users:</b>\n\n"
    count = 0
    async for user in await db.get_premium_users():
        if user['status']['premium']:
            count += 1
            try: u = await bot.get_users(user['id']); mention = u.mention
            except: mention = "Unknown User"
            expiry = user['status']['expire']
            exp_str = expiry.strftime('%d/%m/%Y') if isinstance(expiry, datetime) else "Unlimited"
            out += f"{count}. {mention} (`{user['id']}`) | ⏳ Exp: {exp_str}\n"
    if count == 0: await tx.edit_text("No premium users found.")
    else:
        try: await tx.edit_text(out)
        except MessageTooLong:
            with open('premium_users.txt', 'w+') as outfile: outfile.write(out.replace('<b>', '').replace('</b>', '').replace('`', ''))
            await message.reply_document('premium_users.txt', caption="List of Premium Users")
            os.remove('premium_users.txt')
            await tx.delete()

# --- ADMIN TOGGLES ---
@Client.on_message(filters.command(['add_fsub', 'set_fsub']) & filters.user(ADMINS))
async def add_fsub_cmd(client, message):
    if len(message.command) < 2: return await message.reply("<b>Usage:</b> <code>/add_fsub -100xxxxxx</code>")
    try:
        ids = message.text.split(' ', 1)[1]
        for channel_id in ids.split():
            try:
                chat = await client.get_chat(int(channel_id))
                await client.get_chat_member(int(channel_id), "me")
            except Exception as e: return await message.reply(f"❌ <b>Error:</b> I am not admin in `{channel_id}` or invalid ID.\nError: {e}")
        await db.update_bot_sttgs('FORCE_SUB_CHANNELS', ids)
        await message.reply(f"<b>✅ Force Subscribe Channel Set!</b>\nChannels: `{ids}`")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command(['del_fsub', 'remove_fsub']) & filters.user(ADMINS))
async def del_fsub_cmd(client, message):
    await db.update_bot_sttgs('FORCE_SUB_CHANNELS', "")
    await message.reply("<b>🗑 Force Subscribe Removed!</b>")

@Client.on_message(filters.command(['view_fsub', 'get_fsub']) & filters.user(ADMINS))
async def view_fsub_cmd(client, message):
    stg = await db.get_bot_sttgs()
    if stg and stg.get('FORCE_SUB_CHANNELS'): await message.reply(f"<b>📢 Current F-Sub Channels:</b>\n`{stg['FORCE_SUB_CHANNELS']}`")
    else: await message.reply("<b>❌ No Force Subscribe Channel Set.</b>")

@Client.on_message(filters.command('off_auto_filter') & filters.user(ADMINS))
async def off_auto_filter(bot, message):
    await db.update_bot_sttgs('AUTO_FILTER', False)
    await message.reply('Successfully turned off auto filter')

@Client.on_message(filters.command('on_auto_filter') & filters.user(ADMINS))
async def on_auto_filter(bot, message):
    await db.update_bot_sttgs('AUTO_FILTER', True)
    await message.reply('Successfully turned on auto filter')

@Client.on_message(filters.command('off_pm_search') & filters.user(ADMINS))
async def off_pm_search(bot, message):
    await db.update_bot_sttgs('PM_SEARCH', False)
    await message.reply('Successfully turned off pm search')

@Client.on_message(filters.command('on_pm_search') & filters.user(ADMINS))
async def on_pm_search(bot, message):
    await db.update_bot_sttgs('PM_SEARCH', True)
    await message.reply('Successfully turned on pm search')

# --- ADMIN MANAGEMENT ---
@Client.on_message(filters.command('restart') & filters.user(ADMINS))
async def restart_bot(bot, message):
    msg = await message.reply("Restarting...")
    with open('restart.txt', 'w+') as file: file.write(f"{msg.chat.id}\n{msg.id}")
    os.execl(sys.executable, sys.executable, "bot.py")

@Client.on_message(filters.command('leave') & filters.user(ADMINS))
async def leave_a_chat(bot, message):
    if len(message.command) == 1: return await message.reply('Give me a chat ID')
    try: chat = int(message.command[1])
    except: return await message.reply('Give me a valid chat ID')
    try:
        await bot.send_message(chat_id=chat, text='My owner has told me to leave. Bye!')
        await bot.leave_chat(chat)
        await message.reply(f"Successfully left group: `{chat}`")
    except Exception as e: await message.reply(f'Error: {e}')

@Client.on_message(filters.command('users') & filters.user(ADMINS))
async def list_users(bot, message):
    raju = await message.reply('Getting list of users...')
    users = await db.get_all_users()
    out = "Users saved in database:\n\n"
    count = 0
    async for user in users:
        out += f"Name: {user['name']} | ID: `{user['id']}`\n"
        count += 1
        if count >= 100:
            out += "...\nAnd many more."
            break
    try: await raju.edit_text(out)
    except MessageTooLong:
        with open('users.txt', 'w+') as outfile: outfile.write(out)
        await message.reply_document('users.txt', caption="List of users")
        os.remove('users.txt')

@Client.on_message(filters.command('chats') & filters.user(ADMINS))
async def list_chats(bot, message):
    raju = await message.reply('Getting list of chats...')
    chats = await db.get_all_chats()
    out = "Chats saved in database:\n\n"
    count = 0
    async for chat in chats:
        out += f"Title: {chat['title']} | ID: `{chat['id']}`\n"
        count += 1
        if count >= 100:
            out += "...\nAnd many more."
            break
    try: await raju.edit_text(out)
    except MessageTooLong:
        with open('chats.txt', 'w+') as outfile: outfile.write(out)
        await message.reply_document('chats.txt', caption="List of chats")
        os.remove('chats.txt')

@Client.on_message(filters.command('ban_user') & filters.user(ADMINS))
async def ban_a_user(bot, message):
    try: user_id = int(message.command[1])
    except: return await message.reply('Give me a user ID')
    try:
        await db.ban_user(user_id)
        await message.reply(f"User {user_id} banned successfully.")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command('unban_user') & filters.user(ADMINS))
async def unban_a_user(bot, message):
    try: user_id = int(message.command[1])
    except: return await message.reply('Give me a user ID')
    try:
        await db.remove_ban(user_id)
        await message.reply(f"User {user_id} unbanned successfully.")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command('ban_grp') & filters.user(ADMINS))
async def disable_chat(bot, message):
    try: chat = int(message.command[1])
    except: return await message.reply('Give me a chat ID')
    try:
        await db.disable_chat(chat, "Banned by Admin")
        await message.reply(f"Chat {chat} Disabled.")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command('unban_grp') & filters.user(ADMINS))
async def enable_chat(bot, message):
    try: chat = int(message.command[1])
    except: return await message.reply('Give me a chat ID')
    try:
        await db.re_enable_chat(chat)
        await message.reply(f"Chat {chat} Enabled.")
    except Exception as e: await message.reply(f"Error: {e}")

# --- GROUP ADMIN COMMANDS ---
@Client.on_message(filters.command('ban') & filters.group)
async def ban_chat_user(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return await message.reply_text('You not admin.')
    if not message.reply_to_message: return await message.reply("Reply to a user.")
    try:
        await client.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply(f"Banned {message.reply_to_message.from_user.mention}")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command('mute') & filters.group)
async def mute_chat_user(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return await message.reply_text('You not admin.')
    if not message.reply_to_message: return await message.reply("Reply to a user.")
    try:
        await client.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, ChatPermissions())
        await message.reply(f"Muted {message.reply_to_message.from_user.mention}")
    except Exception as e: await message.reply(f"Error: {e}")

@Client.on_message(filters.command(['unban', 'unmute']) & filters.group)
async def unban_chat_user(client, message):
    if not await is_check_admin(client, message.chat.id, message.from_user.id): return await message.reply_text('You not admin.')
    if not message.reply_to_message: return await message.reply("Reply to a user.")
    try:
        await client.unban_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        await message.reply(f"Unbanned/Unmuted {message.reply_to_message.from_user.mention}")
    except Exception as e: await message.reply(f"Error: {e}")

# --- CONFIRM PAYMENT HANDLER ---
@Client.on_callback_query(filters.regex(r'^confirm_pay'))
async def confirm_payment_handler(client, query):
    if query.from_user.id not in ADMINS: return await query.answer("Not Authorized", show_alert=True)
    _, user_id, days = query.data.split("#")
    user_id = int(user_id); days = int(days)
    
    ask_msg = await client.send_message(query.message.chat.id, f"<b>⚠️ Confirm Activation</b>\nUser ID: `{user_id}`\nDays: {days}\n\n<b>Send days to activate or /cancel</b>")
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text == "/cancel":
            await ask_msg.delete(); await msg.delete()
            return await query.message.reply("❌ Cancelled.")
        final_days = int(msg.text)
        
        mp = await db.get_plan(user_id)
        ex = datetime.now(timezone.utc) + timedelta(days=final_days)
        mp['expire'] = ex
        mp['plan'] = f'{final_days} days'
        mp['premium'] = True
        await db.update_plan(user_id, mp)
        
        user_info = await client.get_users(user_id)
        await client.send_message(LOG_CHANNEL, f"#Premium_Added (Payment)\n\n👤 <b>User:</b> {user_info.mention} (`{user_id}`)\n🗓 <b>Plan:</b> {final_days} Days\n⏰ <b>Expires:</b> {ex.strftime('%d/%m/%Y')}\n👮‍♂️ <b>Approved By:</b> {query.from_user.mention}")
        
        # Delete admin interaction messages
        try: await ask_msg.delete(); await msg.delete()
        except: pass
        
        await client.send_message(query.message.chat.id, f"<b>✅ Premium Activated!</b>\nUser: {user_id}\nDays: {final_days}\nExpire: {ex.strftime('%d/%m/%Y')}")
        await query.message.edit_reply_markup(reply_markup=None)
        try: await client.send_message(user_id, f"<b>🥳 Payment Accepted!</b>\n\nYour Premium plan for <b>{final_days} Days</b> has been activated.")
        except: pass
    except ValueError: await query.message.reply("❌ Invalid Number.")
    except ListenerTimeout: await query.message.reply("⏳ Time Out.")
    except Exception as e: await query.message.reply(f"Error: {e}")
