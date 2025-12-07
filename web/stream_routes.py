import math
import logging
import secrets
import mimetypes
from aiohttp import web
from info import BIN_CHANNEL
from utils import temp
from web.utils.custom_dl import TGCustomYield, chunk_size, offset_fix
from web.utils.render_template import media_watch

routes = web.RouteTableDef()
logger = logging.getLogger(__name__)

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    """Health check route"""
    return web.Response(
        text='<h1 align="center"><a href="https://t.me/YourX"><b>YourX Bot is Running</b></a></h1>',
        content_type='text/html'
    )

@routes.get("/watch/{message_id}")
async def watch_handler(request):
    """Stream video in browser"""
    try:
        message_id = int(request.match_info['message_id'])
        return web.Response(text=await media_watch(message_id), content_type='text/html')
    except ValueError:
        return web.Response(text="<h1>Invalid Message ID</h1>", status=400, content_type='text/html')
    except Exception as e:
        logger.error(f"Watch Error: {e}")
        return web.Response(text="<h1>Internal Server Error</h1>", status=500, content_type='text/html')

@routes.get("/download/{message_id}")
async def download_handler(request):
    """Direct download link"""
    try:
        message_id = int(request.match_info['message_id'])
        return await media_download(request, message_id)
    except ValueError:
        return web.Response(text="<h1>Invalid Message ID</h1>", status=400, content_type='text/html')
    except Exception as e:
        logger.error(f"Download Error: {e}")
        return web.Response(text="<h1>File Not Found or Error Occurred</h1>", status=404, content_type='text/html')

async def media_download(request, message_id: int):
    # 1. Get the message from Telegram
    try:
        media_msg = await temp.BOT.get_messages(BIN_CHANNEL, message_id)
    except Exception as e:
        logger.error(f"Failed to fetch message {message_id}: {e}")
        return web.Response(status=404, text="File not found")

    # 2. Extract media object
    media = getattr(media_msg, media_msg.media.value, None) if media_msg and media_msg.media else None
    
    if not media:
        return web.Response(status=404, text="No media found in this message")

    file_size = getattr(media, 'file_size', 0)
    
    # 3. Handle Filename and MIME Type properly
    file_name = getattr(media, 'file_name', None)
    
    if not file_name:
        # Generate random name with correct extension if possible
        guess_ext = mimetypes.guess_extension(getattr(media, 'mime_type', '')) or ".bin"
        file_name = f"{secrets.token_hex(4)}{guess_ext}"
    
    mime_type = getattr(media, 'mime_type', None)
    if not mime_type:
        # Fix: mimetypes.guess_type returns tuple (type, encoding)
        mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    # 4. Handle Range Headers (Streaming Logic)
    range_header = request.headers.get('Range', 0)
    
    if range_header:
        try:
            from_bytes, until_bytes = range_header.replace('bytes=', '').split('-')
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
        except ValueError:
            from_bytes = 0
            until_bytes = file_size - 1
    else:
        # Use aiohttp built-in range parser if available or default
        from_bytes = 0
        until_bytes = file_size - 1

    # Ensure valid range
    if from_bytes >= file_size or until_bytes >= file_size:
         return web.Response(status=416, headers={"Content-Range": f"bytes */{file_size}"})

    req_length = until_bytes - from_bytes + 1
    
    # 5. Calculate Chunks for Telegram
    try:
        new_chunk_size = await chunk_size(req_length)
        offset = await offset_fix(from_bytes, new_chunk_size)
        first_part_cut = from_bytes - offset
        last_part_cut = (until_bytes % new_chunk_size) + 1
        part_count = math.ceil(req_length / new_chunk_size)
        
        # Initiate the custom generator
        body = TGCustomYield().yield_file(
            media_msg, offset, first_part_cut, last_part_cut, part_count, new_chunk_size
        )
    except Exception as e:
        logger.error(f"Chunk calculation error: {e}")
        return web.Response(status=500, text="Streaming Error")

    # 6. Build Response Headers
    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'attachment; filename="{file_name}"',
    }
    
    if range_header:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"
        headers["Content-Length"] = str(req_length)
        return web.Response(status=206, body=body, headers=headers)
    else:
        headers["Content-Length"] = str(file_size)
        return web.Response(status=200, body=body, headers=headers)
