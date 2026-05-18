import asyncio
from telegram_bot.bot import main as bot_main
from telegram_bot.web_server import start_web_server

async def main():
    await start_web_server()
    await bot_main()

if __name__ == "__main__":
    asyncio.run(main())

