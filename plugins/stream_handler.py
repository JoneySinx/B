import logging
# 🔥 FIX: Add missing imports for Python Typing
from typing import Union, Optional, AsyncGenerator 
from hydrogram.types import Message
from utils import temp

logger = logging.getLogger(__name__)

class StreamHandler:
    """
    Handles streaming logic for web playback and direct file downloads.
    This class can be initialized by the Bot instance.
    """
    def __init__(self, client):
        self.client = client

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["Message", None]]:
        """
        Generates messages for a given chat_id range.
        This is a custom Hydrogram iterator replacement.
        """
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            
            # Use the Bot client to get messages
            messages = await self.client.get_messages(chat_id, list(range(current, current + new_diff + 1)))
            for message in messages:
                yield message
                current += 1
                
    async def stream_media(self, message: Message, limit: int = 0, offset: int = 0) -> AsyncGenerator[bytes, None]:
        """
        Custom generator to stream media chunks for Web Player.
        Required by web/route.py
        """
        try:
            # Placeholder Logic (Replace with your TGCustomYield if available)
            media = getattr(message, message.media.value, None)
            if not media:
                raise ValueError("Message does not contain media.")
                
            logger.warning("Using Placeholder Stream Logic. Replace with TGCustomYield.")
            
            async for chunk in self.client.stream_media(message, offset=offset, limit=limit):
                 yield chunk
                 
        except Exception as e:
            logger.error(f"Streaming Error in StreamHandler: {e}")
            raise e
