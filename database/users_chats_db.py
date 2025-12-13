import logging
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_NAME, DATA_DATABASE_URL
from datetime import datetime

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
        
        # 🔥 NEW: Configuration Collection for Admin Panel
        self.conf = self.db.bot_settings

    # =======================
    # ⚙️ ADMIN PANEL / CONFIG
    # =======================
    
    async def get_config(self):
        """
        बॉट की डायनामिक सेटिंग्स लाता है (Search Mode, Auth Channel, etc.)
        अगर सेटिंग्स नहीं हैं, तो Default बना देता है।
        """
        config = await self.conf.find_one({'_id': 'main_config'})
        if not config:
            default_config = {
                '_id': 'main_config',
                'search_mode': 'hybrid',     # primary / backup / hybrid
                'shortlink_enable': False,   # True / False
                'shortlink_api': '',
                'shortlink_site': '',
                'auth_channel': None,        # Channel ID
                'req_channel': None,         # Log Channel for Requests
                'tutorial_link': None,
                'start_pic': None,           # File ID
                'is_maintenance': False      # True = Only Admin can use
            }
            await self.conf.insert_one(default_config)
            return default_config
        return config

    async def update_config(self, key, value):
        """
        एडमिन पैनल से किसी भी सेटिंग को अपडेट करने के लिए।
        Usage: await db.update_config('search_mode', 'backup')
        """
        await self.conf.update_one(
            {'_id': 'main_config'},
            {'$set': {key: value}},
            upsert=True
        )

    # =======================
    # 👤 USER MANAGEMENT
    # =======================

    async def new_user(self, id):
        return dict(
            id=id,
            join_date=datetime.now().date(),
            ban_status=dict(
                is_banned=False,
                ban_duration=0,
                banned_on=datetime.now().date(),
                ban_reason=''
            )
        )

    async def add_user(self, id):
        user = await self.new_user(id)
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

    # =======================
    # 🏘️ GROUP MANAGEMENT
    # =======================

    async def add_chat(self, chat, title):
        chat_id = chat
        chat_name = title
        if not await self.grp.find_one({'id': chat_id}):
            chat_data = {
                'id': chat_id,
                'name': chat_name,
                'settings': {'AUTO_FILTER': True} # Default Settings
            }
            await self.grp.insert_one(chat_data)

    async def get_chat(self, chat):
        return await self.grp.find_one({'id': int(chat)})

    async def get_bot_sttgs(self):
        # Global Settings (From Config) can override group settings later
        # अभी के लिए यह पुराना लॉजिक सपोर्ट कर रहा है
        return {'AUTO_FILTER': True}

    async def total_chat_count(self):
        return await self.grp.count_documents({})

    async def get_all_chats(self):
        return self.grp.find({})

    # =======================
    # 🚫 BAN MANAGEMENT
    # =======================

    async def add_banned(self, id):
        await self.ban.insert_one({'id': int(id)})

    async def remove_banned(self, id):
        await self.ban.delete_one({'id': int(id)})

    async def get_banned(self):
        users = [b['id'] async for b in self.ban.find({})]
        # Chats banned logic can be added here if needed
        return users, []

    # =======================
    # 💎 PREMIUM MANAGEMENT
    # =======================

    async def add_premium(self, user_id, plan_data):
        # plan_data example: {'expire': datetime_obj, 'premium': True, ...}
        await self.prm.update_one(
            {'id': int(user_id)},
            {'$set': {'status': plan_data}},
            upsert=True
        )

    async def remove_premium(self, user_id):
        await self.prm.delete_one({'id': int(user_id)})

    async def get_premium_users(self):
        return self.prm.find({'status.premium': True})
    
    async def is_premium(self, user_id):
        user = await self.prm.find_one({'id': int(user_id)})
        if user and user.get('status', {}).get('premium'):
            # Check expiry logic should be handled in utils or bot loop
            return True
        return False
    
    async def get_premium_count(self):
        return await self.prm.count_documents({'status.premium': True})

    async def update_plan(self, user_id, data):
        await self.prm.update_one({'id': int(user_id)}, {'$set': {'status': data}})

    # =======================
    # 💾 DB SIZE UTILS
    # =======================
    
    async def get_db_size(self):
        return (await self.db.command("dbstats"))['dataSize'], (await self.db.command("dbstats"))['storageSize']

# Initialize Database
db = Database(DATA_DATABASE_URL, DATABASE_NAME)
