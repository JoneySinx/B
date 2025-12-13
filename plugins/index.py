import re
import time
import math
import asyncio
import logging
from hydrogram import Client, filters, enums
from hydrogram.errors import FloodWait, MessageNotModified
from info import ADMINS
# 🔥 IMPORT UPDATED save_file
from database.ia_filterdb import save_file
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp, get_readable_time

logger = logging.getLogger(__name__)
lock = asyncio.Lock()

# --- 🎨 PROGRESS BAR (RETRO SQUARES) ---
def get_progress_bar_string(current, total):
    filled_symbol = "■"
    empty_symbol = "□"
    completed = int(current * 10 / total)
    remainder = 10 - completed
    return filled_symbol * completed + empty_symbol * remainder

# --- CUSTOM ITERATOR ---
async def iter_messages(bot, chat_id, limit, offset):
    current = offset
    while current < limit:
        new_diff = min(200, limit - current)
        if new_diff <= 0: return
        batch_ids = list(range(current, current + new_diff + 1))
        try:
            messages = await bot.get_messages(chat_id, batch_ids)
            for message in messages:
                if message: yield message
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            logger.error(f"Error fetching batch {current}: {e}")
            pass
        current += 200

# --- CALLBACK HANDLER (UPDATED FOR DUAL DB) ---
@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    # Data Format: index#action#target_db#chat_id#last_msg_id#skip
    data = query.data.split("#")
    action = data[1]

    if query.from_user.id not in ADMINS:
         return await query.answer("🛑 Access Denied! Admins Only.", show_alert=True)
         
    if action == 'start':
        target_db = data[2] # primary / backup
        chat = int(data[3])
        lst_msg_id = int(data[4])
        skip = int(data[5])

        msg = query.message
        await msg.edit(f"<b>🎛️ Iɴᴛɪᴀʟɪᴢɪɴɢ Iɴᴅᴇx Eɴɢɪɴᴇ ({target_db.upper()})...</b>")
        
        # Start Indexing with Target DB
        await index_files_to_db(lst_msg_id, chat, msg, bot, skip, target_db)
    
    elif action == 'cancel':
        temp.CANCEL = True
        await query.message.edit("<b>🛑 Sᴛᴏᴘᴘɪɴɢ Pʀᴏᴄᴇss... Pʟᴇᴀsᴇ Wᴀɪᴛ.</b>")

# --- INITIATION HANDLER ---
@Client.on_message(filters.forwarded & filters.private & filters.incoming & filters.user(ADMINS))
async def send_for_index(bot, message):
    if lock.locked():
        return await message.reply('<b>⚠️ A Process is already running. Please wait.</b>')
        
    msg = message
    chat_id = None
    last_msg_id = None
    
    # 1. Parsing Logic
    if msg.text and msg.text.startswith("https://t.me"):
        try:
            msg_link = msg.text.split("/")
            last_msg_id = int(msg_link[-1])
            chat_id = msg_link[-2]
            if chat_id.isnumeric():
                chat_id = int(("-100" + chat_id)) 
        except Exception as e:
            logger.error(f"Link parsing error: {e}")
            await message.reply('<b>❌ Invalid Message Link!</b>')
            return
            
    elif msg.forward_from_chat and msg.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = msg.forward_from_message_id
        chat_id = msg.forward_from_chat.username or msg.forward_from_chat.id
    else:
        await message.reply('<b>⚠️ Please forward a message from a Channel or send a Link.</b>')
        return
        
    try:
        chat = await bot.get_chat(chat_id)
    except Exception as e:
        return await message.reply(f'<b>❌ Error Accessing Chat:</b> {e}')

    if chat.type != enums.ChatType.CHANNEL:
        return await message.reply("<b>❌ I can only index Channels.</b>")

    # 2. Skip Input
    s = await message.reply("<b>🔢 Send Skip Count (Start Message ID):</b>\n<i>(Send 0 to start from beginning)</i>")
    try:
        msg_skip = await bot.listen(chat_id=message.chat.id, user_id=message.from_user.id, timeout=30) 
        await s.delete()
        skip = int(msg_skip.text)
    except Exception:
        await s.delete()
        return await message.reply("<b>❌ Invalid Input or Timeout.</b>")
        
    # 3. 🔥 DUAL DB BUTTONS (The Change)
    buttons = [
        [
            InlineKeyboardButton('🚀 Primary DB', callback_data=f'index#start#primary#{chat_id}#{last_msg_id}#{skip}'),
            InlineKeyboardButton('🗄️ Backup DB', callback_data=f'index#start#backup#{chat_id}#{last_msg_id}#{skip}')
        ],
        [InlineKeyboardButton('❌ CANCEL', callback_data='close_data')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    await message.reply(
        f"<b>🗂️ <u>Iɴᴅᴇxɪɴɢ Cᴏɴᴛʀᴏʟ Pᴀɴᴇʟ</u></b>\n\n"
        f"<b>📢 Cʜᴀɴɴᴇʟ:</b> {chat.title}\n"
        f"<b>🔢 Tᴏᴛᴀʟ Mᴇssᴀɢᴇs:</b> <code>{last_msg_id}</code>\n"
        f"<b>⏭️ Sᴋɪᴘ Uɴᴛɪʟ:</b> <code>{skip}</code>\n\n"
        f"<i>Select target database to start:</i>",
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )

# --- INDEXING CORE LOGIC ---
async def index_files_to_db(lst_msg_id, chat, msg, bot, skip, target_db):
    start_time = time.time()
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    
    current = skip
    total_to_process = lst_msg_id - skip
    
    async with lock:
        try:
            async for message in iter_messages(bot, chat, lst_msg_id, skip):
                
                # --- CANCEL LOGIC ---
                if temp.CANCEL:
                    temp.CANCEL = False
                    time_taken = get_readable_time(time.time()-start_time)
                    await msg.edit_text(
                        f"<b>🛑 Iɴᴅᴇxɪɴɢ Aʙᴏʀᴛᴇᴅ!</b>\n\n"
                        f"<b>🎯 Tᴀʀɢᴇᴛ:</b> {target_db.upper()}\n"
                        f"<b>⏱️ Rᴜɴᴛɪᴍᴇ:</b> {time_taken}\n"
                        f"<b>⚡ Sᴀᴠᴇᴅ:</b> <code>{total_files}</code>",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
                    
                current += 1
                
                # --- PROGRESS UPDATE ---
                if current % 200 == 0:
                    now = time.time()
                    diff = now - start_time
                    speed = (current - skip) / diff if diff > 0 else 1
                    remaining_msgs = lst_msg_id - current
                    eta = get_readable_time(remaining_msgs / speed)
                    
                    percentage = (current - skip) * 100 / total_to_process
                    prog_bar = get_progress_bar_string(current - skip, total_to_process)
                    
                    # Button to Stop
                    btn = [[InlineKeyboardButton('⛔ STOP OPERATION', callback_data=f'index#cancel#{target_db}#{chat}#{lst_msg_id}#{skip}')]]
                    
                    try:
                        await msg.edit_text(
                            text=(
                                f"<b>🔄 Pʀᴏᴄᴇssɪɴɢ ({target_db.upper()})...</b>\n\n"
                                f"{prog_bar} <b>{percentage:.2f}%</b>\n\n"
                                f"<b>📂 Sᴄᴀɴɴᴇᴅ:</b> <code>{current}/{lst_msg_id}</code>\n"
                                f"<b>⚡ Sᴀᴠᴇᴅ:</b> <code>{total_files}</code>\n"
                                f"<b>♻️ Dᴜᴘʟɪᴄᴀᴛᴇs:</b> <code>{duplicate}</code>\n"
                                f"<b>🚀 Sᴘᴇᴇᴅ:</b> <code>{round(speed)} msg/s</code>\n"
                                f"<b>⏳ Eᴛᴀ:</b> <code>{eta}</code>"
                            ),
                            reply_markup=InlineKeyboardMarkup(btn),
                            parse_mode=enums.ParseMode.HTML
                        )
                    except (FloodWait, MessageNotModified):
                        pass
                    except Exception:
                        pass
                        
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT, enums.MessageMediaType.AUDIO]:
                    unsupported += 1
                    continue
                
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                
                media.file_type = message.media.value
                media.caption = message.caption
                
                # 🔥 PASS TARGET DB TO SAVE_FILE
                sts = await save_file(media, target_db=target_db) 
                
                if sts == 'suc':
                    total_files += 1
                elif sts == 'dup':
                    duplicate += 1
                elif sts == 'err':
                    errors += 1
                    
        except Exception as e:
            logger.error(f"Indexing failed for chat {chat}: {e}")
            await msg.reply(f'<b>❌ Cʀɪᴛɪᴄᴀʟ Eʀʀᴏʀ:</b> {e}')
            
        else:
            time_taken = get_readable_time(time.time()-start_time)
            await msg.edit_text(
                f"<b>✅ Oᴘᴇʀᴀᴛɪᴏɴ Sᴜᴄᴄᴇssғᴜʟ!</b>\n\n"
                f"<b>🎯 Tᴀʀɢᴇᴛ DB:</b> {target_db.upper()}\n"
                f"<b>⏱️ Tᴏᴛᴀʟ Tɪᴍᴇ:</b> <code>{time_taken}</code>\n"
                f"<b>📊 Tᴏᴛᴀʟ Sᴄᴀɴɴᴇᴅ:</b> <code>{current - skip}</code>\n"
                f"<b>⚡ Tᴏᴛᴀʟ Sᴀᴠᴇᴅ:</b> <code>{total_files}</code>\n"
                f"<b>♻️ Dᴜᴘʟɪᴄᴀᴛᴇs:</b> <code>{duplicate}</code>\n"
                f"<b>🗑️ Sᴋɪᴘᴘᴇᴅ:</b> <code>{deleted + no_media + unsupported}</code>",
                parse_mode=enums.ParseMode.HTML
                        )
