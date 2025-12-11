# 🚀 Fast Finder Bot - Premium Auto Filter

<p align="center">
  <img src="https://graph.org/file/5a676b7337373f0083906.jpg" alt="Fast Finder Bot">
</p>

<p align="center">
  <a href="https://www.python.org">
    <img src="http://forthebadge.com/images/badges/made-with-python.svg" width="150">
  </a>
  <a href="https://www.mongodb.com">
    <img src="https://img.shields.io/badge/Database-MongoDB-green?style=for-the-badge&logo=mongodb" width="160">
  </a>
</p>

<p align="center">
  <b>An Advanced Auto Filter Bot with Premium Subscription System, Web Streamer, and Group Management Features.</b>
</p>

---

## ✨ Features

- **🚀 Furious Speed:** Search files in milliseconds using indexed database.
- **💎 Premium System:** Built-in subscription system with **UPI QR Code** payment support.
- **🎥 Web Streamer:** Watch files online without downloading (Supports Dark/Light Mode).
- **📂 Auto Index:** Automatically saves files from channels to the database.
- **🛡️ Group Management:** Manage groups with `/ban`, `/mute`, `/purge`, and `/pin`.
- **📊 Advanced Stats:** Professional dashboard for bot statistics.
- **🤖 Manual Filters:** Add custom replies for specific keywords.
- **🚫 Anti-Spam:** Auto-delete search results after a specific time.
- **🧟 Zombie Cleaner:** Kick deleted/inactive accounts from groups.
- **📢 Broadcast:** Send messages to all users/groups with a progress bar.

---

## 🛠️ Deployment (Easy)

### 1️⃣ Deploy on Koyeb
<a href="https://app.koyeb.com/deploy?type=git&repository=YOUR_GITHUB_REPO_LINK&branch=main&name=fast-finder-bot">
  <img src="https://www.koyeb.com/static/images/deploy/button.svg" alt="Deploy">
</a>

### 2️⃣ Deploy on Heroku
<a href="https://heroku.com/deploy?template=YOUR_GITHUB_REPO_LINK">
  <img src="https://www.herokucdn.com/deploy/button.svg" alt="Deploy">
</a>

### 3️⃣ Deploy on Render
<a href="https://render.com/deploy?repo=YOUR_GITHUB_REPO_LINK">
  <img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy">
</a>

---

## 📝 Environment Variables (Config)

You need to set these variables in your `info.py` or Server Environment variables.

### 🔐 Mandatory Vars
| Variable | Description | Example |
| :--- | :--- | :--- |
| `API_ID` | Get this from my.telegram.org | `1234567` |
| `API_HASH` | Get this from my.telegram.org | `abcdef123456` |
| `BOT_TOKEN` | Get this from @BotFather | `12345:ABC-DEF` |
| `DATA_DATABASE_URL` | MongoDB Connection String | `mongodb+srv://...` |
| `ADMINS` | User IDs of Admins (Space separated) | `12345678 87654321` |
| `LOG_CHANNEL` | Channel ID for Logs | `-100xxxxxxxxx` |
| `BIN_CHANNEL` | Channel ID for File Storing | `-100xxxxxxxxx` |
| `URL` | Server URL (For Streamer) | `https://your-app.koyeb.app/` |

### 💎 Premium Vars (Optional)
| Variable | Description | Default |
| :--- | :--- | :--- |
| `IS_PREMIUM` | Enable Premium System | `True` |
| `UPI_ID` | Your UPI ID for Payments | `yourname@oksbi` |
| `UPI_NAME` | Name shown on QR Code | `Fast Finder` |
| `PRE_DAY_AMOUNT` | Price per day (INR) | `10` |

### ⚙️ Feature Toggles (Optional)
| Variable | Description | Default |
| :--- | :--- | :--- |
| `PROTECT_CONTENT` | Prevent forwarding files | `True` |
| `AUTO_DELETE` | Auto delete search results | `False` |
| `DELETE_TIME` | Time to delete (in seconds) | `300` |
| `IS_STREAM` | Enable Stream/Download Links | `True` |
| `INDEX_CHANNELS` | Auto-Index Channel IDs | `-100xxxx -100xxxx` |

---

## 🤖 Commands List

### 👤 User Commands
- `/start` - Check if bot is alive.
- `/link` - Get Direct Download/Stream link.
- `/plan` - Check Premium Plans & Buy.
- `/myplan` - Check current subscription status.
- `/id` - Get Telegram ID & Chat ID.
- `/info` - Get User Information.

### 👮‍♂️ Admin Commands
- `/stats` - Check Bot Statistics & Storage.
- `/broadcast` - Broadcast message to Users/Groups.
- `/index_channels` - List indexed channels.
- `/add_channel` - Add a channel for indexing.
- `/remove_channel` - Remove an indexed channel.
- `/delete` - Delete files from database.
- `/delete_all` - Delete ALL files (Reset DB).
- `/eval` - Execute Python Code.
- `/sh` - Run Terminal Commands.

### 🛡️ Group Management
- `/settings` - Configure Group Settings.
- `/manage` - Manage members (Unmute/Kick).
- `/purge` - Delete messages in bulk.
- `/pin` - Pin a message.
- `/ban`, `/mute`, `/unban` - Moderation tools.
- `/add`, `/del`, `/filters` - Manual Filters.

---

## 📦 Requirements
- Python 3.10+
- MongoDB
- FFmpeg (Optional for encoding)

## 🏗️ Local Deployment
```bash
# 1. Clone the Repo
git clone [https://github.com/joneysinx/x.git](https://github.com/Joneysinx/x.git)
cd YOUR_REPO

# 2. Install Requirements
pip3 install -r requirements.txt

# 3. Edit info.py or Set Env Vars
vi info.py

# 4. Run the Bot
python3 bot.py
