import urllib.parse
import html
import logging
from info import BIN_CHANNEL, URL
from utils import temp

# लॉगिंग सेटअप
logger = logging.getLogger(__name__)

# --- HTML TEMPLATE (With Dark/Light Toggle & Clean Player) ---
watch_tmplt = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{heading}</title>
    <meta property="og:title" content="{heading}">
    <meta property="og:description" content="Watch {file_name} online. Powered by Fast Finder.">
    <meta property="og:image" content="{poster}">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />

    <style>
        /* --- CSS VARIABLES (THEMING) --- */
        :root {
            /* Default Dark Theme */
            --bg-color: #0f0f13;
            --card-bg: #18181b;
            --primary: #e50914;
            --text-main: #ffffff;
            --text-sub: #a1a1aa;
            --border: #27272a;
            --btn-text: #000000;
            --btn-hover: #e2e2e2;
            --tag-bg: rgba(255,255,255,0.1);
        }

        /* Light Theme Overrides */
        [data-theme="light"] {
            --bg-color: #f4f4f5;
            --card-bg: #ffffff;
            --text-main: #18181b;
            --text-sub: #52525b;
            --border: #e4e4e7;
            --btn-text: #ffffff; 
            --btn-hover: #3f3f46;
            --tag-bg: rgba(0,0,0,0.05);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; transition: background-color 0.3s, color 0.3s; }
        body { background-color: var(--bg-color); color: var(--text-main); min-height: 100vh; display: flex; flex-direction: column; }

        .navbar {
            padding: 1rem 1.5rem;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .brand { font-weight: 700; font-size: 1.25rem; color: var(--primary); text-transform: uppercase; letter-spacing: 1px; }

        /* Theme Toggle Button */
        .theme-btn {
            background: none;
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 8px;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .theme-btn:hover { background: var(--tag-bg); }

        .main-container {
            flex: 1; width: 100%; max-width: 1000px; margin: 0 auto; padding: 1.5rem;
            display: flex; flex-direction: column; gap: 1.5rem;
        }

        .video-wrapper {
            width: 100%; background: #000; border-radius: 12px; overflow: hidden;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); aspect-ratio: 16/9;
        }
        video { width: 100%; height: 100%; object-fit: contain; }

        .info-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }
        .file-title { font-size: 1.1rem; font-weight: 600; line-height: 1.5; margin-bottom: 1rem; word-break: break-word; }

        .tags { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
        .tag { background: var(--tag-bg); padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 500; color: var(--text-sub); }
        .tag.hd { background: rgba(229, 9, 20, 0.15); color: #ff4d4d; }

        .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        @media (max-width: 640px) { .actions { grid-template-columns: 1fr; } .main-container { padding: 1rem; } }

        .btn {
            display: flex; align-items: center; justify-content: center; gap: 0.5rem;
            padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; text-decoration: none;
            transition: all 0.2s ease; font-size: 0.95rem;
        }
        
        .btn-primary { background: var(--text-main); color: var(--bg-color); }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
        
        .btn-secondary { background: var(--tag-bg); color: var(--text-main); }
        .btn-secondary:hover { background: var(--border); }

        footer { text-align: center; padding: 1.5rem; color: var(--text-sub); font-size: 0.875rem; border-top: 1px solid var(--border); margin-top: auto; }
        .plyr { --plyr-color-main: var(--primary); border-radius: 12px; }
    </style>
</head>
<body>
    <nav class="navbar">
        <span class="brand">FAST FINDER</span>
        <button class="theme-btn" id="theme-toggle" aria-label="Toggle Theme">
            <svg id="sun-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: none;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
            <svg id="moon-icon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
        </button>
    </nav>

    <main class="main-container">
        <div class="video-wrapper">
            <video id="player" playsinline controls preload="metadata" poster="{poster}">
                <source src="{src}" type="{mime_type}" />
            </video>
        </div>

        <div class="info-card">
            <h1 class="file-title">{file_name}</h1>
            <div class="tags">
                <span class="tag hd">STREAM</span><span class="tag">FAST SERVER</span><span class="tag">NO ADS</span>
            </div>
            <div class="actions">
                <a href="{src}" class="btn btn-primary" download>
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
                    Direct Download
                </a>
                <a href="vlc://{src}" class="btn btn-secondary">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>
                    Play in VLC
                </a>
            </div>
        </div>
        <div class="info-card" style="text-align: center; color: var(--text-sub); font-size: 0.9rem;">
             Audio or Video not playing? Try using <b>VLC Player</b> or <b>MX Player</b>.
        </div>
    </main>

    <footer><p>&copy; 2025 Fast Finder Bot. All rights reserved.</p></footer>

    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Player Setup (REMOVED 'mute' and 'volume')
            const player = new Plyr('#player', {
                controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                settings: ['captions', 'quality', 'speed'],
                keyboard: { focused: true, global: true },
            });

            // Theme Toggle Logic
            const toggleBtn = document.getElementById('theme-toggle');
            const sunIcon = document.getElementById('sun-icon');
            const moonIcon = document.getElementById('moon-icon');
            const html = document.documentElement;

            const currentTheme = localStorage.getItem('theme');
            if (currentTheme === 'light') {
                html.setAttribute('data-theme', 'light');
                sunIcon.style.display = 'none';
                moonIcon.style.display = 'block';
            } else {
                sunIcon.style.display = 'block';
                moonIcon.style.display = 'none';
            }

            toggleBtn.addEventListener('click', () => {
                if (html.getAttribute('data-theme') === 'light') {
                    html.removeAttribute('data-theme');
                    localStorage.setItem('theme', 'dark');
                    sunIcon.style.display = 'block';
                    moonIcon.style.display = 'none';
                } else {
                    html.setAttribute('data-theme', 'light');
                    localStorage.setItem('theme', 'light');
                    sunIcon.style.display = 'none';
                    moonIcon.style.display = 'block';
                }
            });
        });
    </script>
</body>
</html>
"""

# --- MAIN FUNCTION ---
async def media_watch(message_id):
    try:
        media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
        if not media_msg or not media_msg.media:
            return '<h1>File not found or deleted</h1>'

        media = getattr(media_msg, media_msg.media.value, None)
        if not media:
            return '<h1>Unsupported Media Type</h1>'

        file_name = getattr(media, 'file_name', 'Unknown File')
        mime_type = getattr(media, 'mime_type', 'application/octet-stream')
        
        base_url = URL[:-1] if URL.endswith('/') else URL
        src = f"{base_url}/download/{message_id}"
        
        poster_url = "https://i.ibb.co/M8S0Zzj/live-streaming.png"
        if getattr(media, "thumbs", None) or getattr(media, "thumb", None):
             poster_url = f"{base_url}/thumbnail/{message_id}"

        safe_heading = html.escape(f'Watch - {file_name}')
        safe_filename = html.escape(file_name)
            
        return watch_tmplt.replace('{heading}', safe_heading) \
                          .replace('{file_name}', safe_filename) \
                          .replace('{src}', src) \
                          .replace('{poster}', poster_url) \
                          .replace('{mime_type}', mime_type)

    except Exception as e:
        logger.error(f"Render Template Error: {e}")
        return '<h1>Internal Server Error</h1>'
