import logging
import re
import asyncio
from struct import pack
from hydrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from pymongo import TEXT
# 🔥 FIX: Specific Import for Motor AsyncIO to fix "Abstract Method" error
from umongo.frameworks.motor_asyncio import MotorAsyncIOInstance as Instance
from umongo import Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import DATABASE_URI, BACKUP_DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER
from datetime import datetime

logger = logging.getLogger(__name__)

# ==============================================================================
# 🗄️ DATABASE CONNECTION (DUAL ENGINE)
# ==============================================================================

# 1. Primary Engine (Main)
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance(db)

# 2. Secondary Engine (Backup - Optional)
if BACKUP_DATABASE_URI:
    client_bak = AsyncIOMotorClient(BACKUP_DATABASE_URI)
    db_bak = client_bak[DATABASE_NAME]
    instance_bak = Instance(db_bak)
else:
    # Use same DB but different collection for "Backup" simulation
    db_bak = db
    instance_bak = instance

# ==============================================================================
# 📝 DATABASE MODELS (SCHEMAS)
# ==============================================================================

# 1. Primary Collection
@instance.register
class Media(Document):
    file_id = fields.StringField(attribute='_id')
    file_ref = fields.StringField(allow_none=True)
    file_name = fields.StringField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StringField(allow_none=True)
    mime_type = fields.StringField(allow_none=True)
    caption = fields.StringField(allow_none=True)
    
    class Meta:
        collection_name = COLLECTION_NAME
        indexes = [
            'file_name', # Normal Index
            ('file_name', TEXT) # Text Index for Fast Search
        ]

# 2. Backup Collection (Dual DB)
@instance_bak.register
class MediaBackup(Document):
    file_id = fields.StringField(attribute='_id')
    file_ref = fields.StringField(allow_none=True)
    file_name = fields.StringField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StringField(allow_none=True)
    mime_type = fields.StringField(allow_none=True)
    caption = fields.StringField(allow_none=True)
    
    class Meta:
        collection_name = COLLECTION_NAME if BACKUP_DATABASE_URI else f"{COLLECTION_NAME}_backup"
        indexes = [
            'file_name',
            ('file_name', TEXT)
        ]

# 3. Trending/Analytics Collection 📊
@instance.register
class SearchLogs(Document):
    query = fields.StringField(attribute='_id')
    count = fields.IntField(default=1)
    last_searched = fields.DateTimeField(allow_none=True)
    
    class Meta:
        collection_name = "search_analytics"

# ==============================================================================
# 🚀 SMART INDEXING (AUTO-OPTIMIZER)
# ==============================================================================
async def create_indexes():
    try:
        await Media.ensure_indexes()
        await MediaBackup.ensure_indexes()
    except Exception as e:
        logger.error(f"❌ Failed to create indexes: {e}")

asyncio.create_task(create_indexes())

# ==============================================================================
# 📥 SAVE FILE
# ==============================================================================
async def save_file(media, target_db="primary"):
    entry = {
        "file_id": media.file_id,
        "file_ref": media.file_ref,
        "file_name": media.file_name,
        "file_size": media.file_size,
        "file_type": media.media.value,
        "mime_type": media.mime_type,
        "caption": media.caption if media.caption else None,
    }
    
    saved = []
    
    if target_db in ["primary", "both"]:
        try:
            file = Media(**entry)
            await file.commit()
            saved.append('primary')
        except DuplicateKeyError:
            saved.append('primary_dup')
        except Exception as e:
            logger.error(f"Save Primary Error: {e}")

    if target_db in ["backup", "both"]:
        try:
            file = MediaBackup(**entry)
            await file.commit()
            saved.append('backup')
        except DuplicateKeyError:
            saved.append('backup_dup')
        except Exception as e:
            logger.error(f"Save Backup Error: {e}")
            
    return saved

# ==============================================================================
# 🔍 GET SEARCH RESULTS (HYBRID & FUZZY ENGINE)
# ==============================================================================
async def get_search_results(query, file_type=None, max_results=10, offset=0, mode="hybrid"):
    """
    Fetches files using Normal or Fuzzy/Text Search based on mode.
    Mode: 'hybrid', 'primary', 'backup', 'fuzzy'
    """
    query = query.strip()
    if not query: return [], 0, 0

    asyncio.create_task(update_search_stats(query))

    cursors = []
    total_results = 0
    
    # 1. Determine Filter Query based on mode
    if mode == "fuzzy":
        # 🔥 FUZZY/TEXT SEARCH LOGIC (Faster for large DBs and misspellings)
        words = query.split()
        # Ensure that ALL words are present (AND operation)
        text_query = " ".join(words)
        filter_q = {'$text': {'$search': text_query}}
        # Filter files by type if specified
        if file_type: filter_q['file_type'] = file_type
        
        # We search both collections simultaneously for fuzzy results
        cursors.append(Media.find(filter_q))
        cursors.append(MediaBackup.find(filter_q))

    else:
        # NORMAL REGEX SEARCH (Used for precise match or initial pass)
        regex = re.compile(f".*{re.escape(query)}.*", re.IGNORECASE)
        filter_q = {'file_name': regex}

        if USE_CAPTION_FILTER:
            filter_q = {'$or': [{'file_name': regex}, {'caption': regex}]}

        if file_type: filter_q['file_type'] = file_type

        if mode == "primary" or mode == "hybrid":
            cursors.append(Media.find(filter_q))
            
        if mode == "backup" or mode == "hybrid":
            cursors.append(MediaBackup.find(filter_q))

    # 2. Fetch Results (Merging and Deduplication)
    files = []
    
    for cursor in cursors:
        try:
            count = await cursor.count()
            total_results += count
            
            # Sort by relevance for fuzzy search, or newest for normal search
            if mode == "fuzzy":
                cursor.sort([('score', {'$meta': 'textScore'}), ('$natural', -1)])
            else:
                cursor.sort('$natural', -1)
                
            batch_limit = max_results + offset + 20 
            files.extend(await cursor.to_list(length=batch_limit))
        except Exception as e:
            logger.error(f"DB Fetch Error: {e}")

    unique_files = {}
    for f in files:
        # Check if score exists and is above a threshold for fuzzy search (optional refinement)
        # if mode == "fuzzy" and f.score < 0.7: continue 
        if f.file_id not in unique_files:
            unique_files[f.file_id] = f

    final_files = list(unique_files.values())

    # 3. Pagination Logic
    sliced_files = final_files[offset : offset + max_results]
    
    next_offset = offset + len(sliced_files)
    if next_offset >= len(final_files):
        next_offset = ""
    
    return sliced_files, next_offset, total_results

# ==============================================================================
# 🗑️ DELETE MANAGER
# ==============================================================================

# A. BULK DELETE (Regex)
async def delete_files(query, target="all"):
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

# B. SURGICAL DELETE (Single File by ID)
async def delete_one_file(file_id, target="all"):
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
    file = await Media.find_one({'file_id': file_id})
    if file: return file
    file = await MediaBackup.find_one({'file_id': file_id})
    return file

async def db_count_documents():
    pri = await Media.count_documents({})
    bak = await MediaBackup.count_documents({})
    return pri, bak, (pri + bak)
