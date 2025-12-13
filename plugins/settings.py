import logging
from hydrogram import Client, filters, enums
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import is_check_admin, get_settings, save_group_settings

logger = logging.getLogger(__name__)

# ==============================================================================
# ⚙️ GROUP SETTINGS DASHBOARD (/settings)
# ==============================================================================
@Client.on_message(filters.command("settings") & filters.group)
async def settings_handler(client, message):
    try:
        # Check Admin Permission
        if not await is_check_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("<b>🛑 Access Denied! Only Admins can change settings.</b>")
            
        settings = await get_settings(message.chat.id)
        
        # Determine Button States (✅/❌)
        auto_filter = "✅" if settings.get('auto_filter', True) else "❌"
        spell_check = "✅" if settings.get('spell_check', True) else "❌"
        auto_delete = "✅" if settings.get('auto_delete', False) else "❌"
        welcome = "✅" if settings.get('welcome', True) else "❌"
        protect = "✅" if settings.get('protect', False) else "❌"
        
        # Settings Panel Buttons
        btn = [
            [
                InlineKeyboardButton(f"Filter: {auto_filter}", callback_data=f"setgs#auto_filter#{message.chat.id}"),
                InlineKeyboardButton(f"Spell Check: {spell_check}", callback_data=f"setgs#spell_check#{message.chat.id}")
            ],
            [
                InlineKeyboardButton(f"Auto-Delete: {auto_delete}", callback_data=f"setgs#auto_delete#{message.chat.id}"),
                InlineKeyboardButton(f"Welcome: {welcome}", callback_data=f"setgs#welcome#{message.chat.id}")
            ],
            [
                InlineKeyboardButton(f"Protect Content: {protect}", callback_data=f"setgs#protect#{message.chat.id}")
            ],
            [
                InlineKeyboardButton("📝 Edit Caption", callback_data=f"caption_setgs#{message.chat.id}"),
                InlineKeyboardButton("👋 Edit Welcome", callback_data=f"welcome_setgs#{message.chat.id}")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]
        
        await message.reply_text(
            f"<b>⚙️ <u>GROUP SETTINGS</u></b>\n\n"
            f"<b>🏷️ Group:</b> {message.chat.title}\n"
            f"<b>🆔 ID:</b> <code>{message.chat.id}</code>\n\n"
            f"<i>Tap buttons to toggle features ON/OFF.</i>",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        
    except Exception as e:
        logger.error(f"Settings Error: {e}")
        await message.reply("❌ Error opening settings!")

# ==============================================================================
# 🎛️ CALLBACK HANDLER (Toggle Logic)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^setgs#"))
async def settings_callback_handler(client, query):
    try:
        _, feature, chat_id = query.data.split("#")
        chat_id = int(chat_id)
        
        # Security Check
        if not await is_check_admin(client, chat_id, query.from_user.id):
            return await query.answer("🛑 You are not an Admin!", show_alert=True)
            
        # Get Current Status & Toggle
        curr_settings = await get_settings(chat_id)
        curr_status = curr_settings.get(feature, True if feature in ['auto_filter', 'spell_check'] else False)
        new_status = not curr_status
        
        # Save New Status
        await save_group_settings(chat_id, feature, new_status)
        
        # Refresh Panel
        new_settings = await get_settings(chat_id)
        
        auto_filter = "✅" if new_settings.get('auto_filter', True) else "❌"
        spell_check = "✅" if new_settings.get('spell_check', True) else "❌"
        auto_delete = "✅" if new_settings.get('auto_delete', False) else "❌"
        welcome = "✅" if new_settings.get('welcome', True) else "❌"
        protect = "✅" if new_settings.get('protect', False) else "❌"
        
        btn = [
            [
                InlineKeyboardButton(f"Filter: {auto_filter}", callback_data=f"setgs#auto_filter#{chat_id}"),
                InlineKeyboardButton(f"Spell Check: {spell_check}", callback_data=f"setgs#spell_check#{chat_id}")
            ],
            [
                InlineKeyboardButton(f"Auto-Delete: {auto_delete}", callback_data=f"setgs#auto_delete#{chat_id}"),
                InlineKeyboardButton(f"Welcome: {welcome}", callback_data=f"setgs#welcome#{chat_id}")
            ],
            [
                InlineKeyboardButton(f"Protect Content: {protect}", callback_data=f"setgs#protect#{chat_id}")
            ],
            [
                InlineKeyboardButton("📝 Edit Caption", callback_data=f"caption_setgs#{chat_id}"),
                InlineKeyboardButton("👋 Edit Welcome", callback_data=f"welcome_setgs#{chat_id}")
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="close_data")
            ]
        ]
        
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        await query.answer(f"✅ {feature.replace('_', ' ').title()} Updated!")
        
    except Exception as e:
        logger.error(f"Toggle Error: {e}")
        await query.answer("❌ Error Updating!", show_alert=True)
