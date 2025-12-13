import logging
import re
import base64
import asyncio
from struct import pack
from hydrogram.file_id import FileId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT
from pymongo.errors import DuplicateKeyError
from info import DATA_DATABASE_URL, DATABASE_NAME, COLLECTION_NAME, MAX_BTN, USE_CAPTION_FILTER

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(DATA_DATABASE_URL)
db = client[DATABASE_NAME]

# --- 🗄️ DUAL DATABASE COLLECTIONS ---
# 1. Primary DB (Safe Files)
col_main = db[COLLECTION_NAME]
# 2. Backup DB (Risky Files)
col_backup = db[f"{COLLECTION_NAME}_backup"]
# 3. Config DB (Router Rules & Settings)
col_config = db["bot_configuration"]

# --- ⚡ COMPILED REGEX (Stronger & Optimized) ---
RE_SPECIAL = re.compile(r"[\.\+\-_]")
RE_USERNAMES = re.compile(r"@\w+")
RE_BRACKETS = re.compile(r"[\[\(\{].*?[\]\}\)]")
RE_EXTENSIONS = re.compile(r"(\.|\b)(mkv|mp4|avi|m4v|webm|flv|mov|wmv|3gp|mpg|mpeg|hevc|h264)\b", re.IGNORECASE)
RE_SPACES = re.compile(r"\s+")

# --- 🛠️ INDEXING HELPER ---
async def create_text_index():
    # दोनों कलेक्शन में इंडेक्स बनाएँ
    try:
        await col_main.create_index([("file_name", TEXT), ("caption", TEXT)], name="main_search_index")
        await col_backup.create_index([("file_name", TEXT), ("caption", TEXT)], name="backup_search_index")
    except Exception as e:
        logger.warning(f"Index Error: {e}")

# --- 🧹 CLEANING FUNCTION ---
def clean_text(text):
    if not text: return ""
    text = str(text)
    
    # 1. Remove unwanted patterns
    text = RE_USERNAMES.sub("", text)
    text = RE_BRACKETS.sub("", text)
    text = RE_EXTENSIONS.sub("", text) # Remove extensions like .mkv
    text = RE_SPECIAL.sub(" ", text)
    
    # 2. Fix Spaces
    text = RE_SPACES.sub(" ", text).strip()
    
    # 3. Naming Convention
    text = text.title()
    text = text.replace(" L ", " l ") # Fix 'L' to 'l'
    
    return text

# --- 🚦 ROUTING & CONFIG LOGIC ---
async def get_target_db(channel_id):
    """
    चेक करता है कि इस चैनल की फाइल किस DB में जानी चाहिए।
    Default: 'primary'
    """
    try:
        rule = await col_config.find_one({'_id': 'channel_routes'})
        if rule and str(channel_id) in rule.get('routes', {}):
            return rule['routes'][str(channel_id)] # returns 'backup' or 'primary'
    except: pass
    return 'primary'

async def set_route(channel_id, target):
    """
    एडमिन पैनल से रूट सेट करने के लिए।
    target: 'primary' or 'backup'
    """
    await col_config.update_one(
        {'_id': 'channel_routes'},
        {'$set': {f"routes.{channel_id}": target}},
        upsert=True
    )

# --- 💾 SAVE FILE (SMART DUAL DB) ---
async def save_file(media, target_db="primary"):
    """
    target_db: 'primary' (Default) or 'backup'
    """
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_text(media.file_name)
    file_caption = clean_text(media.caption)
    
    document = {
        '_id': file_id,
        'file_name': file_name,
        'file_size': media.file_size,
        'caption': file_caption,
        'file_type': media.file_type,
        'mime_type': media.mime_type
    }
    
    # सही कलेक्शन चुनें
    collection = col_backup if target_db == 'backup' else col_main
    
    try:
        await collection.insert_one(document)
        logger.info(f"✅ Saved to [{target_db.upper()}]: {file_name[:50]}...") 
        return 'suc'
    except DuplicateKeyError:
        return 'dup'
    except Exception as e:
        logger.error(f"Save Error: {e}")
        return 'err'

# --- 🔄 UPDATE FILE (GLOBAL UPDATE) ---
async def update_file(media):
    # अपडेट दोनों जगह ट्राई करेगा क्योंकि हमें नहीं पता फाइल कहाँ है (Primary में या Backup में)
    file_id = unpack_new_file_id(media.file_id)
    file_name = clean_text(media.file_name)
    file_caption = clean_text(media.caption)
    
    update_data = {'$set': {'file_name': file_name, 'caption': file_caption, 'file_size': media.file_size}}
    
    res1 = await col_main.update_one({'_id': file_id}, update_data)
    res2 = await col_backup.update_one({'_id': file_id}, update_data)
    
    if res1.modified_count or res2.modified_count:
        logger.info(f"📝 Updated: {file_name[:50]}...")
        return 'suc'
    return 'err'

# --- 🔍 SMART SEARCH (HYBRID LOGIC) ---
async def get_search_results(query, max_results=MAX_BTN, offset=0, lang=None, mode="hybrid"):
    """
    mode: 'primary', 'backup', or 'hybrid'
    """
    query = str(query).strip().lower()
    query = RE_SPECIAL.sub(" ", query)
    query = RE_SPACES.sub(" ", query).strip()

    if not query: return [], "", 0

    # 1. सर्च क्वेरी बनाओ
    if lang: filter_dict = {'$text': {'$search': f'"{query}" "{lang}"'}}
    else: filter_dict = {'$text': {'$search': query}}
    
    regex_fallback = False
    
    # 2. कलेक्शन तय करो
    collections_to_search = []
    if mode == 'primary': collections_to_search = [col_main]
    elif mode == 'backup': collections_to_search = [col_backup]
    else: collections_to_search = [col_main, col_backup] # Hybrid Order: Primary First, then Backup

    # 3. सर्च एग्जीक्यूट करो
    final_files = []
    
    for col in collections_to_search:
        try:
            # Text Search
            cursor_count = await col.count_documents(filter_dict)
            if cursor_count > 0:
                cursor = col.find(filter_dict, {'score': {'$meta': 'textScore'}}).sort([('score', {'$meta': 'textScore'})])
                # Limit fetched results per DB to avoid memory overload
                found = [doc async for doc in cursor.limit(100)] 
                final_files.extend(found)
            else:
                regex_fallback = True
        except:
            regex_fallback = True
            
    # 4. Regex Fallback (अगर टेक्स्ट सर्च फेल हो)
    if not final_files and regex_fallback:
        words = query.split()
        if len(words) > 0:
            pattern = "".join(f"(?=.*{re.escape(word)})" for word in words)
            filt = {'$or': [{'file_name': {'$regex': pattern, '$options': 'i'}}, {'caption': {'$regex': pattern, '$options': 'i'}}]} if USE_CAPTION_FILTER else {'file_name': {'$regex': pattern, '$options': 'i'}}
            
            for col in collections_to_search:
                try:
                    found = [doc async for doc in col.find(filt).sort('_id', -1).limit(50)]
                    final_files.extend(found)
                except: pass

    # 5. Pagination Logic (Memory Slicing for Hybrid Results)
    total_count = len(final_files)
    
    start = offset
    end = offset + max_results
    sliced_files = final_files[start:end]
    
    next_offset = end if end < total_count else ""
    
    return sliced_files, next_offset, total_count

# --- 🗑️ DELETE FILES ---
async def delete_files(query):
    if not query:
        r1 = await col_main.delete_many({})
        r2 = await col_backup.delete_many({})
        return r1.deleted_count + r2.deleted_count
    
    filt = {'file_name': {'$regex': query, '$options': 'i'}}
    r1 = await col_main.delete_many(filt)
    r2 = await col_backup.delete_many(filt)
    return r1.deleted_count + r2.deleted_count

async def get_file_details(query):
    # दोनों में चेक करो
    doc = await col_main.find_one({'_id': query})
    if not doc:
        doc = await col_backup.find_one({'_id': query})
    return doc

# --- 📊 STATS FUNCTION (For Breakdown) ---
async def db_count_documents():
    """
    Returns: Primary Count, Backup Count, Total Count
    """
    c1 = await col_main.count_documents({})
    c2 = await col_backup.count_documents({})
    return c1, c2, c1 + c2

# --- FILE ID UTILS ---
def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0: n += 1
        else:
            if n: r += b"\x00" + bytes([n]); n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    decoded = FileId.decode(new_file_id)
    return encode_file_id(pack("<iiqq", int(decoded.file_type), decoded.dc_id, decoded.media_id, decoded.access_hash))
