import math
import asyncio
import logging
from typing import Union
from hydrogram import Client, utils, raw
from hydrogram.session import Session, Auth
from hydrogram.errors import AuthBytesInvalid, RPCError, FloodWait
from hydrogram.types import Message
from hydrogram.file_id import FileId, FileType, ThumbnailSource
from utils import temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 🧠 STREAMING ENGINE CONFIG
# ==============================================================================
# Concurrent sessions lock to prevent race conditions
session_lock = asyncio.Lock()
# Retry limit for Telegram API calls
MAX_RETRIES = 5

async def chunk_size(length):
    """
    Dynamically calculates chunk size based on file length.
    Optimized for streaming players.
    """
    return 2 ** max(min(math.ceil(math.log2(length / 1024)), 10), 2) * 1024

async def offset_fix(offset, chunksize):
    """
    Aligns offset to chunk boundaries.
    """
    offset -= offset % chunksize
    return offset

class TGCustomYield:
    def __init__(self):
        """
        A custom method to stream files directly from Telegram MTProto.
        Supports Multi-DC and Range Requests (Seeking).
        """
        self.main_bot = temp.BOT

    @staticmethod
    async def generate_file_properties(msg: Message):
        """
        Decodes FileID to get DC_ID and other metadata.
        """
        media = getattr(msg, msg.media.value, None)
        file_id_obj = FileId.decode(media.file_id)
        return file_id_obj

    async def generate_media_session(self, client: Client, msg: Message):
        """
        Creates a dedicated session for the specific Data Center (DC).
        This prevents 'Worker Busy' errors on the main bot.
        """
        data = await self.generate_file_properties(msg)

        async with session_lock:
            # Check if we already have a session for this DC
            media_session = client.media_sessions.get(data.dc_id, None)

            if media_session is None:
                # If DC is different from Main Bot's DC, create new session
                if data.dc_id != await client.storage.dc_id():
                    media_session = Session(
                        client, 
                        data.dc_id, 
                        await Auth(client, data.dc_id, await client.storage.test_mode()).create(),
                        await client.storage.test_mode(), 
                        is_media=True
                    )
                    await media_session.start()

                    # Authorization Transfer (Export -> Import)
                    for _ in range(3):
                        try:
                            exported_auth = await client.invoke(
                                raw.functions.auth.ExportAuthorization(
                                    dc_id=data.dc_id
                                )
                            )
                            await media_session.send(
                                raw.functions.auth.ImportAuthorization(
                                    id=exported_auth.id,
                                    bytes=exported_auth.bytes
                                )
                            )
                            break
                        except AuthBytesInvalid:
                            continue
                        except Exception as e:
                            logger.error(f"Failed to export auth to DC {data.dc_id}: {e}")
                            await media_session.stop()
                            raise e
                    else:
                        await media_session.stop()
                        raise AuthBytesInvalid
                else:
                    # Same DC, just create a media session
                    media_session = Session(
                        client, 
                        data.dc_id, 
                        await client.storage.auth_key(),
                        await client.storage.test_mode(), 
                        is_media=True
                    )
                    await media_session.start()

                client.media_sessions[data.dc_id] = media_session

        return media_session

    @staticmethod
    async def get_location(file_id: FileId):
        """
        Converts FileID to InputFileLocation for MTProto.
        """
        file_type = file_id.file_type

        if file_type == FileType.CHAT_PHOTO:
            if file_id.chat_id > 0:
                peer = raw.types.InputPeerUser(
                    user_id=file_id.chat_id,
                    access_hash=file_id.chat_access_hash
                )
            else:
                if file_id.chat_access_hash == 0:
                    peer = raw.types.InputPeerChat(chat_id=-file_id.chat_id)
                else:
                    peer = raw.types.InputPeerChannel(
                        channel_id=utils.get_channel_id(file_id.chat_id),
                        access_hash=file_id.chat_access_hash
                    )

            location = raw.types.InputPeerPhotoFileLocation(
                peer=peer,
                volume_id=file_id.volume_id,
                local_id=file_id.local_id,
                big=file_id.thumbnail_source == ThumbnailSource.CHAT_PHOTO_BIG
            )
        elif file_type == FileType.PHOTO:
            location = raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size
            )
        else:
            location = raw.types.InputDocumentFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size
            )

        return location

    async def yield_file(self, media_msg: Message, offset: int, first_part_cut: int,
                         last_part_cut: int, part_count: int, chunk_size: int):
        """
        The Core Streaming Generator.
        Yields bytes chunk by chunk to the Web Server.
        """
        client = self.main_bot
        data = await self.generate_file_properties(media_msg)
        media_session = await self.generate_media_session(client, media_msg)

        current_part = 1
        location = await self.get_location(data)

        r = None
        
        # 1. Fetch First Chunk (with Retries)
        for attempt in range(MAX_RETRIES):
            try:
                r = await media_session.send(
                    raw.functions.upload.GetFile(
                        location=location,
                        offset=offset,
                        limit=chunk_size
                    ),
                )
                break
            except (asyncio.TimeoutError, RPCError, FloodWait) as e:
                if isinstance(e, FloodWait):
                    await asyncio.sleep(e.value)
                elif attempt == MAX_RETRIES - 1:
                    logger.error(f"Failed to fetch initial chunk: {e}")
                    return
                await asyncio.sleep(1)
                continue
        
        if r is None:
            return

        # 2. Stream Loop
        if isinstance(r, raw.types.upload.File):
            while current_part <= part_count:
                chunk = r.bytes
                if not chunk:
                    break
                
                # Slicing logic for range requests
                if current_part == 1:
                    yield chunk[first_part_cut:]
                elif current_part == part_count:
                    yield chunk[:last_part_cut]
                else:
                    yield chunk

                # Prepare next offset
                offset += chunk_size
                current_part += 1

                if current_part <= part_count:
                    success = False
                    for attempt in range(MAX_RETRIES):
                        try:
                            r = await media_session.send(
                                raw.functions.upload.GetFile(
                                    location=location,
                                    offset=offset,
                                    limit=chunk_size
                                ),
                            )
                            success = True
                            break
                        except (asyncio.TimeoutError, RPCError, FloodWait) as e:
                            if isinstance(e, FloodWait):
                                await asyncio.sleep(e.value)
                            await asyncio.sleep(0.5)
                            continue
                    
                    if not success:
                        logger.error(f"Stream aborted: Failed chunk {current_part}")
                        break
