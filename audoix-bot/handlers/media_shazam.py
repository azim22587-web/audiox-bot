import os
import logging
import uuid
import html
import asyncio
from pathlib import Path
from aiogram import Router, types, F
from aiogram.types import FSInputFile
from aiogram.utils.chat_action import ChatActionSender
from config import TEMP_DIR
from services.ffmpeg_helper import extract_audio_sample, convert_to_wav
from services.recognition_service import recognize_audio
from services.music_service import search_tracks, download_track_mp3
from utils.keyboards import get_media_actions_keyboard
from utils.formatters import format_caption
from database import get_cached_track, cache_track, add_user

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.voice | F.video_note | F.audio | F.video | (F.document & F.document.mime_type.startswith(('audio/', 'video/'))))
async def handle_media_recognition(message: types.Message):
    """
    Handle voice messages, video notes (kruglyash), audios, and videos for music identification.
    """
    user = message.from_user
    if user:
        await add_user(user.id, user.username, user.first_name)

    async with ChatActionSender.record_voice(bot=message.bot, chat_id=message.chat.id):
        status_msg = await message.reply("🎧 <i>Ovoz eshitilmoqda va musiqa/qo'shiq matni aniqlanmoqda...</i>", parse_mode="HTML")
        
        target_file = (
            message.voice
            or message.video_note
            or message.audio
            or message.video
            or message.document
        )
        
        if not target_file:
            await status_msg.edit_text("❌ Faylni yuklab olishda xatolik.")
            return

        unique_id = str(uuid.uuid4())[:8]
        raw_download_path = TEMP_DIR / f"raw_{unique_id}.tmp"
        extracted_mp3_path = TEMP_DIR / f"sample_{unique_id}.mp3"
        extracted_wav_path = TEMP_DIR / f"sample_{unique_id}.wav"

        try:
            # 1. Download file from Telegram
            file_info = await message.bot.get_file(target_file.file_id)
            await message.bot.download_file(file_info.file_path, destination=raw_download_path)

            # 2. Extract clean MP3 & 16kHz WAV samples
            await extract_audio_sample(raw_download_path, extracted_mp3_path, duration=30)
            await convert_to_wav(raw_download_path, extracted_wav_path, duration=30)

            sample_mp3 = extracted_mp3_path if os.path.exists(extracted_mp3_path) else raw_download_path

            # 3. Recognize track
            track = await recognize_audio(sample_mp3, extracted_wav_path)

            if not track or not track.title:
                await status_msg.edit_text(
                    "😔 <b>Afsuski, ushbu ovozdan musiqa topilmadi.</b>\n\n"
                    "💡 <i>Maslahat: Musiqani uzoqroq (10-15 soniya), aniqroq qilib yuboring yoki qo'shiq nomi/matnini yozib yuboring.</i>",
                    parse_mode="HTML"
                )
                return

            search_query = track.query
            safe_query = html.escape(search_query)

            # 4. Success - Inform user
            await status_msg.edit_text(
                f"✅ <b>Topildi:</b> <i>«{safe_query}»</i>\n"
                f"⏳ <i>Musiqa va video tayyorlanmoqda...</i>",
                parse_mode="HTML"
            )

            # 5. Search & Download full track
            search_results = await search_tracks(search_query, limit=1)

            if search_results:
                best_track = search_results[0]
                bot_user = await message.bot.get_me()
                keyboard = get_media_actions_keyboard("audio", best_track.id)

                # Check cache first
                cached = await get_cached_track(best_track.id)
                if cached:
                    file_id, c_title, c_artist, c_duration = cached
                    caption = format_caption(title=c_title, artist=c_artist, bot_username=bot_user.username)
                    await message.answer_audio(
                        audio=file_id,
                        title=c_title,
                        performer=c_artist,
                        duration=c_duration,
                        caption=caption,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    download_info = await download_track_mp3(best_track.id, title=track.title, artist=track.artist)
                    if download_info and os.path.exists(download_info['file_path']):
                        audio_input = FSInputFile(download_info['file_path'])
                        caption = format_caption(title=download_info['title'], artist=download_info['artist'], bot_username=bot_user.username)

                        sent_msg = await message.answer_audio(
                            audio=audio_input,
                            title=download_info['title'],
                            performer=download_info['artist'],
                            duration=download_info['duration'],
                            caption=caption,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )

                        if sent_msg.audio:
                            await cache_track(
                                track_key=best_track.id,
                                file_id=sent_msg.audio.file_id,
                                title=download_info['title'],
                                artist=download_info['artist'],
                                duration=download_info['duration']
                            )

                        await asyncio.sleep(1)
                        if os.path.exists(download_info['file_path']):
                            try:
                                os.remove(download_info['file_path'])
                            except Exception:
                                pass
            else:
                await message.answer(
                    f"🎵 <b>{safe_query}</b>\n"
                    f"Musiqa aniqlandi, lekin uni internetdan yuklab bo'lmadi.",
                    parse_mode="HTML"
                )

        except Exception as e:
            logger.error(f"Error in media recognition: {e}", exc_info=True)
            await status_msg.edit_text("❌ Musiqani aniqlashda xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")
        finally:
            # Clean temporary files
            for p in [raw_download_path, extracted_mp3_path, extracted_wav_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
