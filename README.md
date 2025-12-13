<h1 align="center">
  <img src="https://graph.org/file/5a676b7337373f0083906.jpg" width="200px" style="border-radius: 50%;">
  <br>
  ⚡ Fast Finder Bot (God Mode Edition) ⚡
</h1>

<p align="center">
  <a href="https://github.com/YourRepo/Auto-Filter-Bot">
    <img src="https://img.shields.io/github/stars/YourRepo/Auto-Filter-Bot?style=social">
  </a>
  <a href="https://github.com/YourRepo/Auto-Filter-Bot/fork">
    <img src="https://img.shields.io/github/forks/YourRepo/Auto-Filter-Bot?label=Fork&style=social">
  </a>  
</p>

<p align="center">
  <b>The Ultimate Telegram Auto Filter Bot with Dual Database, Clone System, Premium Payments, and Advanced Streaming Web UI.</b>
</p>

<hr>

## 🌟 God Mode Features

| Feature | Description |
| :--- | :--- |
| **🧠 Dual Database** | Connect Primary & Backup MongoDB. If one fails, the bot switches to the other. |
| **🤖 Clone System** | Users can create their own bots (`/clone`) that run on your server. |
| **🎥 Ultra Streaming** | Custom Web Player with Speed Control, PIP, and direct **MX Player / VLC** intents. |
| **💎 Premium System** | Built-in **UPI Payment** system. Auto-expire plans & 12h/6h reminders. |
| **🛡️ God Admin Panel** | Control everything via `/admin` & `/settings` (No restart needed). |
| **🧹 Surgical Delete** | Delete specific files by ID using `/purge` or Interactive Mode. |
| **🚀 Fast Indexing** | Auto-index channels and groups with duplicate removal. |
| **🕵️ Analytics** | Track what users are searching for and optimize your content. |

---

## 🛠️ Deployment (The Easy Way)

### 1️⃣ Deploy to Render (Recommended 🐳)
This bot is optimized for Render with **Docker** (FFmpeg + MediaInfo pre-installed).

<a href="https://render.com/deploy?repo=https://github.com/YourRepo/Auto-Filter-Bot">
  <img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render">
</a>

### 2️⃣ Deploy to Heroku
<a href="https://heroku.com/deploy?template=https://github.com/YourRepo/Auto-Filter-Bot">
  <img src="https://www.herokucdn.com/deploy/button.svg" alt="Deploy">
</a>

### 3️⃣ Deploy on VPS (Docker)
```bash
# 1. Update & Install Docker
sudo apt update && sudo apt install docker.io -y

# 2. Clone Repo
git clone [https://github.com/YourRepo/Auto-Filter-Bot](https://github.com/YourRepo/Auto-Filter-Bot)
cd Auto-Filter-Bot

# 3. Build & Run
docker build -t god-bot .
docker run -d -p 80:8080 --env-file config.env god-bot
