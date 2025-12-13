import logging
import re
import asyncio
from struct import pack
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from pymongo import TEXT
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import DATA_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER
from datetime import datetime

logger = logging.getLogger(__name__)

# --- DATABASE CONNECTION ---
client = AsyncIOMotorClient(DATA_DATABASE_URL)
db = client[DATABASE_NAME]
instance = Instance(db)

# ==============================================================================
# 🗄️ DATABASE MODELS (SCHEMAS)
# ==============================================================================

# 1. Primary Collection
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
        indexes = [
            'file_name', # Normal Index
            ('file_name', TEXT) # Text Index for Fast Search
        ]

# 2. Backup Collection (Dual DB)
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
        indexes = [
            'file_name',
            ('file_name', TEXT)
        ]

# 3. Trending/Analytics Collection 📊
@instance.register
class SearchLogs(Document):
    query = fields.StrField(attribute='_id')
    count = fields.IntField(default=1)
    last_searched = fields.DateTimeField(allow_none=True)
    
    class Meta:
        collection_name = "search_analytics"

# ==============================================================================
# 🚀 SMART INDEXING (AUTO-OPTIMIZER)
# ==============================================================================
async def create_indexes():
    """
    Creates indexes on startup to make search 10x Faster.
    """
    try:
        await Media.ensure_indexes()
        await MediaBackup.ensure_indexes()
        # logger.info("✅ Database Indexes Created Successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to create indexes: {e}")

# Run indexing in background immediately
asyncio.create_task(create_indexes())

# ==============================================================================
# 📥 SAVE FILE (SMART ROUTING)
# ==============================================================================
async def save_file(media, target_db="primary"):
    """
    Saves file to Primary or Backup DB based on Admin's command.
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
    
    # Select Target Collection
    Collection = Media if target_db == "primary" else MediaBackup
    
    try:
        file = Collection(**entry)
        await file.commit()
        return 'suc'
    except DuplicateKeyError:
        return 'dup'
    except ValidationError:
        return 'err'

# ==============================================================================
# 🔍 GET SEARCH RESULTS (HYBRID ENGINE)
# ==============================================================================
async def get_search_results(query, file_type=None, max_results=10, offset=0, lang=None, mode="hybrid"):
    """
    Fetches files based on Admin's Mood (Mode: Primary/Backup/Hybrid)
    """
    query = query.strip()
    if not query: return [], 0, 0

    # 1. Log the Search (Analytics)
    asyncio.create_task(update_search_stats(query))

    # 2. Build Regex Query
    regex = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
    filter_q = {'file_name': regex}

    if USE_CAPTION_FILTER:
        filter_q = {'$or': [{'file_name': regex}, {'caption': regex}]}

    if file_type: filter_q['file_type'] = file_type

    # 3. Mode Logic (Admin Control)
    cursors = []
    if mode == "primary" or mode == "hybrid":
        cursors.append(Media.find(filter_q))
        
    if mode == "backup" or mode == "hybrid":
        cursors.append(MediaBackup.find(filter_q))

    # 4. Fetch Results (Merging)
    files = []
    total_results = 0
    
    for cursor in cursors:
        try:
            # Estimate count for speed
            count = await cursor.count()
            total_results += count
            
            # Sort by Newest First ($natural -1 is fast)
            cursor.sort('$natural', -1)
            
            # Fetch a batch (fetch extra to handle duplicates)
            batch_limit = max_results + offset + 20 
            files.extend(await cursor.to_list(length=batch_limit))
        except Exception as e:
            logger.error(f"DB Error: {e}")

    # 5. Smart Deduplication (Hybrid Mode Fix)
    # If file exists in both, show only one.
    unique_files = {}
    for f in files:
        if f.file_id not in unique_files:
            unique_files[f.file_id] = f

    # Convert back to list
    final_files = list(unique_files.values())

    # 6. Pagination Logic (Memory Slicing)
    sliced_files = final_files[offset : offset + max_results]
    
    next_offset = offset + len(sliced_files)
    if next_offset >= len(final_files) and next_offset >= total_results:
        next_offset = ""
    
    return sliced_files, next_offset, total_results

# ==============================================================================
# 🗑️ DELETE MANAGER (ADVANCED)
# ==============================================================================

# A. BULK DELETE (Regex)
async def delete_files(query, target="all"):
    """
    Deletes ALL files matching the query name.
    target: 'primary', 'backup', 'all'
    """
    regex = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
    filter_q = {'file_name': regex}
    
    deleted = 0
    
    if target in ["primary", "all"]:
        r1 = await Media.collection.delete_many(filter_q)
        deleted += r1.deleted_count
        
    if target in ["backup", "all"]:
        r2 = await MediaBackup.collection.delete_many(filter_q)
        deleted += r2.deleted_count
        
    return deleted

# B. SURGICAL DELETE (Single File by ID) - 🔥 MISSING FEATURE ADDED
async def delete_one_file(file_id, target="all"):
    """
    Deletes a specific file by its unique ID.
    Used in Interactive Mode.
    """
    deleted = 0
    filter_q = {'file_id': file_id}
    
    if target in ["primary", "all"]:
        r1 = await Media.collection.delete_one(filter_q)
        deleted += r1.deleted_count
        
    if target in ["backup", "all"]:
        r2 = await MediaBackup.collection.delete_one(filter_q)
        deleted += r2.deleted_count
        
    return deleted

# ==============================================================================
# 📊 ANALYTICS SYSTEM
# ==============================================================================
async def update_search_stats(query):
    """
    Tracks what users are searching for.
    """
    try:
        clean_q = re.sub(r'[^\w\s]', '', query).lower().strip()
        if len(clean_q) < 3: return 

        await SearchLogs.collection.update_one(
            {'_id': clean_q},
            {
                '$inc': {'count': 1}, 
                '$set': {'last_searched': datetime.now()}
            },
            upsert=True
        )
    except: pass

# ==============================================================================
# 🛠️ UTILITIES
# ==============================================================================
async def get_file_details(file_id):
    # Try Primary
    file = await Media.find_one({'file_id': file_id})
    if file: return file
    # Try Backup
    file = await MediaBackup.find_one({'file_id': file_id})
    return file

async def db_count_documents():
    pri = await Media.count_documents({})
    bak = await MediaBackup.count_documents({})
    return pri, bak, (pri + bak)
