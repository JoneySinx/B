import os
import asyncio
import logging
from datetime import datetime
from speedtest import Speedtest, ConfigRetrievalError, SpeedtestBestServerFailure
from hydrogram import Client, filters, enums
from hydrogram.errors import UserNotParticipant
from info import ADMINS
from utils import get_size

logger = logging.getLogger(__name__)

@Client.on_message(filters.command('id'))
async def showid(client, message):
    chat_type = message.chat.type
    
    # यदि किसी मैसेज पर रिप्लाई किया गया है
    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.forward_from_chat:
            await message.reply_text(f"<b>Forwarded Channel/Group ID:</b> <code>{reply.forward_from_chat.id}</code>")
        elif reply.from_user:
            await message.reply_text(f"<b>Replied User ID:</b> <code>{reply.from_user.id}</code>")
        else:
             await message.reply_text(f"<b>Message ID:</b> <code>{reply.id}</code>")
        return

    # यदि प्राइवेट चैट है
    if chat_type == enums.ChatType.PRIVATE:
        await message.reply_text(f'<b>★ User ID:</b> <code>{message.from_user.id}</code>')

    # यदि ग्रुप है
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await message.reply_text(f'<b>★ Group ID:</b> <code>{message.chat.id}</code>')

    # यदि चैनल है
    elif chat_type == enums.ChatType.CHANNEL:
        await message.reply_text(f'<b>★ Channel ID:</b> <code>{message.chat.id}</code>')


# Speedtest को नॉन-ब्लॉकिंग बनाने के लिए अलग फंक्शन
def run_speedtest():
    speed = Speedtest()
    speed.get_best_server()
    speed.download()
    speed.upload()
    return speed.results

@Client.on_message(filters.command('speedtest') & filters.user(ADMINS))
async def speedtest_handler(client, message):
    msg = await message.reply_text("⚡️ Initiating Speedtest... Please wait!")
    
    try:
        # इसे थ्रेड में चलाएं ताकि बॉट ब्लॉक न हो
        results = await asyncio.to_thread(run_speedtest)
    except (ConfigRetrievalError, SpeedtestBestServerFailure) as e:
        await msg.edit(f"❌ Can't connect to Server: {e}")
        return
    except Exception as e:
        await msg.edit(f"❌ Error: {e}")
        return

    # रिजल्ट्स प्रोसेस करें
    results.share()
    result = results.dict()
    photo = result['share']
    
    text = f'''
➲ <b>SPEEDTEST INFO</b>
┠ <b>Upload:</b> <code>{get_size(result['upload'] / 8)}/s</code>
┠ <b>Download:</b> <code>{get_size(result['download'] / 8)}/s</code>
┠ <b>Ping:</b> <code>{result['ping']} ms</code>
┠ <b>Time:</b> <code>{datetime.strptime(result['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M:%S")}</code>

➲ <b>CLIENT DETAILS</b>
┠ <b>IP:</b> <code>{result['client']['ip']}</code>
┠ <b>ISP:</b> <code>{result['client']['isp']}</code>
┖ <b>Country:</b> <code>{result['client']['country']}</code>
'''
    await message.reply_photo(photo=photo, caption=text)
    await msg.delete()


@Client.on_message(filters.command("info"))
async def who_is(client, message):
    status_message = await message.reply_text("Fetching user info...")
    
    from_user_id = None
    if message.reply_to_message:
        from_user_id = message.reply_to_message.from_user.id
    elif len(message.command) > 1:
        from_user_id = message.command[1]
        if from_user_id.isdigit():
            from_user_id = int(from_user_id)
    else:
        from_user_id = message.from_user.id
        
    try:
        from_user = await client.get_users(from_user_id)
    except Exception as error:
        await status_message.edit(f'Error: {error}')
        return

    message_out_str = ""
    message_out_str += f"<b>➲ First Name:</b> {from_user.first_name}\n"
    message_out_str += f"<b>➲ Last Name:</b> {from_user.last_name or 'None'}\n"
    message_out_str += f"<b>➲ Telegram ID:</b> <code>{from_user.id}</code>\n"
    message_out_str += f"<b>➲ Username:</b> @{from_user.username or 'None'}\n"
    message_out_str += f"<b>➲ DC ID:</b> <code>{from_user.dc_id or 'Unknown'}</code>\n"
    message_out_str += f"<b>➲ Last Online:</b> {last_online(from_user)}\n"
    message_out_str += f"<b>➲ User Link:</b> <a href='tg://user?id={from_user.id}'><b>Click Here</b></a>\n"

    # यदि यह ग्रुप है तो जॉइन डेट चेक करें
    if message.chat.type in [enums.ChatType.SUPERGROUP, enums.ChatType.GROUP]:
        try:
            chat_member_p = await message.chat.get_member(from_user.id)
            if chat_member_p.joined_date:
                joined_date = chat_member_p.joined_date.strftime('%Y.%m.%d %H:%M:%S')
                message_out_str += f"<b>➲ Joined Chat:</b> <code>{joined_date}</code>\n"
        except UserNotParticipant:
            pass
        except Exception:
            pass

    chat_photo = from_user.photo
    if chat_photo:
        try:
            local_user_photo = await client.download_media(message=chat_photo.big_file_id)
            await message.reply_photo(
                photo=local_user_photo,
                caption=message_out_str,
                parse_mode=enums.ParseMode.HTML
            )
            os.remove(local_user_photo)
        except Exception as e:
            logger.warning(f"Failed to download/send photo: {e}")
            await message.reply_text(message_out_str, parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(
            text=message_out_str,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    await status_message.delete()


def last_online(from_user):
    if from_user.is_bot:
        return "🤖 Bot"
    elif from_user.status == enums.UserStatus.RECENTLY:
        return "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        return "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        return "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        return "A long time ago"
    elif from_user.status == enums.UserStatus.ONLINE:
        return "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        if from_user.last_online_date:
            return from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return "Unknown"
