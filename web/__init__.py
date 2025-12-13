import logging
from aiohttp import web
from web.route import routes

# ==============================================================================
# 🚀 WEB SERVER FACTORY
# ==============================================================================
def create_app():
    """
    Creates the Aiohttp Web Application with High Capacity.
    """
    # 1. High Traffic Capacity (100 MB Limit)
    # साधारण बोट्स 10MB पर क्रैश हो जाते हैं, हमने इसे 100MB कर दिया है।
    app = web.Application(client_max_size=100 * 1024 * 1024)
    
    # 2. Register All Routes
    app.add_routes(routes)
    
    return app

# 3. Export App Instance (Used in bot.py)
web_app = create_app()
