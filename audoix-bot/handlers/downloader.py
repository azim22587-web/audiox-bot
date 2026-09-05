import os
import logging
from aiogram import Router, types, F
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from services.downloader_service import is_social_url, extract_urls, download_media_video, get_url_hash
from services.ffmpeg_helper import convert_to_mp3
from utils.keyboards import get_media_actions_keyboard
from utils.formatters import format_caption
from database import get_cached_video, cache_video, add_user, cache_track, get_cached_track
from config import TEMP_DIR

logger = logging.getLogger(__name__)
router = Router()

URL_CACHE = {}

@router.message(F.text.func(lambda text: is_social_url(text)))
async def handle_social_media_link(message: types.Message):
    """Handle links from Instagram, TikTok, YouTube, Pinterest, etc."""
    urls = extract_urls(message.text)
    if not urls:
        return

    target_url = urls[0]
    user = message.from_user
    if user:
        await add_user(user.id, user.username, user.first_name)

    url_hash = get_url_hash(target_url)
    URL_CACHE[url_hash] = target_url

    async with ChatActionSender.upload_video(bot=message.bot, chat_id=message.chat.id):
        status_msg = await message.reply("⏳ <i>Video yuklanmoqda, iltimos kuting...</i>", parse_mode="HTML")
        
        # 1. Check cache
        cached = await get_cached_video(url_hash)
        bot_user = await message.bot.get_me()
        keyboard = get_media_actions_keyboard("video", url_hash)

        if cached:
            file_id, video_title = cached
            try:
                caption = format_caption(title=video_title or 'Video', bot_username=bot_user.username)
                await message.answer_video(
                    video=file_id,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                await status_msg.delete()
                return
            except Exception as e:
                logger.warning(f"Error sending cached video: {e}")

        # 2. Download video
        download_info = await download_media_video(target_url)
        if not download_info or not download_info.get('file_path') or not os.path.exists(download_info['file_path']):
            await status_msg.edit_text(
                "❌ <b>Videoni yuklab bo'lmadi.</b>\n"
                "Profil yopiq (private) bo'lishi yoki havola noto'g'ri bo'lishi mumkin.",
                parse_mode="HTML"
            )
            return

        video_file_path = download_info['file_path']
        video_title = download_info.get('title', 'Video')
        duration = download_info.get('duration', 0)

        video_input = FSInputFile(video_file_path)
        caption = format_caption(title=video_title, bot_username=bot_user.username)

        try:
            sent_msg = await message.answer_video(
                video=video_input,
                caption=caption,
                duration=duration,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            if sent_msg.video:
                await cache_video(url_hash, sent_msg.video.file_id, video_title)

            await status_msg.delete()

        except Exception as e:
            logger.error(f"Error uploading video: {e}")
            await status_msg.edit_text("❌ Videoni Telegramga yuborishda xatolik yuz berdi.")
        finally:
            if os.path.exists(video_file_path):
                try:
                    os.remove(video_file_path)
                except Exception:
                    pass

@router.callback_query(F.data.startswith("dl_audio_from_vid:"))
async def handle_extract_audio_callback(callback: CallbackQuery):
    """Extract audio MP3 from previously downloaded link/video"""
    url_hash = callback.data.split(":", 1)[1]
    target_url = URL_CACHE.get(url_hash)

    await callback.answer("⏳ Audio ajratib olinmoqda...")
    
    if not target_url:
        await callback.message.answer("❌ Havola eskirgan. Iltimos havolani qaytadan yuboring.")
        return

    audio_cached = await get_cached_track(f"aud_{url_hash}")
    bot_user = await callback.bot.get_me()

    if audio_cached:
        file_id, title, artist, duration = audio_cached
        caption = format_caption(title=title, artist=artist, bot_username=bot_user.username)
        await callback.message.answer_audio(
            audio=file_id,
            title=title,
            performer=artist,
            duration=duration,
            caption=caption,
            parse_mode="HTML"
        )
        return

    # Download and extract MP3
    async with ChatActionSender.upload_voice(bot=callback.bot, chat_id=callback.message.chat.id):
        from services.music_service import download_track_mp3
        download_info = await download_track_mp3(target_url)

        if not download_info or not os.path.exists(download_info['file_path']):
            await callback.message.answer("❌ Musiqani ajratib olishda xatolik yuz berdi.")
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
            parse_mode="HTML"
        )

        if sent_msg.audio:
            await cache_track(
                track_key=f"aud_{url_hash}",
                file_id=sent_msg.audio.file_id,
                title=title,
                artist=artist,
                duration=duration
            )

        if os.path.exists(mp3_file):
            try:
                os.remove(mp3_file)
            except Exception:
                pass
