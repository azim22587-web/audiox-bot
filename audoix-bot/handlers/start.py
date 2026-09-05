from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from database import add_user
from config import ADMIN_USERNAME

router = Router()

def get_start_text() -> str:
    lines = [
        "Salom men <b>audoix</b> botman!\n",
        "✅ <b>Mening xususiyatlarim bilan tanishing:</b>\n",
        "• Qo'shiq matni, nomi yoki ijrochi ismi orqali musiqa topaman\n",
        "• Instagram, Youtube va Tik-Tokdan video va undagi musiqani yuklab beraman\n",
        "• Bundan tashqari men ovozli xabar, video va audiodagi musiqani to'liq shaklda topib beraman"
    ]
    if ADMIN_USERNAME:
        lines.append(f"\n👨‍💻 <b>Bot yaratuvchisi:</b> @{ADMIN_USERNAME}")
        lines.append(f"📢 <b>Reklama va murojaat:</b> @{ADMIN_USERNAME}")
    return "\n".join(lines)

def get_help_text() -> str:
    lines = [
        "👋 <b>Salom!</b>\n"
        "Men sizga musiqa va video topishga yordam beraman 🎶 menga quyidagilardan birini yuboring:\n",
        "🎵 Qo'shiq yoki ijrochi nomi",
        "🔤 Qo'shiq matni",
        "🎙 Musiqa bilan ovozli xabar",
        "📽 Musiqa bilan video",
        "🔊 Audioyozuv",
        "🎥 Musiqa bilan videoxabar",
        "🔗 Instagram, Tik-Tok, YouTube va boshqa saytlarga video havola\n",
        "💃 <b>Rohatlaning!</b>"
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
