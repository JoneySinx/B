import logging
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from info import (
    DATABASE_NAME, DATA_DATABASE_URL, 
    PROTECT_CONTENT, IMDB, SPELL_CHECK, 
    AUTO_DELETE, WELCOME, WELCOME_TEXT, IMDB_TEMPLATE, FILE_CAPTION, 
    SHORTLINK_URL, SHORTLINK_API, SHORTLINK, TUTORIAL, LINK_MODE, 
    BOT_ID
)

logger = logging.getLogger(__name__)

# --- MongoDB Connection ---
mongo_client = AsyncIOMotorClient(DATA_DATABASE_URL)
db_instance = mongo_client[DATABASE_NAME]

class Database:
    # --- Defaults ---
    default_setgs = {
        'file_secure': PROTECT_CONTENT,
        'imdb': IMDB,
        'spell_check': SPELL_CHECK,
        'auto_delete': AUTO_DELETE,
        'welcome': WELCOME,
        'welcome_text': WELCOME_TEXT,
        'template': IMDB_TEMPLATE,
        'caption': FILE_CAPTION,
        'url': SHORTLINK_URL,
        'api': SHORTLINK_API,
        'shortlink': SHORTLINK,
        'tutorial': TUTORIAL,
        'links': LINK_MODE
    }

    default_verify = {
        'is_verified': False,
        'verified_time': 0,
        'verify_token': "",
        'link': "",
        'expire_time': 0
    }
    
    default_prm = {
        'expire': '',
        'trial': False,
        'plan': '',
        'premium': False
    }

    def __init__(self):
        self.col = db_instance.Users
        self.grp = db_instance.Groups
        self.prm = db_instance.Premiums
        self.stg = db_instance.Settings
        self.filters = db_instance.Filters
        self.note = db_instance.Notes
        
        # Simple Cache for Bot Settings (To reduce DB calls)
        self.settings_cache = None

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
            verify_status=self.default_verify
        )

    def new_group(self, id, title):
        return dict(
            id = id,
            title = title,
            chat_status=dict(
                is_disabled=False,
                reason="",
            ),
            settings=self.default_setgs
        )
    
    # --- STORAGE STATS ---
    async def get_db_size(self):
        try:
            stats = await db_instance.command("dbstats")
            used = stats.get('dataSize', 0)
            limit = 536870912 # 512MB
            free = limit - used
            return used, free
        except Exception:
            return 0, 0

    # --- INDEX CHANNELS ---
    async def add_index_channel(self, chat_id):
        await self.stg.update_one(
            {'id': BOT_ID},
            {'$addToSet': {'index_channels': int(chat_id)}},
            upsert=True
        )

    async def remove_index_channel(self, chat_id):
        await self.stg.update_one(
            {'id': BOT_ID},
            {'$pull': {'index_channels': int(chat_id)}}
        )

    async def get_index_channels_db(self):
        doc = await self.stg.find_one({'id': BOT_ID})
        return doc.get('index_channels', []) if doc else []

    # --- FILTERS ---
    async def add_filter(self, chat_id, name, filter_data):
        name = name.lower().strip()
        await self.filters.update_one(
            {'chat_id': int(chat_id), 'name': name},
            {'$set': {'data': filter_data}},
            upsert=True
        )

    async def get_filter(self, chat_id, name):
        name = name.lower().strip()
        doc = await self.filters.find_one({'chat_id': int(chat_id), 'name': name})
        return doc['data'] if doc else None

    async def delete_filter(self, chat_id, name):
        name = name.lower().strip()
        result = await self.filters.delete_one({'chat_id': int(chat_id), 'name': name})
        return result.deleted_count > 0

    async def delete_all_filters(self, chat_id):
        await self.filters.delete_many({'chat_id': int(chat_id)})

    async def get_filters(self, chat_id):
        cursor = self.filters.find({'chat_id': int(chat_id)})
        return [doc['name'] async for doc in cursor]

    # --- USERS MANAGEMENT (Optimized with Upsert) ---
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        # Upsert=True prevents DuplicateKeyError crash
        await self.col.update_one({'id': int(id)}, {'$setOnInsert': user}, upsert=True)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id': int(id)})
        return bool(user)
    
    async def total_users_count(self):
        return await self.col.count_documents({})
    
    async def get_all_users(self):
        return self.col.find({})
    
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    # --- BAN SYSTEM ---
    async def remove_ban(self, id):
        await self.col.update_one(
            {'id': int(id)}, 
            {'$set': {'ban_status': {'is_banned': False, 'ban_reason': ''}}}
        )
    
    async def ban_user(self, user_id, ban_reason="Violation"):
        await self.col.update_one(
            {'id': int(user_id)}, 
            {'$set': {'ban_status': {'is_banned': True, 'ban_reason': ban_reason}}}
        )

    async def get_ban_status(self, id):
        user = await self.col.find_one({'id': int(id)})
        default = {'is_banned': False, 'ban_reason': ''}
        return user.get('ban_status', default) if user else default

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        chats = self.grp.find({'chat_status.is_disabled': True})
        b_chats = [chat['id'] async for chat in chats]
        b_users = [user['id'] async for user in users]
        return b_users, b_chats

    # --- GROUPS MANAGEMENT ---
    async def add_chat(self, chat_id, title):
        chat = self.new_group(chat_id, title)
        await self.grp.update_one({'id': int(chat_id)}, {'$setOnInsert': chat}, upsert=True)

    async def get_chat(self, chat_id):
        chat = await self.grp.find_one({'id': int(chat_id)})
        return chat.get('chat_status') if chat else False
    
    async def disable_chat(self, chat_id, reason="No Reason"):
        await self.grp.update_one(
            {'id': int(chat_id)}, 
            {'$set': {'chat_status': {'is_disabled': True, 'reason': reason}}}
        )

    async def re_enable_chat(self, chat_id):
        await self.grp.update_one(
            {'id': int(chat_id)}, 
            {'$set': {'chat_status': {'is_disabled': False, 'reason': ""}}}
        )

    async def total_chat_count(self):
        return await self.grp.count_documents({})
    
    async def get_all_chats(self):
        return self.grp.find({})

    # --- SETTINGS MANAGEMENT ---
    async def update_settings(self, id, settings):
        await self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})      
    
    async def get_settings(self, id):
        chat = await self.grp.find_one({'id': int(id)})
        return chat.get('settings', self.default_setgs) if chat else self.default_setgs

    # --- PREMIUM SYSTEM ---
    async def get_plan(self, id):
        st = await self.prm.find_one({'id': int(id)})
        return st['status'] if st else self.default_prm
    
    async def update_plan(self, id, data):
        await self.prm.update_one(
            {'id': int(id)}, 
            {'$set': {'status': data}}, 
            upsert=True
        )

    async def get_premium_count(self):
        return await self.prm.count_documents({'status.premium': True})
    
    async def get_premium_users(self):
        return self.prm.find({'status.premium': True})

    # --- BOT GLOBAL SETTINGS (With Caching) ---
    async def update_bot_sttgs(self, var, val):
        await self.stg.update_one(
            {'id': BOT_ID},
            {'$set': {var: val}},
            upsert=True
        )
        self.settings_cache = None # Clear cache to refresh on next get

    async def get_bot_sttgs(self):
        # Return cached settings if available
        if self.settings_cache:
            return self.settings_cache
            
        stg = await self.stg.find_one({'id': BOT_ID})
        if not stg:
            # Create default if not exists
            await self.stg.insert_one({'id': BOT_ID})
            stg = {}
        
        self.settings_cache = stg # Save to cache
        return stg

db = Database()
