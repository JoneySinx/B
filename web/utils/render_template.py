import urllib.parse
import html
import logging
from info import BIN_CHANNEL, URL
from utils import temp

# लॉगिंग सेटअप
logger = logging.getLogger(__name__)

# HTML Template (Plyr Player with Dark Theme)
watch_tmplt = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta property="og:image" content="https://i.ibb.co/M8S0Zzj/live-streaming.png" itemprop="thumbnailUrl">
    <meta property="og:title" content="{heading}">
    <meta property="og:description" content="Watch {file_name} online with high speed streaming.">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{heading}</title>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <style>
        :root {
            --primary: #818cf8;
            --primary-hover: #6366f1;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --bg-color: #0f172a;
            --player-bg: #1e293b;
            --footer-bg: #1e293b;
            --border-color: #334155;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        header {
            padding: 1rem;
            background-color: var(--player-bg);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 10;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        #file-name {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 80%;
            text-align: center;
        }
        
        .container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 2rem;
            width: 100%;
        }
        
        .player-container {
            width: 100%;
            max-width: 1200px;
            background-color: var(--player-bg);
            border-radius: 0.5rem;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        
        .action-buttons {
            display: flex;
            justify-content: center;
            gap: 1rem;
            margin-top: 1rem;
            padding: 1rem;
            flex-wrap: wrap;
        }
        
        .action-btn {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.25rem;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            text-decoration: none;
            transition: background-color 0.2s;
        }
        
        .action-btn:hover { background-color: var(--primary-hover); }
        
        footer {
            padding: 1rem;
            text-align: center;
            background-color: var(--footer-bg);
            color: var(--text-secondary);
            font-size: 0.875rem;
            border-top: 1px solid var(--border-color);
        }
        
        @media (max-width: 768px) {
            #file-name { font-size: 0.9rem; max-width: 90%; }
            .container { padding: 0.5rem; }
            .action-buttons { gap: 0.5rem; }
            .action-btn { font-size: 0.9rem; flex: 1; justify-content: center; }
        }
        
        /* Plyr overrides */
        .plyr--video .plyr__control--overlaid { background: var(--primary); }
        .plyr--video .plyr__control:hover, 
        .plyr--video .plyr__control[aria-expanded="true"] { background: var(--primary-hover); }
        .plyr__control.plyr__tab-focus { box-shadow: 0 0 0 5px rgba(99, 102, 241, 0.5); }
        .plyr--full-ui input[type="range"] { color: var(--primary); }
    </style>
</head>
<body class="dark">
    <header>
        <div id="file-name" title="{file_name}">{file_name}</div>
    </header>

    <div class="container">
        <div class="player-container">
            <video controls crossorigin playsinline>
                <source src="{src}" type="{mime_type}">
                Your browser does not support the video tag.
            </video>
            <div class="action-buttons">
                <a href="{src}" class="action-btn" download>
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Download
                </a>
                <a href="vlc://{src}" class="action-btn">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    Play in VLC
                </a>
            </div>
        </div>
    </div>

    <footer>
        <p>Video not playing? Try downloading the file or opening in VLC.</p>
    </footer>

    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const player = new Plyr('video', {
                controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
                settings: ['captions', 'quality', 'speed'],
                speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] }
            });
        });
    </script>
</body>
</html>
"""

async def media_watch(message_id):
    try:
        # 1. Message Fetching
        media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
        if not media_msg or not media_msg.media:
            return '<h1>File not found or deleted</h1>'

        media = getattr(media_msg, media_msg.media.value, None)
        if not media:
            return '<h1>Unsupported Media Type</h1>'

        # 2. Extract Details
        file_name = getattr(media, 'file_name', 'Unknown File')
        mime_type = getattr(media, 'mime_type', 'application/octet-stream')
        
        # 3. Stream Link Generation
        base_url = URL[:-1] if URL.endswith('/') else URL
        src = f"{base_url}/download/{message_id}"

        # 4. Check if streamable
        is_video = 'video' in mime_type
        is_audio = 'audio' in mime_type
        
        if is_video or is_audio:
            safe_heading = html.escape(f'Watch - {file_name}')
            safe_filename = html.escape(file_name)
            
            # FIX: Using .replace() instead of .format() to avoid CSS brace conflicts
            return watch_tmplt.replace('{heading}', safe_heading) \
                              .replace('{file_name}', safe_filename) \
                              .replace('{src}', src) \
                              .replace('{mime_type}', mime_type)
        else:
            return f'''
            <!DOCTYPE html>
            <html lang="en">
            <head><title>Not Streamable</title></head>
            <body style="background:#0f172a; color:#fff; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif;">
                <div style="text-align:center;">
                    <h1>File not streamable</h1>
                    <p>Filename: {html.escape(file_name)}</p>
                    <br>
                    <a href="{src}" style="background:#818cf8; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">Download File</a>
                </div>
            </body>
            </html>
            '''

    except Exception as e:
        logger.error(f"Render Template Error: {e}")
        return '<h1>Internal Server Error</h1>'
