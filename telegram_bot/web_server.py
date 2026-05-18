"""
Dummy web server to keep Render/Railway health checks happy.
Runs alongside the bot in the same asyncio event loop.
"""

import os
from aiohttp import web

async def health_check(request):
    return web.Response(text="TradingAgents Telegram Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render.com provides PORT environment variable (default 10000)
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Dummy health-check server started on port {port}")
