import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import DATA_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER
from database.users_chats_db import db as config_db # Config fetch karne ke liye

logger = logging.getLogger(__name__)
client = AsyncIOMotorClient(DATA_DATABASE_URL)
db = client[DATABASE_NAME]
instance = Instance(db)

# --- DUAL COLLECTIONS ---
# Primary Collection
@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)
    class Meta:
        collection_name = COLLECTION_NAME

# Backup Collection (New)
@instance.register
class MediaBackup(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)
    class Meta:
        collection_name = f"{COLLECTION_NAME}_backup"

# --- SAVE FILE (SMART ROUTING) ---
async def save_file(media, target_db="primary"):
    """
    target_db: 'primary' or 'backup'
    """
    entry = {
        "file_id": media.file_id,
        "file_ref": media.file_ref,
        "file_name": media.file_name,
        "file_size": media.file_size,
        "file_type": media.media.value,
        "mime_type": media.mime_type,
        "caption": media.caption.html if media.caption else None,
    }
    
    # Select Collection
    Collection = Media if target_db == "primary" else MediaBackup
    
    try:
        file = Collection(**entry)
        await file.commit()
        return 'suc'
    except DuplicateKeyError:
        return 'dup'
    except ValidationError:
        return 'err'

# --- GET SEARCH RESULTS (THE HYBRID ENGINE) ---
async def get_search_results(query, file_type=None, max_results=10, offset=0, lang=None, mode="hybrid"):
    """
    mode: 'primary', 'backup', 'hybrid' (Controlled by Admin Panel)
    """
    query = query.strip()
    if not query: return [], 0, 0

    # Regex Query
    regex = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
    filter_q = {'file_name': regex}

    if USE_CAPTION_FILTER:
        filter_q = {'$or': [{'file_name': regex}, {'caption': regex}]}

    if file_type: filter_q['file_type'] = file_type

    # --- MODE LOGIC ---
    cursors = []
    
    if mode == "primary" or mode == "hybrid":
        cursors.append(Media.find(filter_q))
        
    if mode == "backup" or mode == "hybrid":
        cursors.append(MediaBackup.find(filter_q))

    # Fetching & Merging
    files = []
    total_results = 0
    
    # Note: Sorting & Pagination in Hybrid mode is complex. 
    # We will fetch a bit more and merge for best experience.
    
    for cursor in cursors:
        # Count
        count = await cursor.count()
        total_results += count
        
        # Sort & Skip
        cursor.sort('$natural', -1)
        cursor.skip(offset)
        cursor.limit(max_results)
        
        files.extend(await cursor.to_list(length=max_results))

    # Remove Duplicates (if any in Hybrid) & Slice
    unique_files = {f.file_id: f for f in files}.values()
    final_files = list(unique_files)[:max_results]
    
    # Calculate Next Offset
    next_offset = offset + len(final_files)
    if next_offset >= total_results: next_offset = ""
    
    return final_files, next_offset, total_results

# --- GET FILE DETAILS ---
async def get_file_details(file_id):
    # Try Primary
    file = await Media.find_one({'file_id': file_id})
    if file: return file
    # Try Backup
    file = await MediaBackup.find_one({'file_id': file_id})
    return file

# --- COUNT DOCS ---
async def db_count_documents():
    pri = await Media.count_documents({})
    bak = await MediaBackup.count_documents({})
    return pri, bak, (pri + bak)

# --- DELETE FILES ---
async def delete_files(query):
    regex = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
    filter_q = {'file_name': regex}
    
    # Delete from BOTH to be safe
    r1 = await Media.collection.delete_many(filter_q)
    r2 = await MediaBackup.collection.delete_many(filter_q)
    
    return r1.deleted_count + r2.deleted_count
