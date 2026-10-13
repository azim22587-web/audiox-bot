import asyncio
import logging
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from aiohttp import web
from config import BOT_TOKEN
from database import init_db
from handlers import all_routers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AudoixBot")

async def start_web_health_server():
    """Start lightweight HTTP health server if running on Render / Cloud Web Service"""
    port_str = os.environ.get("PORT")
    if not port_str:
        return None
    try:
        port = int(port_str)
        app = web.Application()
        
        async def handle_ping(request):
            return web.json_response({
                "status": "online",
                "service": "audoix_bot",
                "message": "Bot is running 24/7"
            })

        app.router.add_get("/", handle_ping)
        app.router.add_get("/health", handle_ping)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"🌐 Render Cloud HTTP Health Server ishga tushdi (Port: {port})")
        return runner
    except Exception as e:
        logger.warning(f"Could not start cloud health server on port {port_str}: {e}")
        return None

async def set_bot_commands(bot: Bot):
    """Set standard Telegram menu commands"""
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam va qo'llanma"),
    ]
    try:
        await bot.set_my_commands(commands)
    except Exception as e:
        logger.warning(f"Note: Could not set bot commands: {e}")

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error(
            "\n" + "="*60 + "\n"
            "❌ XATOLIK: BOT_TOKEN ko'rsatilmagan!\n"
            "Iltimos, '.env' faylini oching va Telegram @BotFather'dan olgan tokeningizni yozing:\n"
            "BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ\n"
            + "="*60
        )
        return

    logger.info("🚀 Audoix Bot ishga tushirilmoqda...")
    
    # 1. Initialize SQLite Database
    await init_db()

    # 2. Start Web Health Server for Render (if PORT is set)
    await start_web_health_server()

    dp = Dispatcher()

    # 3. Include all routers
    for router in all_routers:
        dp.include_router(router)

    # 4. Continuous auto-reconnect loop (24/7 reliability)
    while True:
        bot = None
        try:
            session = AiohttpSession(timeout=300)
            bot = Bot(
                token=BOT_TOKEN,
                session=session,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            bot_info = await bot.get_me()
            logger.info(f"✅ Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
            await set_bot_commands(bot)
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("📡 Xabarlar qabul qilish (polling) boshlandi...")
            await dp.start_polling(bot)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot to'xtatildi.")
            break
        except Exception as e:
            logger.warning(f"⚠️ Tarmoq uzilishi kuzatildi ({e}). 5 soniyadan so'ng avtomatik qayta ulanadi...")
            await asyncio.sleep(5)
        finally:
            if bot and bot.session:
                try:
                    await bot.session.close()
                except Exception:
                    pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot yakunlandi.")
