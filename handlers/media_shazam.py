import os
import logging
import uuid
import html
import asyncio
from pathlib import Path
from aiogram import Router, types, F
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.utils.chat_action import ChatActionSender
from config import TEMP_DIR
from services.ffmpeg_helper import (
    extract_audio_sample,
    convert_to_wav,
    convert_to_round_video_note,
    convert_to_mp3,
    get_video_duration
)
from services.recognition_service import recognize_audio
from services.music_service import search_tracks, download_track_mp3
from utils.keyboards import (
    get_media_actions_keyboard,
    get_search_results_keyboard,
    get_direct_video_keyboard
)
from utils.formatters import format_caption
from database import get_cached_track, cache_track, add_user

logger = logging.getLogger(__name__)
router = Router()

# In-memory mapping of user video messages for action buttons
USER_VIDEO_STORE = {}

@router.message(F.video | (F.document & F.document.mime_type.func(lambda m: m and m.startswith('video/'))))
async def handle_direct_video(message: types.Message):
    """
    Handle video files sent directly by users.
    Offers instant choices: Round (Kruglyash), MP3 audio extraction, or Shazam music recognition.
    """
    user = message.from_user
    if user:
        await add_user(user.id, user.username, user.first_name)

    vid_target = message.video or message.document
    if not vid_target:
        return

    action_id = uuid.uuid4().hex[:8]
    USER_VIDEO_STORE[action_id] = vid_target.file_id

    caption_text = (
        "🎬 <b>Video qabul qilindi!</b>\n\n"
        "👇 <b>Quyidagi amallardan birini tanlang:</b>\n\n"
        "• 🔄 <b>Yumaloq video (Round)</b> — Telegram kruglyash formatiga aylantirish\n"
        "• 🎵 <b>Musiqasini ajratib olish</b> — MP3 formatda yuklash\n"
        "• 🔍 <b>Shazam</b> — videodagi qo'shiqni aniqlash"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yumaloq video (Round)", callback_data=f"uvid_action:round:{action_id}")],
        [
            InlineKeyboardButton(text="🎵 Musiqasini ajratish (MP3)", callback_data=f"uvid_action:mp3:{action_id}"),
            InlineKeyboardButton(text="🔍 Shazam orqali aniqlash", callback_data=f"uvid_action:shazam:{action_id}")
        ]
    ])

    await message.reply(caption_text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("uvid_action:"))
async def handle_user_video_action(callback: CallbackQuery):
    """Handle actions for directly uploaded video"""
    parts = callback.data.split(":")
    action = parts[1]
    action_id = parts[2]

    file_id = USER_VIDEO_STORE.get(action_id)
    if not file_id:
        # Check if the replied message has video
        if callback.message.reply_to_message and callback.message.reply_to_message.video:
            file_id = callback.message.reply_to_message.video.file_id
        else:
            await callback.answer("❌ Fayl eskirgan. Videoni qaytadan yuboring.")
            return

    unique_id = uuid.uuid4().hex[:6]
    temp_video = str(TEMP_DIR / f"uvid_{unique_id}.mp4")

    if action == "round":
        await callback.answer("⏳ Video yumaloq shaklga (Round) keltirilmoqda...")
        async with ChatActionSender.record_video_note(bot=callback.bot, chat_id=callback.message.chat.id):
            round_output = str(TEMP_DIR / f"round_{unique_id}.mp4")
            try:
                file_info = await callback.bot.get_file(file_id)
                await callback.bot.download_file(file_info.file_path, destination=temp_video)

                success = await convert_to_round_video_note(temp_video, round_output, max_duration=60, size=384)
                if not success or not os.path.exists(round_output):
                    await callback.message.answer("❌ Videoni yumaloq shaklga keltirishda xatolik yuz berdi.")
                    return

                round_dur = min(60, get_video_duration(round_output) or 10)
                await callback.message.answer_video_note(
                    video_note=FSInputFile(round_output),
                    duration=round_dur,
                    length=384
                )
            except Exception as e:
                logger.error(f"Error in round video conversion: {e}")
                await callback.message.answer("❌ Xatolik yuz berdi.")
            finally:
                for p in [temp_video, round_output]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass

    elif action == "mp3":
        await callback.answer("⏳ Musiqa ajratib olinmoqda...")
        async with ChatActionSender.upload_voice(bot=callback.bot, chat_id=callback.message.chat.id):
            mp3_output = str(TEMP_DIR / f"audio_{unique_id}.mp3")
            try:
                file_info = await callback.bot.get_file(file_id)
                await callback.bot.download_file(file_info.file_path, destination=temp_video)

                success = await convert_to_mp3(temp_video, mp3_output)
                if not success or not os.path.exists(mp3_output):
                    await callback.message.answer("❌ Musiqani ajratishda xatolik yuz berdi.")
                    return

                bot_user = await callback.bot.get_me()
                caption = format_caption(title="Ajratib olingan musiqa", bot_username=bot_user.username)
                await callback.message.answer_audio(
                    audio=FSInputFile(mp3_output),
                    title="Audio Trek",
                    performer=bot_user.first_name,
                    caption=caption,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Error extracting mp3: {e}")
                await callback.message.answer("❌ Xatolik yuz berdi.")
            finally:
                for p in [temp_video, mp3_output]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass

    elif action == "shazam":
        await callback.answer("🔍 Shazam orqali aniqlanmoqda...")
        async with ChatActionSender.record_voice(bot=callback.bot, chat_id=callback.message.chat.id):
            sample_mp3 = str(TEMP_DIR / f"shazam_{unique_id}.mp3")
            try:
                file_info = await callback.bot.get_file(file_id)
                await callback.bot.download_file(file_info.file_path, destination=temp_video)
                await extract_audio_sample(temp_video, sample_mp3, duration=25)

                track = await recognize_audio(sample_mp3)
                if not track or not track.title:
                    await callback.message.answer("😔 Afsuski, videodagi musiqa aniqlanmadi.")
                    return

                safe_title = html.escape(track.query)
                await callback.message.answer(
                    f"✅ <b>Topildi:</b> <i>«{safe_title}»</i>\n"
                    f"⏳ <i>Musiqa qidirilmoqda...</i>",
                    parse_mode="HTML"
                )

                search_res = await search_tracks(track.query, limit=1)
                if search_res:
                    best = search_res[0]
                    bot_user = await callback.bot.get_me()
                    dl_info = await download_track_mp3(best.id, title=track.title, artist=track.artist)
                    if dl_info and os.path.exists(dl_info['file_path']):
                        kbrd = get_media_actions_keyboard("audio", best.id)
                        caption = format_caption(title=dl_info['title'], artist=dl_info['artist'], bot_username=bot_user.username)
                        await callback.message.answer_audio(
                            audio=FSInputFile(dl_info['file_path']),
                            title=dl_info['title'],
                            performer=dl_info['artist'],
                            caption=caption,
                            reply_markup=kbrd,
                            parse_mode="HTML"
                        )
                        if os.path.exists(dl_info['file_path']):
                            os.remove(dl_info['file_path'])
            except Exception as e:
                logger.error(f"Error in video shazam: {e}")
                await callback.message.answer("❌ Musiqani aniqlashda xatolik yuz berdi.")
            finally:
                for p in [temp_video, sample_mp3]:
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass

@router.message(F.voice | F.video_note | F.audio | (F.document & F.document.mime_type.func(lambda m: m and m.startswith('audio/'))))
async def handle_media_recognition(message: types.Message):
    """
    Handle voice messages, video notes (kruglyash), and audios for music identification & speech voice search.
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

            # 3. Recognize track (Shazam / Speech recognition)
            track = await recognize_audio(sample_mp3, extracted_wav_path)

            if not track or not track.title:
                await status_msg.edit_text(
                    "😔 <b>Afsuski, ushbu ovozdan musiqa yoki so'rov topilmadi.</b>\n\n"
                    "💡 <i>Maslahat: Musiqani uzoqroq (10-15 soniya), aniqroq qilib yuboring yoki qo'shiq nomi/ijrochini ovoz bilan aytib yuboring.</i>",
                    parse_mode="HTML"
                )
                return

            search_query = track.query
            safe_query = html.escape(search_query)

            # 4. If recognized via speech recognition (e.g. user said "Munisa Rizayeva"):
            # Show search results list with songs, concerts, videos and numbers [ 1 ] [ 2 ] [ 3 ]!
            if getattr(track, 'is_speech', False):
                tracks = await search_tracks(search_query, limit=5)
                if not tracks:
                    await status_msg.edit_text(
                        f"🗣 <b>Ovozli qidiruv:</b> «<i>{safe_query}</i>»\n\n"
                        "😔 <b>Afsuski, ushbu so'rov bo'yicha hech qanday natija topilmadi.</b>\n"
                        "Iltimos, qaytadan aniqroq aytib ko'ring.",
                        parse_mode="HTML"
                    )
                    return

                text_lines = [
                    f"🗣 <b>Ovozli qidiruv:</b> «<i>{safe_query}</i>»\n",
                    "🔍 <b>Topilgan natijalar (qo'shiqlar, konsertlar va videolar):</b>\n"
                ]
                for idx, tr in enumerate(tracks, 1):
                    text_lines.append(f"<b>{idx}.</b> 🎬 <b>{tr.safe_title}</b>")
                    text_lines.append(f"   👤 <i>{tr.safe_artist}</i> | ⏱ <code>{tr.duration_str}</code>\n")

                text_lines.append("👇 <b>Kerakli musiqa yoki videoni yuklab olish uchun raqamlardan birini bosing:</b>")
                results_text = "\n".join(text_lines)

                keyboard = get_search_results_keyboard(tracks)
                await status_msg.edit_text(results_text, reply_markup=keyboard, parse_mode="HTML")
                return

            # 5. If recognized via Shazam fingerprinting (exact studio song):
            await status_msg.edit_text(
                f"✅ <b>Topildi:</b> <i>«{safe_query}»</i>\n"
                f"⏳ <i>Musiqa tayyorlanmoqda...</i>",
                parse_mode="HTML"
            )

            search_results = await search_tracks(search_query, limit=1)
            if not search_results and track.title and track.title != search_query:
                search_results = await search_tracks(track.title, limit=1)

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
            for p in [raw_download_path, extracted_mp3_path, extracted_wav_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
