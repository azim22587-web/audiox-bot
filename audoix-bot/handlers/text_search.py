import os
import logging
import html
import asyncio
from aiogram import Router, types, F
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from services.music_service import search_tracks, download_track_mp3, download_track_video
from services.downloader_service import is_social_url
from utils.keyboards import get_search_results_keyboard, get_track_format_keyboard, get_media_actions_keyboard
from utils.formatters import format_caption
from database import get_cached_track, cache_track, get_cached_video, cache_video, add_user

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_query(message: types.Message):
    """Handle text search query (song name, artist, lyrics, video title)"""
    query = message.text.strip()
    
    # Ignore if it is a link
    if is_social_url(query):
        return

    user = message.from_user
    if user:
        await add_user(user.id, user.username, user.first_name)

    safe_query = html.escape(query)

    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        status_msg = await message.answer(f"🔍 <i>«{safe_query}» qidirilmoqda...</i>", parse_mode="HTML")
        tracks = await search_tracks(query, limit=5)

        if not tracks:
            await status_msg.edit_text(
                "😔 <b>Afsuski, hech qanday natija topilmadi.</b>\n"
                "Iltimos, so'rovni to'g'riroq yoki aniqroq yozib ko'ring.",
                parse_mode="HTML"
            )
            return

        # Format results text with HTML escaping
        text_lines = [f"🔍 <b>«{safe_query}»</b> bo'yicha topilgan natijalar:\n"]
        for idx, track in enumerate(tracks, 1):
            text_lines.append(f"<b>{idx}.</b> 🎬 <b>{track.safe_title}</b>")
            text_lines.append(f"   👤 <i>{track.safe_artist}</i> | ⏱ <code>{track.duration_str}</code>\n")

        text_lines.append("👇 <b>Kerakli musiqa yoki videoni yuklab olish uchun raqamlardan birini bosing:</b>")
        results_text = "\n".join(text_lines)

        keyboard = get_search_results_keyboard(tracks)
        await status_msg.edit_text(results_text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("select_track:"))
async def handle_select_track_callback(callback: CallbackQuery):
    """Handle selecting track number - show format options (Audio or Video)"""
    track_id = callback.data.split(":", 1)[1]
    await callback.answer()
    
    keyboard = get_track_format_keyboard(track_id)
    await callback.message.reply(
        "👇 <b>Qaysi formatda yuklab olmoqchisiz?</b>\n\n"
        "• 🎵 <b>Audio (MP3)</b> — faqat musiqasi\n"
        "• 🎬 <b>Video (MP4)</b> — to'liq videoroligi",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("dl_song:"))
async def handle_download_song_callback(callback: CallbackQuery):
    """Handle download audio MP3"""
    track_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Musiqa yuklanmoqda...")
    
    # 1. Check database cache for instant sending (0.1s response)
    cached = await get_cached_track(track_id)
    bot_user = await callback.bot.get_me()
    keyboard = get_media_actions_keyboard("audio", track_id)

    if cached:
        file_id, title, artist, duration = cached
        try:
            caption = format_caption(title=title, artist=artist, bot_username=bot_user.username)
            await callback.message.answer_audio(
                audio=file_id,
                title=title,
                performer=artist,
                duration=duration,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.warning(f"Failed to send cached file_id {file_id}: {e}")

    # 2. If not cached, download track
    async with ChatActionSender.upload_voice(bot=callback.bot, chat_id=callback.message.chat.id):
        download_info = await download_track_mp3(track_id)
        if not download_info or not os.path.exists(download_info['file_path']):
            await callback.message.answer("❌ Kechirasiz, musiqani yuklab olishda xatolik yuz berdi. Boshqa musiqani tanlab ko'ring.")
            return

        mp3_file = download_info['file_path']
        title = download_info['title']
        artist = download_info['artist']
        duration = download_info['duration']

        audio_input = FSInputFile(mp3_file)
        caption = format_caption(title=title, artist=artist, bot_username=bot_user.username)

        sent_msg = await callback.message.answer_audio(
            audio=audio_input,
            title=title,
            performer=artist,
            duration=duration,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        if sent_msg.audio:
            await cache_track(
                track_key=track_id,
                file_id=sent_msg.audio.file_id,
                title=title,
                artist=artist,
                duration=duration
            )

        await asyncio.sleep(1)
        try:
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
        except Exception as e:
            logger.warning(f"Could not remove temp file: {e}")

@router.callback_query(F.data.startswith("dl_vid:"))
async def handle_download_video_callback(callback: CallbackQuery):
    """Handle download Video MP4"""
    track_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Video yuklanmoqda...")
    
    # Check video cache
    cached_v = await get_cached_video(f"yt_{track_id}")
    bot_user = await callback.bot.get_me()
    keyboard = get_media_actions_keyboard("video", track_id)

    if cached_v:
        file_id, video_title = cached_v
        try:
            caption = format_caption(title=video_title, bot_username=bot_user.username)
            await callback.message.answer_video(
                video=file_id,
                caption=caption,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.warning(f"Failed to send cached video {file_id}: {e}")

    # Download video
    async with ChatActionSender.upload_video(bot=callback.bot, chat_id=callback.message.chat.id):
        download_info = await download_track_video(track_id)
        if not download_info or not download_info.get('file_path') or not os.path.exists(download_info['file_path']):
            await callback.message.answer("❌ Kechirasiz, videoni yuklab olishda xatolik yuz berdi.")
            return

        vid_file = download_info['file_path']
        title = download_info['title']
        duration = download_info['duration']

        video_input = FSInputFile(vid_file)
        caption = format_caption(title=title, bot_username=bot_user.username)

        sent_msg = await callback.message.answer_video(
            video=video_input,
            caption=caption,
            duration=duration,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        if sent_msg.video:
            await cache_video(
                url_hash=f"yt_{track_id}",
                file_id=sent_msg.video.file_id,
                video_title=title
            )

        await asyncio.sleep(1)
        try:
            if os.path.exists(vid_file):
                os.remove(vid_file)
        except Exception as e:
            logger.warning(f"Could not remove temp file: {e}")

@router.callback_query(F.data == "cancel_search")
async def handle_cancel_search(callback: CallbackQuery):
    """Handle cancel search button"""
    await callback.answer("Qidiruv bekor qilindi")
    try:
        await callback.message.delete()
    except Exception:
        pass
