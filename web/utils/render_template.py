import urllib.parse
import html
import logging
from info import BIN_CHANNEL, URL
from utils import temp

# लॉगिंग सेटअप
logger = logging.getLogger(__name__)

# --- HTML TEMPLATE (God Mode UI) ---
watch_tmplt = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{heading}</title>
    <meta property="og:title" content="{heading}">
    <meta property="og:description" content="Watch {file_name} in High Quality. Powered by Fast Finder Bot.">
    <meta property="og:image" content="{poster}">
    <meta name="theme-color" content="#0f0f13">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">

    <style>
        /* --- CSS VARIABLES (Modern Palette) --- */
        :root {
            --bg-color: #09090b;
            --card-bg: #18181b;
            --primary: #e50914; /* Netflix Red */
            --primary-hover: #f40612;
            --text-main: #ffffff;
            --text-sub: #a1a1aa;
            --border: #27272a;
            --surface: #27272a;
            --shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
        }

        [data-theme="light"] {
            --bg-color: #f4f4f5;
            --card-bg: #ffffff;
            --text-main: #18181b;
            --text-sub: #52525b;
            --border: #e4e4e7;
            --surface: #f4f4f5;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: var(--bg-color); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; transition: background-color 0.3s; }

        /* --- NAVBAR --- */
        .navbar {
            padding: 1rem 1.5rem;
            background: rgba(24, 24, 27, 0.8);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border);
            position: sticky; top: 0; z-index: 100;
            display: flex; align-items: center; justify-content: space-between;
        }
        [data-theme="light"] .navbar { background: rgba(255, 255, 255, 0.8); }
        
        .brand { font-weight: 800; font-size: 1.25rem; background: linear-gradient(45deg, #e50914, #ff5e62); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: 0.5px; }

        .theme-btn {
            background: var(--surface); border: none; color: var(--text-main);
            width: 40px; height: 40px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all 0.2s; font-size: 1.2rem;
        }
        .theme-btn:hover { transform: rotate(15deg); background: var(--border); }

        /* --- MAIN CONTENT --- */
        .main-container {
            flex: 1; width: 100%; max-width: 1100px; margin: 0 auto; padding: 1.5rem;
            display: flex; flex-direction: column; gap: 1.5rem;
        }

        /* Player Wrapper */
        .video-wrapper {
            width: 100%; background: #000; border-radius: 16px; overflow: hidden;
            box-shadow: var(--shadow); aspect-ratio: 16/9; position: relative;
            border: 1px solid var(--border);
        }
        video { width: 100%; height: 100%; }

        /* Info Card */
        .info-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; box-shadow: var(--shadow); }
        
        .file-header { display: flex; justify-content: space-between; align-items: start; gap: 1rem; margin-bottom: 1rem; }
        .file-title { font-size: 1.25rem; font-weight: 700; line-height: 1.4; color: var(--text-main); }
        
        .badge-container { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
        .badge { 
            padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; 
            background: var(--surface); color: var(--text-sub); border: 1px solid var(--border);
        }
        .badge.pro { background: rgba(229, 9, 20, 0.1); color: var(--primary); border-color: rgba(229, 9, 20, 0.2); }

        /* --- ACTION GRID (GOD MODE) --- */
        .grid-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; }
        
        .btn {
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem;
            padding: 1rem; border-radius: 12px; font-weight: 600; text-decoration: none;
            transition: all 0.2s ease; text-align: center; border: 1px solid var(--border);
            background: var(--surface); color: var(--text-main);
        }
        .btn i { font-size: 1.5rem; margin-bottom: 2px; }
        .btn span { font-size: 0.85rem; }
        
        .btn:hover { transform: translateY(-3px); border-color: var(--primary); background: var(--card-bg); }
        
        .btn-primary { background: var(--primary); color: white; border: none; grid-column: 1 / -1; flex-direction: row; font-size: 1rem; padding: 0.8rem; }
        .btn-primary:hover { background: var(--primary-hover); opacity: 1; transform: translateY(-2px); }
        .btn-primary i { font-size: 1.2rem; margin: 0; }

        /* Toast Notification */
        .toast {
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%) translateY(100px);
            background: var(--text-main); color: var(--bg-color); padding: 10px 20px;
            border-radius: 50px; font-weight: 600; font-size: 0.9rem; opacity: 0;
            transition: all 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55); z-index: 1000;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        .toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }

        footer { text-align: center; padding: 2rem; color: var(--text-sub); font-size: 0.85rem; margin-top: auto; border-top: 1px solid var(--border); background: var(--card-bg); }

        /* Plyr Customization */
        .plyr { --plyr-color-main: var(--primary); border-radius: 12px; font-family: 'Outfit', sans-serif; }
        .plyr__menu__container { background: var(--card-bg); color: var(--text-main); }
        .plyr__control--overlaid { background: rgba(229, 9, 20, 0.8); }
        .plyr__control--overlaid:hover { background: var(--primary); }

        @media (max-width: 600px) {
            .grid-actions { grid-template-columns: 1fr 1fr; }
            .btn-primary { grid-column: 1 / -1; }
            .file-title { font-size: 1.1rem; }
            .main-container { padding: 1rem; }
        }
    </style>
</head>
<body>

    <nav class="navbar">
        <span class="brand"><i class="ri-movie-2-fill"></i> FAST FINDER</span>
        <button class="theme-btn" id="theme-toggle">
            <i class="ri-moon-clear-line" id="icon-theme"></i>
        </button>
    </nav>

    <main class="main-container">
        <div class="video-wrapper">
            <video id="player" playsinline controls preload="metadata" poster="{poster}">
                <source src="{src}" type="{mime_type}" />
            </video>
        </div>

        <div class="info-card">
            <div class="file-header">
                <h1 class="file-title">{file_name}</h1>
            </div>
            
            <div class="badge-container">
                <span class="badge pro">⚡ FAST SERVER</span>
                <span class="badge">NO ADS</span>
                <span class="badge">HD QUALITY</span>
            </div>

            <div class="grid-actions">
                <a href="{src}" class="btn btn-primary" download>
                    <i class="ri-download-cloud-2-fill"></i>
                    <span>Download File</span>
                </a>

                <a href="vlc://{src}" class="btn">
                    <i class="ri-cone-fill" style="color: #ff9800;"></i>
                    <span>Play in VLC</span>
                </a>

                <a href="intent:{src}#Intent;package=com.mxtech.videoplayer.ad;S.title={heading};end" class="btn">
                    <i class="ri-play-circle-fill" style="color: #2196f3;"></i>
                    <span>MX Player</span>
                </a>

                <a href="intent:{src}#Intent;package=com.playit.videoplayer;S.title={heading};end" class="btn">
                    <i class="ri-google-play-fill" style="color: #673ab7;"></i>
                    <span>PlayIt App</span>
                </a>

                <button class="btn" onclick="copyLink()">
                    <i class="ri-file-copy-line" style="color: #00c853;"></i>
                    <span>Copy Link</span>
                </button>
            </div>
        </div>
    </main>

    <footer>
        <p>Powered by <b>Fast Finder Bot</b><br>The Ultimate Telegram Streaming Experience</p>
    </footer>

    <div class="toast" id="toast">Link Copied to Clipboard! ✅</div>

    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // 1. Initialize Player (Full Features)
            const player = new Plyr('#player', {
                controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                settings: ['captions', 'quality', 'speed'],
                speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
                keyboard: { focused: true, global: true },
            });

            // 2. Theme Toggler
            const themeBtn = document.getElementById('theme-toggle');
            const icon = document.getElementById('icon-theme');
            const html = document.documentElement;

            // Load Saved Theme
            const savedTheme = localStorage.getItem('theme') || 'dark';
            html.setAttribute('data-theme', savedTheme);
            updateIcon(savedTheme);

            themeBtn.addEventListener('click', () => {
                const current = html.getAttribute('data-theme');
                const next = current === 'dark' ? 'light' : 'dark';
                
                html.setAttribute('data-theme', next);
                localStorage.setItem('theme', next);
                updateIcon(next);
            });

            function updateIcon(theme) {
                if(theme === 'dark') {
                    icon.className = 'ri-sun-line';
                } else {
                    icon.className = 'ri-moon-clear-line';
                }
            }
        });

        // 3. Copy Link Function
        function copyLink() {
            const link = "{src}";
            navigator.clipboard.writeText(link).then(() => {
                const toast = document.getElementById('toast');
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 3000);
            }).catch(err => {
                console.error('Failed to copy: ', err);
            });
        }
    </script>
</body>
</html>
"""

# --- MAIN RENDER FUNCTION ---
async def media_watch(message_id):
    try:
        # Fetch Message from Bin Channel
        media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
        if not media_msg or not media_msg.media:
            return '<h1>404: File Not Found</h1><p>The file may have been deleted.</p>'

        media = getattr(media_msg, media_msg.media.value, None)
        if not media:
            return '<h1>Error: Unsupported Media Type</h1>'

        # Extract Meta
        file_name = getattr(media, 'file_name', f'File_{message_id}')
        mime_type = getattr(media, 'mime_type', 'application/octet-stream')
        
        # Determine URLs
        base_url = URL[:-1] if URL.endswith('/') else URL
        src = f"{base_url}/download/{message_id}"
        
        # Poster Logic (If video has thumb)
        poster_url = "https://i.ibb.co/M8S0Zzj/live-streaming.png" # Default
        if getattr(media, "thumbs", None) or getattr(media, "thumb", None):
             poster_url = f"{base_url}/thumbnail/{message_id}"

        # Safe Encoding
        safe_heading = html.escape(file_name)
        safe_filename = html.escape(file_name)
            
        # Inject Values into Template
        return watch_tmplt.replace('{heading}', safe_heading) \
                          .replace('{file_name}', safe_filename) \
                          .replace('{src}', src) \
                          .replace('{poster}', poster_url) \
                          .replace('{mime_type}', mime_type)

    except Exception as e:
        logger.error(f"Render Template Error: {e}")
        return f'<h1>Internal Server Error</h1><p>{e}</p>'
