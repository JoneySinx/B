# web/utils/render_template.py

# ... existing imports ...

watch_tmplt = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{heading}</title>
    <meta property="og:title" content="{heading}">
    <meta property="og:description" content="Watch {file_name} online. Powered by Fast Finder.">
    <meta property="og:image" content="https://i.ibb.co/M8S0Zzj/live-streaming.png">
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />

    <style>
        :root {
            --bg-color: #0f0f13; /* Very dark background */
            --card-bg: #18181b; /* Slightly lighter card background */
            --primary: #e50914; /* Netflix-like red, or change to your bot's color like #2196F3 */
            --text-main: #ffffff;
            --text-sub: #a1a1aa;
            --border: #27272a;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Navbar */
        .navbar {
            padding: 1rem 1.5rem;
            background: rgba(15, 15, 19, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .brand {
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--primary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* Main Content */
        .main-container {
            flex: 1;
            width: 100%;
            max-width: 1000px;
            margin: 0 auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        /* Video Player Wrapper */
        .video-wrapper {
            width: 100%;
            background: #000;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4);
            aspect-ratio: 16/9; /* Enforce aspect ratio to prevent layout shifts */
        }
        
        video {
            width: 100%;
            height: 100%;
        }

        /* File Info Section */
        .info-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
        }

        .file-title {
            font-size: 1.1rem;
            font-weight: 600;
            line-height: 1.5;
            margin-bottom: 1rem;
            word-break: break-word;
        }

        .tags {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
        }

        .tag {
            background: rgba(255, 255, 255, 0.1);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--text-sub);
            text-transform: uppercase;
        }

        .tag.hd {
            background: rgba(229, 9, 20, 0.2);
            color: #ff4d4d;
        }

        /* Action Buttons */
        .actions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }

        @media (max-width: 640px) {
            .actions {
                grid-template-columns: 1fr;
            }
            .main-container {
                padding: 1rem;
            }
        }

        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.2s ease;
            font-size: 0.95rem;
        }

        .btn-primary {
            background: var(--text-main);
            color: #000;
        }
        .btn-primary:hover {
            background: #e2e2e2;
            transform: translateY(-1px);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: var(--text-main);
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.15);
        }

        /* Footer */
        footer {
            text-align: center;
            padding: 1.5rem;
            color: var(--text-sub);
            font-size: 0.875rem;
            border-top: 1px solid var(--border);
            margin-top: auto;
        }

        /* Plyr Customization */
        .plyr {
            --plyr-color-main: var(--primary);
            border-radius: 12px;
        }
    </style>
</head>
<body>

    <nav class="navbar">
        <span class="brand">FAST FINDER</span>
    </nav>

    <main class="main-container">
        
        <div class="video-wrapper">
            <video id="player" playsinline controls preload="metadata">
                <source src="{src}" type="{mime_type}" />
            </video>
        </div>

        <div class="info-card">
            <h1 class="file-title">{file_name}</h1>
            
            <div class="tags">
                <span class="tag hd">STREAM</span>
                <span class="tag">FAST SERVER</span>
                <span class="tag">NO ADS</span>
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
             Audio or Video not playing? Try using <b>VLC Player</b> or <b>MX Player</b> for the best experience.
        </div>

    </main>

    <footer>
        <p>&copy; 2025 Fast Finder Bot. All rights reserved.</p>
    </footer>

    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const player = new Plyr('#player', {
                controls: [
                    'play-large', 'play', 'progress', 'current-time', 'duration', 
                    'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'
                ],
                settings: ['captions', 'quality', 'speed'],
                keyboard: { focused: true, global: true },
            });
        });
    </script>
</body>
</html>
"""

# ... rest of the render_template.py code (media_watch function) ...
