import logging
import re
import base64
from struct import pack
from hydrogram.file_id import FileId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT
from pymongo.errors import DuplicateKeyError
from info import FILES_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, MAX_BTN

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(FILES_DATABASE_URL)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

async def save_file(media):
    """Save file in database"""
    file_id = unpack_new_file_id(media.file_id)
    file_name = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.file_name))
    file_caption = re.sub(r"@\w+|(_|\-|\.|\+)", " ", str(media.caption))
    
    document = {
        '_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': file_caption,
        'file_type': media.file_type,
        'mime_type': media.mime_type
    }
    
    try:
        await collection.insert_one(document)
        return 'suc'
    except DuplicateKeyError:
        return 'dup'
    except Exception:
        return 'err'

async def get_search_results(query, max_results=MAX_BTN, offset=0, lang=None):
    query = str(query).strip()
    if not query:
        return [], "", 0

    filter = {'$text': {'$search': query}} 
    
    try:
        total_results = await collection.count_documents(filter)
        cursor = collection.find(filter, {'score': {'$meta': 'textScore'}}).sort([('score', {'$meta': 'textScore'})])
        cursor.skip(offset).limit(max_results)
        files = [doc async for doc in cursor]

        next_offset = offset + len(files)
        if next_offset >= total_results or len(files) == 0:
            next_offset = ""
            
        return files, next_offset, total_results
        
    except Exception as e:
        logger.error(f"Search Error: {e}")
        return [], "", 0

async def get_file_details(query):
    try:
        file_details = await collection.find_one({'_id': query})
        return file_details
    except Exception:
        return None

def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    return file_id

async def db_count_documents():
     return await collection.count_documents({})

# Second DB function removed or kept dummy to avoid import errors in other files
async def second_db_count_documents():
     return 0

async def delete_files(query):
    query = query.strip()
    if not query: return 0
    filter = {'$text': {'$search': query}}
    result1 = await collection.delete_many(filter)
    return result1.deleted_count
