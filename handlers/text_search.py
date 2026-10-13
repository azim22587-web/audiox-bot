import os
import logging
import html
import asyncio
import uuid
from aiogram import Router, types, F
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from services.music_service import search_tracks, download_track_mp3, download_track_video
from services.downloader_service import is_social_url
from services.ffmpeg_helper import convert_to_round_video_note, get_video_duration
from utils.keyboards import get_search_results_keyboard, get_track_format_keyboard, get_media_actions_keyboard
from utils.formatters import format_caption
from database import get_cached_track, cache_track, get_cached_video, cache_video, add_user
from config import TEMP_DIR

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
    """Handle selecting track number - show format options (Audio, Video, Round)"""
    track_id = callback.data.split(":", 1)[1]
    await callback.answer()
    
    keyboard = get_track_format_keyboard(track_id)
    await callback.message.reply(
        "👇 <b>Qaysi formatda yuklab olmoqchisiz?</b>\n\n"
        "• 🎵 <b>Audio (MP3)</b> — to'liq musiqa/audio formati\n"
        "• 🎬 <b>Video (MP4)</b> — to'liq video formati\n"
        "• 🔄 <b>Round Video</b> — yumaloq video (kruglyash)",
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

@router.callback_query(F.data.startswith("dl_round:"))
async def handle_download_round_video_callback(callback: CallbackQuery):
    """Handle download Round Video Note (Kruglyash)"""
    track_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Yumaloq video (Round) tayyorlanmoqda...")

    # 1. Check cache for instant 0.1s sending
    cached_v = await get_cached_video(f"round_{track_id}")
    if cached_v:
        file_id, video_title = cached_v
        try:
            await callback.message.answer_video_note(
                video_note=file_id,
                length=384
            )
            return
        except Exception as e:
            logger.warning(f"Failed to send cached round video {file_id}: {e}")

    # 2. Download and convert to round video note
    async with ChatActionSender.record_video_note(bot=callback.bot, chat_id=callback.message.chat.id):
        download_info = await download_track_video(track_id)
        if not download_info or not download_info.get('file_path') or not os.path.exists(download_info['file_path']):
            await callback.message.answer("❌ Kechirasiz, videoni yuklab olishda xatolik yuz berdi.")
            return

        vid_file = download_info['file_path']
        title = download_info.get('title', 'Video')
        round_output = str(TEMP_DIR / f"round_{track_id}_{uuid.uuid4().hex[:6]}.mp4")

        success = await convert_to_round_video_note(vid_file, round_output, max_duration=60, size=384)
        if not success or not os.path.exists(round_output):
            await callback.message.answer("❌ Kechirasiz, videoni yumaloq shaklga keltirishda xatolik yuz berdi.")
            return

        round_dur = min(60, get_video_duration(round_output) or 10)
        round_input = FSInputFile(round_output)

        sent_msg = await callback.message.answer_video_note(
            video_note=round_input,
            duration=round_dur,
            length=384
        )

        if sent_msg.video_note:
            await cache_video(
                url_hash=f"round_{track_id}",
                file_id=sent_msg.video_note.file_id,
                video_title=title
            )

        for f in [round_output, vid_file]:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

@router.callback_query(F.data.startswith("make_round_vid:"))
async def handle_make_round_vid_callback(callback: CallbackQuery):
    """Convert an already sent video into a Telegram Round Video Note (Kruglyash)"""
    item_id = callback.data.split(":", 1)[1]
    await callback.answer("⏳ Video yumaloq shaklga (Round) keltirilmoqda...")

    # Check cache first
    cached_v = await get_cached_video(f"round_{item_id}")
    if cached_v:
        file_id, video_title = cached_v
        try:
            await callback.message.answer_video_note(
                video_note=file_id,
                length=384
            )
            return
        except Exception as e:
            logger.warning(f"Failed to send cached round video: {e}")

    async with ChatActionSender.record_video_note(bot=callback.bot, chat_id=callback.message.chat.id):
        round_output = str(TEMP_DIR / f"round_{item_id}_{uuid.uuid4().hex[:6]}.mp4")
        temp_input_vid = None

        # Priority 1: If message has video attached, download directly from Telegram
        if callback.message.video:
            try:
                file_info = await callback.bot.get_file(callback.message.video.file_id)
                temp_input_vid = str(TEMP_DIR / f"input_{uuid.uuid4().hex[:6]}.mp4")
                await callback.bot.download_file(file_info.file_path, destination=temp_input_vid)
            except Exception as e:
                logger.warning(f"Could not download video directly from Telegram: {e}")
                temp_input_vid = None

        # Priority 2: Download by item_id (YouTube or social media)
        if not temp_input_vid or not os.path.exists(temp_input_vid):
            from services.downloader_service import download_media_video
            from handlers.downloader import URL_CACHE
            social_url = URL_CACHE.get(item_id)
            if social_url:
                dl = await download_media_video(social_url)
                if dl and dl.get('file_path'):
                    temp_input_vid = dl['file_path']
            else:
                dl = await download_track_video(item_id)
                if dl and dl.get('file_path'):
                    temp_input_vid = dl['file_path']

        if not temp_input_vid or not os.path.exists(temp_input_vid):
            await callback.message.answer("❌ Videoni yuklab bo'lmadi.")
            return

        success = await convert_to_round_video_note(temp_input_vid, round_output, max_duration=60, size=384)
        if not success or not os.path.exists(round_output):
            await callback.message.answer("❌ Videoni yumaloq shaklga keltirishda xatolik yuz berdi.")
            return

        round_dur = min(60, get_video_duration(round_output) or 10)
        round_input = FSInputFile(round_output)

        sent_msg = await callback.message.answer_video_note(
            video_note=round_input,
            duration=round_dur,
            length=384
        )

        if sent_msg.video_note:
            await cache_video(
                url_hash=f"round_{item_id}",
                file_id=sent_msg.video_note.file_id,
                video_title="Round Video"
            )

        for f in [round_output, temp_input_vid]:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass

@router.message(F.reply_to_message & F.reply_to_message.video & F.text.lower().in_(["/round", "round", "yumaloq", "kruglyash", "dumaloq"]))
async def handle_reply_make_round(message: types.Message):
    """Handle user replying to a video message with 'round' / 'yumaloq'"""
    async with ChatActionSender.record_video_note(bot=message.bot, chat_id=message.chat.id):
        status_msg = await message.reply("⏳ <i>Video yumaloq shaklga (Round) aylantirilmoqda...</i>", parse_mode="HTML")
        temp_input = str(TEMP_DIR / f"reply_in_{uuid.uuid4().hex[:6]}.mp4")
        round_out = str(TEMP_DIR / f"reply_round_{uuid.uuid4().hex[:6]}.mp4")
        try:
            file_info = await message.bot.get_file(message.reply_to_message.video.file_id)
            await message.bot.download_file(file_info.file_path, destination=temp_input)
            
            success = await convert_to_round_video_note(temp_input, round_out, max_duration=60, size=384)
            if not success or not os.path.exists(round_out):
                await status_msg.edit_text("❌ Videoni yumaloq shaklga aylantirishda xatolik yuz berdi.")
                return

            round_dur = min(60, get_video_duration(round_out) or 10)
            await message.answer_video_note(
                video_note=FSInputFile(round_out),
                duration=round_dur,
                length=384
            )
            await status_msg.delete()
        except Exception as e:
            logger.error(f"Error in reply make round: {e}")
            await status_msg.edit_text("❌ Xatolik yuz berdi.")
        finally:
            for p in [temp_input, round_out]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

