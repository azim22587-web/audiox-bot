from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from database import add_user
from config import ADMIN_USERNAME

router = Router()

def get_start_text() -> str:
    lines = [
        "🎧 <b>AudioX</b> botiga xush kelibsiz!\n",
        "⚡️ <b>Men nimalar qila olaman?</b>\n",
        "• 🎙 <b>Ovozli qidiruv:</b> Ovozli xabar yuboring (masalan, <i>«Munisa Rizayeva»</i>) va uning qo'shiq hamda konsertlarini topib beraman",
        "• 💬 <b>Matnli qidiruv:</b> Qo'shiq, ijrochi yoki klip nomini yozing, to'liq formatdagi musiqa (MP3) va videolarni (MP4) yuklab bering",
        "• 🔄 <b>Round Video (Yumaloq video):</b> Istalgan videoni bitta tugma orqali dumaloq Telegram video-xabar (kruglyash) holatiga keltirib beraman",
        "• 🔗 <b>Ijtimoiy tarmoqlar:</b> Instagram, TikTok, YouTube havolalaridagi videolarni to'liq yuklab beraman",
        "• 🎧 <b>Shazam:</b> Ovoz yoki videodagi musiqani bir zumda aniqlayman"
    ]
    if ADMIN_USERNAME:
        lines.append(f"\n👨‍💻 <b>Bot yaratuvchisi:</b> @{ADMIN_USERNAME}")
        lines.append(f"📢 <b>Reklama va murojaat:</b> @{ADMIN_USERNAME}")
    return "\n".join(lines)

def get_help_text() -> str:
    lines = [
        "👋 <b>AudioX botidan foydalanish bo'yicha qo'llanma:</b>\n",
        "1️⃣ <b>Ovozli xabar orqali qidiruv:</b>",
        "   Menga shunchaki qo'shiqchi yoki qo'shiq nomini ovoz qilib yuboring (masalan: <i>«Munisa Rizayeva»</i>), bot uning qo'shiqlari va konsertlarini topib beradi.\n",
        "2️⃣ <b>Matn orqali qidiruv:</b>",
        "   Qo'shiq nomi yoki matnini SMS tarzida yozing, so'ngra 🎵 Audio (MP3) yoki 🎬 Video (MP4) formatida yuklab oling.\n",
        "3️⃣ <b>Round Video (Dumaloq video):</b>",
        "   Video chiqqandan so'ng <b>🔄 Yumaloq video (Round)</b> tugmasini bosing yoki botga video yuborib <b>Round</b> ni tanlang!\n",
        "4️⃣ <b>Havola orqali yuklash:</b>",
        "   Instagram, TikTok yoki YouTube havolasini yuboring.",
    ]
    if ADMIN_USERNAME:
        lines.append(f"\n📢 <b>Reklama va hamkorlik uchun:</b> @{ADMIN_USERNAME}")
    return "\n".join(lines)

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Handle /start command"""
    user = message.from_user
    if user:
        await add_user(user.id, user.username, user.first_name)
    await message.answer(get_start_text(), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Handle /help command"""
    await message.answer(get_help_text(), parse_mode="HTML")
