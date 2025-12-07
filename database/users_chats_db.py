import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from info import (
    DATABASE_NAME, DATA_DATABASE_URL, FILES_DATABASE_URL, 
    SECOND_FILES_DATABASE_URL, PROTECT_CONTENT, IMDB, SPELL_CHECK, 
    AUTO_DELETE, WELCOME, WELCOME_TEXT, IMDB_TEMPLATE, FILE_CAPTION, 
    SHORTLINK_URL, SHORTLINK_API, SHORTLINK, TUTORIAL, LINK_MODE, 
    VERIFY_EXPIRE, BOT_ID
)

# --- MongoDB Clients Setup ---
# Motor Client का उपयोग (Async)
data_db_client = AsyncIOMotorClient(DATA_DATABASE_URL)
data_db = data_db_client[DATABASE_NAME]

files_db_client = AsyncIOMotorClient(FILES_DATABASE_URL)
files_db = files_db_client[DATABASE_NAME]

if SECOND_FILES_DATABASE_URL:
    second_files_db_client = AsyncIOMotorClient(SECOND_FILES_DATABASE_URL)
    second_files_db = second_files_db_client[DATABASE_NAME]

class Database:
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
        self.col = data_db.Users
        self.grp = data_db.Groups
        self.prm = data_db.Premiums
        self.req = data_db.Requests
        self.con = data_db.Connections
        self.stg = data_db.Settings

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
    
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
    
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count
    
    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})
    
    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = await self.col.find_one({'id':int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return self.col.find({})
    
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def delete_chat(self, grp_id):
        await self.grp.delete_many({'id': int(grp_id)})

    async def find_join_req(self, id):
        return bool(await self.req.find_one({'id': id}))

    async def add_join_req(self, id):
        await self.req.insert_one({'id': id})

    async def del_join_req(self):
        await self.req.drop()

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        chats = self.grp.find({'chat_status.is_disabled': True})
        b_chats = [chat['id'] async for chat in chats]
        b_users = [user['id'] async for user in users]
        return b_users, b_chats
    
    async def add_chat(self, chat, title):
        chat = self.new_group(chat, title)
        await self.grp.insert_one(chat)

    async def get_chat(self, chat):
        chat = await self.grp.find_one({'id':int(chat)})
        return False if not chat else chat.get('chat_status')
    
    async def re_enable_chat(self, id):
        chat_status=dict(
            is_disabled=False,
            reason="",
            )
        await self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})
        
    async def update_settings(self, id, settings):
        await self.grp.update_one({'id': int(id)}, {'$set': {'settings': settings}})      
    
    async def get_settings(self, id):
        chat = await self.grp.find_one({'id':int(id)})
        if chat:
            return chat.get('settings', self.default_setgs)
        return self.default_setgs
    
    async def disable_chat(self, chat, reason="No Reason"):
        chat_status=dict(
            is_disabled=True,
            reason=reason,
            )
        await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})
    
    async def get_verify_status(self, user_id):
        user = await self.col.find_one({'id':int(user_id)})
        if user:
            info = user.get('verify_status', self.default_verify)
            # Check expiration
            if info.get('expire_time') == 0:
                 # If explicit 0, probably not verified or reset
                 pass
            return info
        return self.default_verify
        
    async def update_verify_status(self, user_id, verify_token="", is_verified=False, link="", expire_time=0):
        # Helper to update specific fields or replace the object
        # Since the argument structure in utils might pass separate args, we handle it here:
        
        # First get current verify status
        current = await self.get_verify_status(user_id)
        
        # Update fields
        if verify_token: current['verify_token'] = verify_token
        if link: current['link'] = link
        if expire_time: current['expire_time'] = expire_time
        # Boolean check is tricky if False is passed, so we assume keyword arguments
        current['is_verified'] = is_verified
        
        # If verify dict is passed directly (from some old logic), handle it
        if isinstance(verify_token, dict):
             current = verify_token

        await self.col.update_one({'id': int(user_id)}, {'$set': {'verify_status': current}})
    
    async def total_chat_count(self):
        count = await self.grp.count_documents({})
        return count
    
    async def get_all_chats(self):
        return self.grp.find({})
    
    async def get_files_db_size(self):
        return (await files_db.command("dbstats"))['dataSize']
   
    async def get_second_files_db_size(self):
        return (await second_files_db.command("dbstats"))['dataSize']
    
    async def get_data_db_size(self):
        return (await data_db.command("dbstats"))['dataSize']
    
    async def get_all_chats_count(self):
        grp = await self.grp.count_documents({})
        return grp
    
    async def get_plan(self, id):
        st = await self.prm.find_one({'id': id})
        if st:
            return st['status']
        return self.default_prm
    
    async def update_plan(self, id, data):
        if not await self.prm.find_one({'id': id}):
            await self.prm.insert_one({'id': id, 'status': data})
        await self.prm.update_one({'id': id}, {'$set': {'status': data}})

    async def get_premium_count(self):
        return await self.prm.count_documents({'status.premium': True})
    
    async def get_premium_users(self):
        return self.prm.find({})
    
    async def add_connect(self, group_id, user_id):
        user = await self.con.find_one({'_id': user_id})
        if user:
            if group_id not in user["group_ids"]:
                await self.con.update_one({'_id': user_id}, {"$push": {"group_ids": group_id}})
        else:
            await self.con.insert_one({'_id': user_id, 'group_ids': [group_id]})

    async def get_connections(self, user_id):
        user = await self.con.find_one({'_id': user_id})
        if user:
            return user["group_ids"]
        else:
            return []
        
    async def update_bot_sttgs(self, var, val):
        if not await self.stg.find_one({'id': BOT_ID}):
            await self.stg.insert_one({'id': BOT_ID, var: val})
        await self.stg.update_one({'id': BOT_ID}, {'$set': {var: val}})

    async def get_bot_sttgs(self):
        return await self.stg.find_one({'id': BOT_ID})

# ---------------------------------------------------------
# यह लाइन सबसे महत्वपूर्ण है, इसके बिना एरर आता रहेगा
# ---------------------------------------------------------
db = Database()
