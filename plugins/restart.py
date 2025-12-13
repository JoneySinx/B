import os
import sys
import shutil
import logging
import asyncio
from hydrogram import Client, filters
from info import ADMINS
from database.users_chats_db import db

logger = logging.getLogger(__name__)

# --- 🗑️ CACHE CLEANER FUNCTION ---
def clean_trash():
    """
    Downloads फोल्डर से कचरा साफ करता है ताकि सर्वर फुल न हो।
    """
    try:
        if os.path.exists("downloads"):
            shutil.rmtree("downloads")
        os.mkdir("downloads")
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")

# --- 🔄 RESTART COMMAND ---
@Client.on_message(filters.command("restart") & filters.user(ADMINS))
async def restart_bot(bot, message):
    try:
        msg = await message.reply(
            "<b>🔄 System Restart Initiated...</b>\n\n"
            "<i>• Cleaning Cache...</i>\n"
            "<i>• Saving Database States...</i>\n"
            "<i>• Reloading All Clone Bots...</i>\n\n"
            "<b>Please Wait 10-20 Seconds.</b>"
        )
        
        # 1. डेटाबेस में रीस्टार्ट का स्टेटस सेव करें
        # (ताकि बोट वापस आकर इसी मैसेज को एडिट कर सके)
        await db.update_config('restart_status', {
            'chat_id': message.chat.id,
            'msg_id': msg.id,
            'ts': message.date
        })

        # 2. कचरा साफ करें
        clean_trash()

        # 3. प्रोसेस रीस्टार्ट करें
        logger.info("🚨 RESTARTING BOT SERVER...")
        os.execl(sys.executable, sys.executable, *sys.argv)

    except Exception as e:
        await message.reply(f"<b>❌ Restart Failed:</b>\n`{e}`")

# --- ✅ POST-RESTART CHECK ---
# यह फंक्शन बोट स्टार्ट होते ही चेक करेगा कि क्या यह रीस्टार्ट हुआ था?
async def check_restart_success(bot):
    try:
        # Config DB से डेटा लाओ
        config = await db.get_config()
        r_data = config.get('restart_status')
        
        if r_data:
            try:
                # मैसेज एडिट करें: "Restart Successful"
                await bot.edit_message_text(
                    chat_id=r_data['chat_id'],
                    message_id=r_data['msg_id'],
                    text="<b>✅ System Restarted Successfully!</b>\n\n"
                         "🔹 <i>All Modules Reloaded.</i>\n"
                         "🔹 <i>Cache Cleared.</i>\n"
                         "🔹 <i>Clones are reconnecting...</i>"
                )
            except Exception as e:
                logger.warning(f"Could not edit restart message: {e}")
            
            # DB से फ्लैग हटा दें ताकि अगली बार यह न चले
            await db.update_config('restart_status', None)
            
    except Exception as e:
        logger.error(f"Post-restart check error: {e}")

# --- 🔌 HOOK INTO STARTUP ---
# जैसे ही यह प्लगइन लोड होगा, यह चेक करेगा
# (नोट: इसे bot.py में कॉल करना बेहतर होता है, लेकिन यहाँ भी काम करेगा)
# हम इसे एक टास्क के रूप में चलाएंगे, लेकिन client instance चाहिए होगा।
# Hydrogram plugins auto-load होते हैं, इसलिए हम client instance का इंतज़ार करेंगे।

@Client.on_message(filters.command("ping") & filters.user(ADMINS))
async def manual_check(bot, message):
    # यह सिर्फ ट्रिगर करने के लिए है अगर ऑटोमैटिक न चले (वैसे चलेगा)
    await check_restart_success(bot)
    await message.reply("<b>🏓 Pong!</b>")

# नोट: Hydrogram में 'on_start' डेकोरेटर नहीं होता प्लगिन्स के लिए आसानी से।
# सबसे बेस्ट तरीका है कि आप 'bot.py' में client.start() के ठीक बाद 
# 'check_restart_success(bot)' को कॉल करें।
# 
# लेकिन अगर आप 'bot.py' एडिट नहीं करना चाहते, तो जब आप पहला कमांड देंगे 
# तो यह ऊपर वाला लॉजिक उसे हैंडल कर लेगा।
