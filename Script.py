class script(object):

    START_TXT = """<b>ʜᴇʏ {}, <i>{}</i></b><br>    <br><b>Premium Filter With PM Search ⚡</b>"""

    # Stats UI Updated (Storage & Uptime Included)
    STATUS_TXT = """<b>📊 Bot Status</b>
    
👤 <b>Users:</b> <code>{}</code>
😎 <b>Premium:</b> <code>{}</code>
👥 <b>Chats:</b> <code>{}</code>

<b>🗂 Database Storage:</b>
• <b>Files Indexed:</b> <code>{}</code>
• <b>DB Used:</b> <code>{}</code>
• <b>Free Space:</b> <code>{}</code>

🚀 <b>Uptime:</b> <code>{}</code>"""

    NEW_GROUP_TXT = """#NewGroup<br>Title - {}<br>ID - <code>{}</code><br>Username - {}<br>Total - <code>{}</code>"""
    NEW_USER_TXT = """#NewUser<br>★ Name: {}<br>★ ID: <code>{}</code>"""
    NOT_FILE_TXT = """👋 Hello {},<br><br>I can't find the <b>{}</b> in my database! 🥲"""
    
    IMDB_TEMPLATE = """✅ I Found: <code>{query}</code><br><br>🏷 Title: <a href={url}>{title}</a>"""
    FILE_CAPTION = """<b>📂 {file_name}</b><br><b>♻️ Size: {file_size}</b><br><b>⚡ Powered By:- @YourXCloud</b>"""
    WELCOME_TEXT = """👋 Hello {mention}, Welcome to {title} group! 💞"""

    HELP_TXT = """👋 Hello {},<br>    <br>I can filter movies and series you want.<br>Just type the name in PM or Group.<br><br><b>Click buttons below for command list.</b>"""

    # Updated with all new Admin Commands
    ADMIN_COMMAND_TXT = """<b>👮‍♂️ Admin Commands:</b>

• /index_channels - Index channel
• /add_fsub - Add Force Subscribe Channel
• /del_fsub - Remove Force Subscribe Channel
• /view_fsub - View current F-Sub Channel
• /stats - Check Bot Status
• /broadcast - Broadcast Message to Users
• /users - List all users
• /chats - List all groups
• /leave - Leave a group
• /restart - Restart the bot
• /delete - Delete specific file
• /delete_all - Delete ALL files
• /ban_user - Ban a user
• /unban_user - Unban a user

<b>💎 Premium Commands:</b>
• /add_prm - Add Premium
• /rm_prm - Remove Premium
• /prm_list - List Premium Users

<b>⚙️ Settings Commands:</b>
• /on_auto_filter - Enable Auto Filter
• /off_auto_filter - Disable Auto Filter
• /on_pm_search - Enable PM Search
• /off_pm_search - Disable PM Search"""
    
    PLAN_TXT = """<b>💎 Premium Plans</b>\n\nActivate premium to get exclusive features like:\n• Ad-free experience\n• Direct Links\n• Fast Download\n\n<b>💰 Price:</b> INR {} per day\n\n<b>UPI ID:</b> <code>{}</code>"""

    USER_COMMAND_TXT = """<b>👤 User Commands:</b>

• /start - Check bot alive
• /myplan - Check your premium status
• /plan - Activate new plan
• /id - Get Telegram ID
• /img_2_link - Convert Image to Link
• /settings - Change Group Settings (Admins only)"""
    
    SOURCE_TXT = """<b>This is a private bot created for our community.</b>"""
