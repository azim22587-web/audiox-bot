import asyncio
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from config import ADMIN_IDS
from database import get_users_count, get_cached_tracks_count, get_all_user_ids

logger = logging.getLogger(__name__)
router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show bot statistics to admin"""
    if not is_admin(message.from_user.id):
        return

    users_count = await get_users_count()
    tracks_count = await get_cached_tracks_count()

    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 <b>Foydalanuvchilar soni:</b> {users_count} ta\n"
        f"⚡️ <b>Keshdagi musiqalar soni:</b> {tracks_count} ta\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    """Broadcast message to all users: /broadcast <matn> or reply to a message with /broadcast"""
    if not is_admin(message.from_user.id):
        return

    user_ids = await get_all_user_ids()
    if not user_ids:
        await message.answer("Bazada foydalanuvchilar mavjud emas.")
        return

    reply = message.reply_to_message
    broadcast_text = message.text.replace("/broadcast", "").strip()

    if not reply and not broadcast_text:
        await message.answer("Xabar yuborish uchun: <code>/broadcast Xabar matni</code> yoki biror xabarga reply qilib <code>/broadcast</code> yozing.", parse_mode="HTML")
        return

    status_msg = await message.answer(f"📢 Xabar {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")
    sent = 0
    blocked = 0

    for uid in user_ids:
        try:
            if reply:
                await reply.copy_to(chat_id=uid)
            else:
                await message.bot.send_message(chat_id=uid, text=broadcast_text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # Avoid Telegram flood limits
        except Exception:
            blocked += 1

    await status_msg.edit_text(
        f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"📨 Yuborildi: {sent} ta\n"
        f"🚫 Bloklagan/Xato: {blocked} ta",
        parse_mode="HTML"
    )
