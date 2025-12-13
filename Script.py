class script(object):

    # --- 👋 START MESSAGE ---
    START_TXT = """<b>👋 Hᴇʟʟᴏ {}, {}!</b>

I ᴀᴍ ᴀɴ ᴀᴅᴠᴀɴᴄᴇᴅ <b>Pʀᴇᴍɪᴜᴍ Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ</b>. ⚡
I ᴄᴀɴ ᴘʀᴏᴠɪᴅᴇ ᴍᴏᴠɪᴇs, sᴇʀɪᴇs, ᴀɴᴅ ғɪʟᴇs ᴅɪʀᴇᴄᴛʟʏ ɪɴ ʏᴏᴜʀ PM ᴏʀ Gʀᴏᴜᴘ.

✨ <b><u>Mʏ Fᴇᴀᴛᴜʀᴇs:</u></b>
🚀 <b>Fᴀsᴛ Sᴇᴀʀᴄʜ:</b> Get files in milliseconds.
🗄️ <b>Dᴜᴀʟ Dᴀᴛᴀʙᴀsᴇ:</b> Separate Primary & Backup storage.
🛡️ <b>Sᴇᴄᴜʀᴇ:</b> No Ads & Direct Links (Premium).
🤖 <b>Cʟᴏɴᴇ:</b> Create your own copy of this bot.
📂 <b>Sᴍᴀʀᴛ Iɴᴅᴇx:</b> Auto-routing for channels.

<i>👇 Cʟɪᴄᴋ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴋɴᴏᴡ ᴍᴏʀᴇ!</i>"""

    # --- 📊 STATUS DASHBOARD ---
    # 3 Placeholders for File Counts (Primary, Backup, Total)
    STATUS_TXT = """<b>📊 <u>Sʏsᴛᴇᴍ Sᴛᴀᴛɪsᴛɪᴄs</u></b>

<b>🥇 Pʀɪᴍᴀʀʏ DB:</b> <code>{}</code>
<b>🥈 Bᴀᴄᴋᴜᴘ DB:</b> <code>{}</code>
<b>📂 Tᴏᴛᴀʟ Fɪʟᴇs:</b> <code>{}</code>

<b>👤 Tᴏᴛᴀʟ Usᴇʀs:</b> <code>{}</code>
<b>🏘️ Tᴏᴛᴀʟ Gʀᴏᴜᴘs:</b> <code>{}</code>
<b>💎 Pʀᴇᴍɪᴜᴍ Usᴇʀs:</b> <code>{}</code>

<b>💾 Sᴛᴏʀᴀɢᴇ:</b> <code>{} / {}</code>
<b>⚙️ Mᴏᴅᴇ:</b> <code>{}</code>
<b>⚡ Uᴘᴛɪᴍᴇ:</b> <code>{}</code>"""

    # --- ⚙️ HELP MENU ---
    HELP_TXT = """<b>⚙️ <u>Hᴇʟᴘ Mᴇɴᴜ</u></b>

Hᴇʀᴇ ʏᴏᴜ ᴄᴀɴ ғɪɴᴅ ᴀʟʟ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅs ᴀɴᴅ ɪɴsᴛʀᴜᴄᴛɪᴏɴs ᴛᴏ ᴜsᴇ ᴍᴇ.

👤 <b>Usᴇʀs:</b> Search & Download Guide.
🤖 <b>Cʟᴏɴᴇ:</b> How to make your own bot.
🦹 <b>Aᴅᴍɪɴs:</b> Control Panel & Management.

<i>👇 Cʜᴏᴏsᴇ ᴀ ᴄᴀᴛᴇɢᴏʀʏ ʙᴇʟᴏᴡ:</i>"""

    # --- 👤 USER COMMANDS ---
    USER_COMMAND_TXT = """<b>👤 <u>Usᴇʀ Cᴏᴍᴍᴀɴᴅs</u></b>

🔹 <code>/start</code> - Check if I am alive.
🔹 <code>/link</code> - Get Stream/Download Link (Reply to file).
🔹 <code>/plan</code> - Check Premium Plans.
🔹 <code>/myplan</code> - Check your current status.
🔹 <code>/id</code> - Get your Telegram ID.
🔹 <code>/img_2_link</code> - Create Link from Image.
🔹 <code>/clone</code> - Create your own bot.

<b>🔍 Hᴏᴡ ᴛᴏ Sᴇᴀʀᴄʜ?</b>
Just type the <b>Movie or Series Name</b> in the Group or PM."""

    # --- 🤖 CLONE GUIDE (New) ---
    CLONE_TXT = """<b>🤖 <u>Cʟᴏɴᴇ Bᴏᴛ Gᴜɪᴅᴇ</u></b>

<i>You can create your own bot that works exactly like this one!</i>

<b>1️⃣ Step 1:</b> Go to @BotFather and create a new bot.
<b>2️⃣ Step 2:</b> Get the <b>Bot Token</b>.
<b>3️⃣ Step 3:</b> Use command: <code>/clone [Bot Token]</code>

<b>⚠️ Note:</b>
• Clone bots are valid for <b>30 Days</b> (Renewable).
• You will be the owner of your clone.
• All files from my database will be available in your clone."""

    # --- 🦹 ADMIN COMMANDS (Clean Version) ---
    ADMIN_COMMAND_TXT = """<b>🦹 <u>Aᴅᴍɪɴ Cᴏɴᴛʀᴏʟs</u></b>

<b>🛠️ Mᴀsᴛᴇʀ Cᴏɴᴛʀᴏʟ:</b>
🔹 <code>/admin</code> or <code>/settings</code> - <b>Oᴘᴇɴ Gᴜɪ Cᴏɴᴛʀᴏʟ Pᴀɴᴇʟ</b> (Manage DB, Channels, Settings, Clones).

<b>⚡ Qᴜɪᴄᴋ Aᴄᴛɪᴏɴs:</b>
🔹 <code>/index [Channel ID]</code> - Quick Indexing.
🔹 <code>/delete [Query]</code> - Delete files.
🔹 <code>/broadcast</code> - Send Message to Users.
🔹 <code>/users</code> - View User List.
🔹 <code>/stats</code> - Check System Status.

<i>ℹ️ Note: Manage Index Channels, Auth Channels, and Premium Users directly from the <b>/admin</b> panel.</i>"""

    # --- 💎 PREMIUM PLAN ---
    PLAN_TXT = """<b>💎 <u>Pʀᴇᴍɪᴜᴍ Uᴘɢʀᴀᴅᴇ</u></b>

<i>Uɴʟᴏᴄᴋ ᴛʜᴇ ғᴜʟʟ ᴘᴏᴛᴇɴᴛɪᴀʟ ᴏғ Fᴀsᴛ Fɪɴᴅᴇʀ!</i> 🚀

✅ <b>Nᴏ Aᴅs & Cᴀᴘᴛᴄʜᴀ</b>
✅ <b>Dɪʀᴇᴄᴛ Dᴏᴡɴʟᴏᴀᴅ Lɪɴᴋs</b>
✅ <b>Hɪɢʜ Sᴘᴇᴇᴅ Sᴛʀᴇᴀᴍɪɴɢ</b>
✅ <b>Pʀɪᴏʀɪᴛʏ Sᴜᴘᴘᴏʀᴛ</b>

💰 <b>Pʀɪᴄᴇ:</b> ₹{} / Dᴀʏ
<i>(Contact Admin for Custom Plans)</i>

<b>🛍️ Hᴏᴡ ᴛᴏ Bᴜʏ?</b>
1️⃣ Click the button below.
2️⃣ Enter the number of days.
3️⃣ Pay via UPI QR Code.
4️⃣ Send the screenshot to <b>{}</b>."""

    # --- 📝 LOG MESSAGES ---
    NEW_USER_TXT = """<b>#New_User_Started 👤</b>

<b>🙋🏻‍♀️ Nᴀᴍᴇ:</b> {}
<b>🆔 ID:</b> <code>{}</code>
<b>📅 Dᴀᴛᴇ:</b> <i>Today</i>"""

    NEW_GROUP_TXT = """<b>#New_Group_Added 🏘️</b>

<b>🏷️ Tɪᴛʟᴇ:</b> {}
<b>🆔 ID:</b> <code>{}</code>
<b>🔗 Usᴇʀɴᴀᴍᴇ:</b> {}
<b>👥 Tᴏᴛᴀʟ Mᴇᴍʙᴇʀs:</b> <code>{}</code>"""

    # --- ⚠️ LEGACY VARIABLES ---
    NOT_FILE_TXT = """👋 Hᴇʟʟᴏ {},<br><br>I ᴄᴀɴ'ᴛ ғɪɴᴅ <b>{}</b> ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀsᴇ! 🥲"""
    IMDB_TEMPLATE = """✅ I Fᴏᴜɴᴅ: <code>{query}</code>""" 
    FILE_CAPTION = """<b>📂 {file_name}</b>\n<b>💾 Sɪᴢᴇ: {file_size}</b>"""
    WELCOME_TEXT = """<b>👋 Hᴇʟʟᴏ {mention}, Wᴇʟᴄᴏᴍᴇ ᴛᴏ {title}!</b>"""
    START_IMG = "https://i.ibb.co/qD4q2dG/image.jpg"
