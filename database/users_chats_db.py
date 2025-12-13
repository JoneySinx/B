import logging
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_NAME, DATA_DATABASE_URL

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        # --- COLLECTIONS ---
        self.col = self.db.users
        self.grp = self.db.groups
        self.ban = self.db.banned
        self.prm = self.db.premium_users
        self.verify = self.db.verify_status  # For Verification/Ads
        self.notes = self.db.notes           # For Saved Notes
        self.filters = self.db.filters       # For Custom Filters
        
        # 🔥 NEW: Configuration Collection for Admin Panel
        self.conf = self.db.bot_settings
        
        # 🔥 NEW: Clone Collection
        self.clones = self.db.clones

    # ==========================================================================
    # ⚙️ ADMIN PANEL / DYNAMIC CONFIG
    # ==========================================================================
    
    async def get_config(self):
        """
        Fetches dynamic bot settings. Creates default if missing.
        """
        config = await self.conf.find_one({'_id': 'main_config'})
        if not config:
            default_config = {
                '_id': 'main_config',
                'search_mode': 'hybrid',     # primary / backup / hybrid
                'shortlink_enable': False,
                'shortlink_api': '',
                'shortlink_site': '',
                'auth_channel': None,
                'req_channel': None,
                'is_maintenance': False,
                'maintenance_reason': 'Updating Server...',
                'is_verify': False,
                'verify_duration': 86400,
                'is_premium_active': True,
                'is_protect_content': True,
                'delete_mode': 'interactive', # interactive / general
                'delete_time': 300,
                'dual_save_mode': True,
                'disable_clone': False,
                'tpl_start_msg': None,       # Custom Templates
                'tpl_help_msg': None,
                'restart_status': None       # To track restart msg
            }
            await self.conf.insert_one(default_config)
            return default_config
        return config

    async def update_config(self, key, value):
        """
        Updates a specific setting in the config.
        """
        await self.conf.update_one(
            {'_id': 'main_config'},
            {'$set': {key: value}},
            upsert=True
        )

    async def get_index_channels_db(self):
        """
        Returns list of indexed channels stored in DB (Dynamic Adding).
        """
        # For now, we rely on ENV, but this allows future expansion via /index command logic if needed
        # Or we can store specific channel list in config
        conf = await self.get_config()
        return conf.get('db_index_channels', [])

    # ==========================================================================
    # 👤 USER MANAGEMENT
    # ==========================================================================

    async def new_user(self, id):
        return {
            'id': id,
            'join_date': datetime.datetime.now().date(),
            'ban_status': {
                'is_banned': False,
                'ban_reason': ''
            }
        }

    async def add_user(self, id):
        user = await self.new_user(id)
        if not await self.is_user_exist(id):
            await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'id': int(id)})
        return True if user else False

    async def total_users_count(self):
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    # ==========================================================================
    # 🏘️ GROUP MANAGEMENT & SETTINGS
    # ==========================================================================

    async def add_chat(self, chat, title):
        if not await self.grp.find_one({'id': int(chat)}):
            chat_data = {
                'id': int(chat),
                'name': title,
                'settings': {
                    'auto_filter': True,
                    'spell_check': True,
                    'auto_delete': False,
                    'welcome': True,
                    'protect': False,
                    'template': None,
                    'caption': None
                }
            }
            await self.grp.insert_one(chat_data)

    async def get_chat(self, chat):
        return await self.grp.find_one({'id': int(chat)})
    
    async def get_settings(self, chat_id):
        chat = await self.get_chat(chat_id)
        if chat:
            return chat.get('settings', {})
        # Return defaults if chat not found (rare)
        return {'auto_filter': True, 'spell_check': True, 'welcome': True}

    async def update_settings(self, chat_id, settings):
        await self.grp.update_one({'id': int(chat_id)}, {'$set': {'settings': settings}})
        
    async def get_bot_sttgs(self):
        # Legacy support call
        return {'AUTO_FILTER': True}

    async def total_chat_count(self):
        return await self.grp.count_documents({})

    async def get_all_chats(self):
        return self.grp.find({})

    # ==========================================================================
    # 🚫 BAN MANAGEMENT (USERS & CHATS)
    # ==========================================================================

    async def add_banned_user(self, id, reason="Violated Rules"):
        # Add to simple banned list and update user profile
        await self.ban.update_one({'id': int(id)}, {'$set': {'id': int(id), 'reason': reason}}, upsert=True)
        await self.col.update_one({'id': int(id)}, {'$set': {'ban_status.is_banned': True, 'ban_status.ban_reason': reason}})

    async def remove_banned_user(self, id):
        await self.ban.delete_one({'id': int(id)})
        await self.col.update_one({'id': int(id)}, {'$set': {'ban_status.is_banned': False}})

    async def get_ban_status(self, id):
        return await self.ban.find_one({'id': int(id)})

    async def get_banned(self):
        users = [b['id'] async for b in self.ban.find({})]
        return users, [] # Returning empty list for chats for now

    # ==========================================================================
    # 💎 PREMIUM MANAGEMENT
    # ==========================================================================

    async def get_plan(self, user_id):
        user = await self.prm.find_one({'id': int(user_id)})
        if not user: return {}
        return user.get('status', {})

    async def update_plan(self, user_id, data):
        # data: {'expire': datetime, 'premium': True, ...}
        await self.prm.update_one(
            {'id': int(user_id)},
            {'$set': {'id': int(user_id), 'status': data}},
            upsert=True
        )

    async def get_premium_users(self):
        # Returns cursor
        return self.prm.find({'status.premium': True})
    
    async def get_premium_count(self):
        return await self.prm.count_documents({'status.premium': True})

    # ==========================================================================
    # 🔐 VERIFICATION STATUS
    # ==========================================================================
    
    async def get_verify_status(self, user_id):
        status = await self.verify.find_one({'id': int(user_id)})
        if not status:
            return {'is_verified': False, 'verified_time': 0, 'token': None}
        return status

    async def update_verify_status(self, user_id, verify_token="", is_verified=False, verified_time=0):
        await self.verify.update_one(
            {'id': int(user_id)},
            {'$set': {
                'id': int(user_id),
                'token': verify_token,
                'is_verified': is_verified,
                'verified_time': verified_time
            }},
            upsert=True
        )

    # ==========================================================================
    # 📝 SAVED NOTES & FILTERS
    # ==========================================================================

    async def save_note(self, chat_id, name, note_data):
        await self.notes.update_one(
            {'chat_id': chat_id, 'name': name},
            {'$set': {'note': note_data}},
            upsert=True
        )

    async def get_note(self, chat_id, name):
        doc = await self.notes.find_one({'chat_id': chat_id, 'name': name})
        return doc['note'] if doc else None

    async def get_all_notes(self, chat_id):
        return self.notes.find({'chat_id': chat_id})

    async def delete_note(self, chat_id, name):
        res = await self.notes.delete_one({'chat_id': chat_id, 'name': name})
        return res.deleted_count > 0

    async def delete_all_notes(self, chat_id):
        await self.notes.delete_many({'chat_id': chat_id})

    # --- FILTERS ---
    async def add_filter(self, chat_id, name, filter_data):
        await self.filters.update_one(
            {'chat_id': chat_id, 'name': name},
            {'$set': {'filter': filter_data}},
            upsert=True
        )

    async def get_filter(self, chat_id, name):
        doc = await self.filters.find_one({'chat_id': chat_id, 'name': name})
        return doc['filter'] if doc else None

    async def get_filters(self, chat_id):
        return [doc['name'] async for doc in self.filters.find({'chat_id': chat_id})]

    async def delete_filter(self, chat_id, name):
        res = await self.filters.delete_one({'chat_id': chat_id, 'name': name})
        return res.deleted_count > 0

    async def delete_all_filters(self, chat_id):
        await self.filters.delete_many({'chat_id': chat_id})

    # ==========================================================================
    # 💾 DB SIZE UTILS
    # ==========================================================================
    
    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize'], stats['storageSize']
        except:
            return 0, 0

# Initialize Database
db = Database(DATA_DATABASE_URL, DATABASE_NAME)
