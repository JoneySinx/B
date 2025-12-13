import time
import math
import logging
import secrets
import mimetypes
from aiohttp import web
from urllib.parse import quote
from utils import temp
from info import BIN_CHANNEL
from web.utils.render_template import media_watch
from hydrogram.errors import RPCError, FloodWait

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)

# ==============================================================================
# 🏥 HEALTH CHECK (KEEP-ALIVE)
# ==============================================================================
@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response({
        "server_status": "online",
        "bot": temp.U_NAME,
        "uptime": time.time() - temp.START_TIME
    })

# ==============================================================================
# 📺 WATCH PAGE
# ==============================================================================
@routes.get("/watch/{message_id}")
async def watch_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        return web.Response(text=await media_watch(message_id), content_type='text/html')
    except ValueError:
        return web.Response(text="Invalid Request", status=400)

# ==============================================================================
# 🖼️ SMART THUMBNAIL SERVER (WITH CACHING)
# ==============================================================================
@routes.get("/thumbnail/{message_id}")
async def thumbnail_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        
        # 1. Fetch Message
        msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
        media = getattr(msg, msg.media.value, None) if msg and msg.media else None
        
        if not media or not getattr(media, 'thumb', None):
            return web.Response(status=404, text="No Thumbnail")

        # 2. Download into Memory
        file = await temp.BOT.download_media(media.thumb.file_id, in_memory=True)
        
        # 3. God Mode: Add Cache Headers
        # यह ब्राउज़र को बोलेगा: "1 घंटे तक यह फोटो मेरे से मत मांगना, अपनी मेमोरी से उठा लो"
        return web.Response(
            body=file.getvalue(), 
            content_type='image/jpeg',
            headers={
                "Cache-Control": "public, max-age=3600" # Cache for 1 Hour
            }
        )
        
    except Exception as e:
        logger.error(f"Thumbnail Error: {e}")
        return web.Response(status=500)

# ==============================================================================
# 🚀 ULTRA STREAMER (RESUMABLE DOWNLOADS)
# ==============================================================================
@routes.get("/download/{message_id}")
async def stream_handler(request):
    try:
        message_id = int(request.match_info['message_id'])
        
        # 1. Get Message & Media
        msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
        if not msg or not msg.media:
            return web.Response(status=404, text="File Not Found")
            
        media = getattr(msg, msg.media.value, None)
        file_id = media.file_id
        file_size = media.file_size
        
        # 2. Fix Filename (Emoji & Space Handling)
        raw_name = getattr(media, 'file_name', 'default_file')
        file_name = quote(raw_name) # URL Encode
        mime_type = getattr(media, 'mime_type', mimetypes.guess_type(raw_name)[0] or 'application/octet-stream')

        # 3. Range Handling (For Seek/Resume)
        offset = 0
        limit = file_size
        headers = request.headers
        range_header = headers.get("Range")
        
        if range_header:
            parts = range_header.replace("bytes=", "").split("-")
            offset = int(parts[0]) if parts[0] else 0
            if len(parts) > 1 and parts[1]:
                limit = int(parts[1]) + 1 # End byte
        
        # Bounds Check
        if offset >= file_size:
            return web.Response(status=416, text="Requested Range Not Satisfiable")
            
        # Calculate Chunk Size
        content_length = limit - offset
        
        # 4. Response Headers
        resp_headers = {
            'Content-Type': mime_type,
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {offset}-{limit - 1}/{file_size}',
            'Content-Length': str(content_length),
            'Content-Disposition': f'attachment; filename="{raw_name}"; filename*=UTF-8\'\'{file_name}',
            'Cache-Control': 'no-cache' # Streaming shouldn't be cached aggressively
        }

        response = web.StreamResponse(
            status=206 if range_header else 200,
            reason='Partial Content' if range_header else 'OK',
            headers=resp_headers
        )
        
        await response.prepare(request)
        
        # 5. Stream Loop (The Engine)
        try:
            # 64KB Chunks for smooth streaming
            async for chunk in temp.BOT.stream_media(file_id, limit=content_length, offset=offset):
                await response.write(chunk)
                
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass # User closed the player/tab
        except RPCError as e:
            logger.warning(f"Telegram Stream Error: {e}")
        except Exception as e:
            logger.error(f"Stream Critical: {e}")
            
        return response
        
    except Exception as e:
        logger.error(f"Stream Handler Error: {e}")
        return web.Response(status=500)
