import asyncio
import re
import math
import os
import random
import logging
import qrcode
from time import time as time_now
from hydrogram.errors import ListenerTimeout
from hydrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
from datetime import datetime, timedelta, timezone
from info import (
    IS_PREMIUM, PICS, TUTORIAL, SHORTLINK_API, SHORTLINK_URL, 
    RECEIPT_SEND_USERNAME, UPI_ID, UPI_NAME, PRE_DAY_AMOUNT, 
    ADMINS, URL, MAX_BTN, BIN_CHANNEL, 
    IS_STREAM, DELETE_TIME, FILMS_LINK, LOG_CHANNEL, SUPPORT_GROUP, 
    SUPPORT_LINK, UPDATES_LINK, LANGUAGES, QUALITY
)
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto
from hydrogram import Client, filters, enums
from utils import (
    is_premium, get_size, is_subscribed, is_check_admin, get_wish, 
    get_shortlink, get_readable_time, get_poster, temp, get_settings, 
    save_group_settings
)
from database.users_chats_db import db
from database.ia_filterdb import get_search_results, delete_files, db_count_documents
from plugins.commands import get_grp_stg

logger = logging.getLogger(__name__)

BUTTONS = {}
CAP = {}

@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_search(client, message):
    if message.text.startswith("/"):
        return
        
    if not await is_premium(message.from_user.id, client):
        return

    stg = await db.get_bot_sttgs()
    if not stg: stg = {}
        
    if 'AUTO_FILTER' in stg and not stg.get('AUTO_FILTER'):
        return await message.reply_text('Auto filter is globally disabled by Admin!')
        
    s = await message.reply(f"<b><i>⚠️ `{message.text}` searching...</i></b>", quote=True, parse_mode=enums.ParseMode.HTML)
    await auto_filter(client, message, s)


@Client.on_message(filters.group & filters.text & filters.incoming)
async def group_search(client, message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message and message.from_user else 0
    
    if not await is_premium(user_id, client):
        return

    stg = await db.get_bot_sttgs()
    if not stg: stg = {'AUTO_FILTER': True}
        
    if stg.get('AUTO_FILTER', True):
        if message.chat.id == SUPPORT_GROUP:
            files, offset, total = await get_search_results(message.text)
            if files:
                btn = [[InlineKeyboardButton("Here", url=FILMS_LINK)]]
                await message.reply_text(f'Total {total} results found in this group', reply_markup=InlineKeyboardMarkup(btn))
            return
            
        if message.text.startswith("/"): return
            
        elif '@admin' in message.text.lower() or '@admins' in message.text.lower():
            if await is_check_admin(client, message.chat.id, message.from_user.id): return
            admins = []
            async for member in client.get_chat_members(chat_id=message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if not member.user.is_bot:
                    admins.append(member.user.id)
                    if member.status == enums.ChatMemberStatus.OWNER:
                        if message.reply_to_message:
                            try:
                                sent_msg = await message.reply_to_message.forward(member.user.id)
                                await sent_msg.reply_text(f"#Attention\n★ User: {message.from_user.mention}\n★ Group: {message.chat.title}\n\n★ <a href={message.reply_to_message.link}>Go to message</a>", disable_web_page_preview=True)
                            except: pass
                        else:
                            try:
                                sent_msg = await message.forward(member.user.id)
                                await sent_msg.reply_text(f"#Attention\n★ User: {message.from_user.mention}\n★ Group: {message.chat.title}\n\n★ <a href={message.link}>Go to message</a>", disable_web_page_preview=True)
                            except: pass
            hidden_mentions = (f'[\u2064](tg://user?id={uid})' for uid in admins)
            await message.reply_text('Report sent!' + ''.join(hidden_mentions))
            return

        elif re.findall(r'https?://\S+|www\.\S+|t\.me/\S+|@\w+', message.text):
            if await is_check_admin(client, message.chat.id, message.from_user.id): return
            try: await message.delete()
            except: pass
            return await message.reply('Links not allowed here!')
        
        elif '#request' in message.text.lower():
            if message.from_user.id in ADMINS: return
            await client.send_message(LOG_CHANNEL, f"#Request\n★ User: {message.from_user.mention}\n★ Group: {message.chat.title}\n\n★ Message: {re.sub(r'#request', '', message.text.lower())}")
            await message.reply_text("Request sent!")
            return  
        else:
            s = await message.reply(f"<b><i>⚠️ `{message.text}` searching...</i></b>", parse_mode=enums.ParseMode.HTML)
            await auto_filter(client, message, s)
    else:
        k = await message.reply_text('Auto Filter Off! ❌')
        await asyncio.sleep(5)
        await k.delete()
        try: await message.delete()
        except: pass

@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    try: offset = int(offset)
    except: offset = 0
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search:
        await query.answer(f"Hello {query.from_user.first_name},\nSend New Request Again!", show_alert=True)
        return

    files, n_offset, total = await get_search_results(search, offset=offset)
    try: n_offset = int(n_offset)
    except: n_offset = 0

    if not files: return
    temp.FILES[key] = files
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code> ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs</b>" if settings["auto_delete"] else ''
    files_link = ''

    if settings['links']:
        btn = []
        for file_num, file in enumerate(files, start=offset+1):
            files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(text=f"{get_size(file['file_size'])} - {file['file_name']}", callback_data=f"file#{file['_id']}")] for file in files]

    # --- BUTTONS REMOVED HERE ---
    # Languages बटन हटा दिया गया है
    # सिर्फ Send All और Quality बटन रखा गया है
    if settings['shortlink'] and not await is_premium(query.from_user.id, bot):
        btn.insert(0,
            [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", url=await get_shortlink(settings['url'], settings['api'], f'https://t.me/{temp.U_NAME}?start=all_{query.message.chat.id}_{key}')),
            InlineKeyboardButton("⚙️ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")]
        )
    else:
        btn.insert(0,
            [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=f"send_all#{key}#{req}"),
            InlineKeyboardButton("⚙️ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#{offset}")]
        )

    if 0 < offset <= MAX_BTN:
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - MAX_BTN
        
    if n_offset == 0:
        btn.append([InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"🗓{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons")])
    elif off_set is None:
        btn.append([InlineKeyboardButton(f"🗓{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")])
    else:
        btn.append([InlineKeyboardButton("⏪ BACK", callback_data=f"next_{req}_{key}_{off_set}"), InlineKeyboardButton(f"🗓{math.ceil(int(offset) / MAX_BTN) + 1}/{math.ceil(total / MAX_BTN)}", callback_data="buttons"), InlineKeyboardButton("NEXT ⏩", callback_data=f"next_{req}_{key}_{n_offset}")])
    
    # --- SUBSCRIPTION BUTTON REMOVED HERE ---
    # btn.append([InlineKeyboardButton('🤑 Buy Subscription : Remove Ads', ...)])  <-- Removed

    await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)

# ... (Quality, Lang search, Auto filter Logic Updated Below) ...

@Client.on_callback_query(filters.regex(r"^quality"))
async def quality(client: Client, query: CallbackQuery):
    _, key, req, offset = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    btn = [
        [InlineKeyboardButton(text=QUALITY[i].title(), callback_data=f"qual_search#{QUALITY[i]}#{key}#{offset}#{req}"),
         InlineKeyboardButton(text=QUALITY[i+1].title(), callback_data=f"qual_search#{QUALITY[i+1]}#{key}#{offset}#{req}")]
        for i in range(0, len(QUALITY)-1, 2)
    ]
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{offset}")])  
    await query.message.edit_text("<b>ɪɴ ᴡʜɪᴄʜ ǫᴜᴀʟɪᴛʏ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ, sᴇʟᴇᴄᴛ ʜᴇʀᴇ 👇</b>", disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^qual_search"))
async def quality_search(client: Client, query: CallbackQuery):
    _, qual, key, offset, req = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    if not search:
        await query.answer("Send New Request Again!", show_alert=True)
        return
    files, l_offset, total_results = await get_search_results(search, lang=qual)
    if not files:
        await query.answer(f"sᴏʀʀʏ '{qual.title()}' ǫᴜᴀʟɪᴛʏ ꜰɪʟᴇs ɴᴏᴛ ꜰᴏᴜɴᴅ 😕", show_alert=1)
        return
    temp.FILES[key] = files
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code> ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs</b>" if settings["auto_delete"] else ''
    files_link = ''
    if settings['links']:
        btn = []
        for file_num, file in enumerate(files, start=1):
            files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(text=f"{get_size(file['file_size'])} - {file['file_name']}", callback_data=f'file#{file["_id"]}')] for file in files]
    
    btn.append([InlineKeyboardButton(text="⪻ ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ ᴘᴀɢᴇ", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text(cap + files_link + del_msg, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)

@Client.on_callback_query(filters.regex(r"^qual_next"))
async def quality_next_page(bot, query):
    ident, req, key, qual, l_offset, offset = query.data.split("#")
    if int(req) != query.from_user.id:
        return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
    try: l_offset = int(l_offset)
    except: l_offset = 0
    search = BUTTONS.get(key)
    cap = CAP.get(key)
    settings = await get_settings(query.message.chat.id)
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code> ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs</b>" if settings["auto_delete"] else ''
    if not search:
        await query.answer("Send New Request Again!", show_alert=True)
        return
    files, n_offset, total = await get_search_results(search, offset=l_offset, lang=qual)
    if not files: return
    temp.FILES[key] = files
    try: n_offset = int(n_offset)
    except: n_offset = 0
    files_link = ''
    if settings['links']:
        btn = []
        for file_num, file in enumerate(files, start=l_offset+1):
            files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    else:
        btn = [[InlineKeyboardButton(text=f"{get_size(file['file_size'])} - {file['file_name']}", callback_data=f'file#{file["_id"]}')] for file in files]
        
    btn.append([InlineKeyboardButton(text="Back To Main Page", callback_data=f"next_{req}_{key}_{offset}")])
    await query.message.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)

# Auto Filter Logic Updated (Buttons Removed)
async def auto_filter(client, msg, s, spoll=False):
    if not spoll:
        message = msg
        settings = await get_settings(message.chat.id)
        search = re.sub(r"\s+", " ", re.sub(r"[-:\"';!]", " ", message.text)).strip()
        files, offset, total_results = await get_search_results(search)
        if not files:
            if settings["spell_check"]:
                await advantage_spell_chok(message, s)
            else:
                await s.edit(f'I cant find {search}')
            return
    else:
        settings = await get_settings(msg.message.chat.id)
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
    req = message.from_user.id if message and message.from_user else 0
    key = f"{message.chat.id}-{message.id}"
    temp.FILES[key] = files
    BUTTONS[key] = search
    files_link = ""
    if settings['links']:
        btn = []
        for file_num, file in enumerate(files, start=1):
            files_link += f"""<b>\n\n{file_num}. <a href=https://t.me/{temp.U_NAME}?start=file_{message.chat.id}_{file['_id']}>[{get_size(file['file_size'])}] {file['file_name']}</a></b>"""
    else:
        btn = [[
            InlineKeyboardButton(text=f"{get_size(file['file_size'])} - {file['file_name']}", callback_data=f'file#{file["_id"]}')
        ] for file in files]
    
    if offset != "":
        # --- BUTTONS REMOVED HERE TOO ---
        if settings['shortlink'] and not await is_premium(message.from_user.id, client):
            btn.insert(0,
                [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", url=await get_shortlink(settings['url'], settings['api'], f'https://t.me/{temp.U_NAME}?start=all_{message.chat.id}_{key}')),
                InlineKeyboardButton("⚙️ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0")]
            )
        else:
            btn.insert(0,
                [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ", callback_data=f"send_all#{key}#{req}"),
                InlineKeyboardButton("⚙️ ǫᴜᴀʟɪᴛʏ", callback_data=f"quality#{key}#{req}#0")]
            )
        btn.append(
            [InlineKeyboardButton(text=f"🗓1/{math.ceil(int(total_results) / MAX_BTN)}", callback_data="buttons"),
             InlineKeyboardButton(text="NEXT ⏩", callback_data=f"next_{req}_{key}_{offset}")]
        )
    else:
        if settings['shortlink'] and not await is_premium(message.from_user.id, client):
            btn.insert(0,
                [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ ♻️", url=await get_shortlink(settings['url'], settings['api'], f'https://t.me/{temp.U_NAME}?start=all_{message.chat.id}_{key}'))]
            )
        else:
            btn.insert(0,
                [InlineKeyboardButton("♻️ sᴇɴᴅ ᴀʟʟ ♻️", callback_data=f"send_all#{key}#{req}")]
            )
            
    # --- SUBSCRIPTION BUTTON REMOVED ---
    # btn.append([InlineKeyboardButton('🤑 Buy Subscription : Remove Ads', ...)]) <-- Removed

    imdb = await get_poster(search, file=(files[0])['file_name']) if settings["imdb"] else None
    TEMPLATE = settings['template']
    if imdb:
        cap = TEMPLATE.format(
            query=search, title=imdb['title'], votes=imdb['votes'], aka=imdb["aka"], seasons=imdb["seasons"],
            box_office=imdb['box_office'], localized_title=imdb['localized_title'], kind=imdb['kind'], imdb_id=imdb["imdb_id"],
            cast=imdb["cast"], runtime=imdb["runtime"], countries=imdb["countries"], certificates=imdb["certificates"],
            languages=imdb["languages"], director=imdb["director"], writer=imdb["writer"], producer=imdb["producer"],
            composer=imdb["composer"], cinematographer=imdb["cinematographer"], music_team=imdb["music_team"],
            distributors=imdb["distributors"], release_date=imdb['release_date'], year=imdb['year'], genres=imdb['genres'],
            poster=imdb['poster'], plot=imdb['plot'], rating=imdb['rating'], url=imdb['url'], **locals()
        )
    else:
        cap = f"<b>✅ Search Results:- {search}\n🦹 Requested By {message.from_user.mention}\n⚡ Powered By:- {message.chat.title} \n🎬 Total File Found :- {total_results}</b>"
    CAP[key] = cap
    del_msg = f"\n\n<b>⚠️ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴀꜰᴛᴇʀ <code>{get_readable_time(DELETE_TIME)}</code> ᴛᴏ ᴀᴠᴏɪᴅ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs</b>" if settings["auto_delete"] else ''
    
    if imdb and imdb.get('poster'):
        await s.delete()
        try:
            k = await message.reply_photo(photo=imdb.get('poster'), caption=cap[:1024] + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML, quote=True)
            if settings["auto_delete"]:
                await asyncio.sleep(DELETE_TIME)
                await k.delete()
                try: await message.delete()
                except: pass
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg")
            try:
                k = await message.reply_photo(photo=poster, caption=cap[:1024] + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML, quote=True)
                if settings["auto_delete"]:
                    await asyncio.sleep(DELETE_TIME)
                    await k.delete()
                    try: await message.delete()
                    except: pass
            except Exception:
                k = await message.reply_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True)
                if settings["auto_delete"]:
                    await asyncio.sleep(DELETE_TIME)
                    await k.delete()
                    try: await message.delete()
                    except: pass
        except Exception:
            k = await message.reply_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML, quote=True)
            if settings["auto_delete"]:
                await asyncio.sleep(DELETE_TIME)
                await k.delete()
                try: await message.delete()
                except: pass
    else:
        k = await s.edit_text(cap + files_link + del_msg, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
        if settings["auto_delete"]:
            await asyncio.sleep(DELETE_TIME)
            await k.delete()
            try: await message.delete()
            except: pass

async def advantage_spell_chok(message, s):
    # Same spelling code as before
    search = message.text
    google_search = search.replace(" ", "+")
    btn = [[
        InlineKeyboardButton("⚠️ Instructions ⚠️", callback_data='instructions'),
        InlineKeyboardButton("🔎 Search Google 🔍", url=f"https://www.google.com/search?q={google_search}")
    ]]
    try: movies = await get_poster(search, bulk=True)
    except:
        n = await s.edit_text(text=script.NOT_FILE_TXT.format(message.from_user.mention, search), reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
        await asyncio.sleep(60)
        await n.delete()
        try: await message.delete()
        except: pass
        return
    if not movies:
        n = await s.edit_text(text=script.NOT_FILE_TXT.format(message.from_user.mention, search), reply_markup=InlineKeyboardMarkup(btn), parse_mode=enums.ParseMode.HTML)
        await temp.BOT.send_message(LOG_CHANNEL, f"#No_Result\n\nRequester: {message.from_user.mention}\nContent: {search}")
        await asyncio.sleep(60)
        await n.delete()
        try: await message.delete()
        except: pass
        return
    unique_movies = []
    seen_ids = set()
    for m in movies:
        if m.movieID not in seen_ids:
            unique_movies.append(m)
            seen_ids.add(m.movieID)
    movies = unique_movies
    user = message.from_user.id if message.from_user else 0
    buttons = [[InlineKeyboardButton(text=movie.get('title'), callback_data=f"spolling#{movie.movieID}#{user}")] for movie in movies]
    buttons.append([InlineKeyboardButton("🙅 Close", callback_data="close_data")])
    s = await s.edit_text(text=f"👋 Hello {message.from_user.mention},\n\nI couldn't find the <b>'{search}'</b> you requested.\nSelect if you meant one of these? 👇", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=enums.ParseMode.HTML)
    await asyncio.sleep(300)
    await s.delete()
    try: await message.delete()
    except: pass

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    # This must handle close_data, file, stream etc.
    if query.data == "close_data":
        try: user = query.message.reply_to_message.from_user.id
        except: user = query.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nThis Is Not For You!", show_alert=True)
        await query.answer("Closed!")
        await query.message.delete()
        try: await query.message.reply_to_message.delete()
        except: pass
  
    elif query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        try: user = query.message.reply_to_message.from_user.id
        except: user = query.message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(f"Hello {query.from_user.first_name},\nDon't Click Other Results!", show_alert=True)
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")

    # ... (Include the rest of cb_handler from previous response: stream, stats, help, activate_plan, etc.)
    # Since this file was already working, just ensure you paste the full working cb_handler logic here as well.
    # The crucial part was removing buttons from auto_filter and next_page above.
    pass
