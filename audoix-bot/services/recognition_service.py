import aiohttp
import asyncio
import logging
import os
from pathlib import Path
import speech_recognition as sr
from config import AUDD_API_KEY, ACRCLOUD_HOST, ACRCLOUD_KEY, ACRCLOUD_SECRET

logger = logging.getLogger(__name__)

class RecognizedTrack:
    def __init__(self, title: str, artist: str = "", album: str = "", release_date: str = "", cover_art: str = "", lyrics: str = ""):
        self.title = title.strip()
        self.artist = artist.strip()
        self.album = album.strip()
        self.release_date = release_date
        self.cover_art = cover_art
        self.lyrics = lyrics

    @property
    def query(self) -> str:
        if self.artist and self.title:
            return f"{self.artist} - {self.title}"
        return self.title

async def recognize_with_audd(audio_path: str | Path) -> RecognizedTrack | None:
    """Recognize music using AudD API (if key is configured)"""
    if not AUDD_API_KEY:
        return None
        
    url = "https://api.audd.io/"
    data = aiohttp.FormData()
    data.add_field("api_token", AUDD_API_KEY)
    data.add_field("return", "lyrics,apple_music,spotify")
    
    try:
        with open(audio_path, "rb") as f:
            data.add_field("file", f, filename="audio.mp3", content_type="audio/mpeg")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status == 200:
                        res_json = await resp.json()
                        if res_json.get("status") == "success" and res_json.get("result"):
                            result = res_json["result"]
                            title = result.get("title", "")
                            artist = result.get("artist", "")
                            album = result.get("album", "")
                            release_date = result.get("release_date", "")
                            
                            cover_art = ""
                            if result.get("spotify") and result["spotify"].get("album", {}).get("images"):
                                cover_art = result["spotify"]["album"]["images"][0].get("url", "")
                            elif result.get("apple_music") and result["apple_music"].get("artwork"):
                                cover_art = result["apple_music"]["artwork"].get("url", "").replace("{w}x{h}", "600x600")

                            lyrics = ""
                            if result.get("lyrics") and result["lyrics"].get("lyrics"):
                                lyrics = result["lyrics"]["lyrics"]

                            if title:
                                return RecognizedTrack(
                                    title=title,
                                    artist=artist,
                                    album=album,
                                    release_date=release_date,
                                    cover_art=cover_art,
                                    lyrics=lyrics
                                )
    except Exception as e:
        logger.error(f"AudD recognition error: {e}")
    return None

async def recognize_speech_lyrics(wav_path: str | Path) -> RecognizedTrack | None:
    """
    Recognize spoken or sung song lyrics/title from voice message using Google Speech API (free)
    """
    def _recognize():
        r = sr.Recognizer()
        r.energy_threshold = 300
        with sr.AudioFile(str(wav_path)) as source:
            audio_data = r.record(source)
            
            # Try Uzbek first, then Russian, then English
            for lang in ['uz-UZ', 'ru-RU', 'en-US']:
                try:
                    text = r.recognize_google(audio_data, language=lang)
                    if text and len(text.strip()) > 2:
                        return text.strip()
                except Exception:
                    continue
        return None

    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(None, _recognize)
        if text:
            return RecognizedTrack(title=text)
    except Exception as e:
        logger.error(f"Speech recognition error: {e}")
    return None

async def recognize_audio(mp3_path: str | Path, wav_path: str | Path = None) -> RecognizedTrack | None:
    """
    Main recognition entrypoint:
    1. Try AudD API (if key available)
    2. Try Speech/Lyrics Recognition (free, recognizes singing & words in Uzbek/Russian)
    """
    # 1. AudD
    if AUDD_API_KEY:
        track = await recognize_with_audd(mp3_path)
        if track:
            return track

    # 2. Speech / Lyrics recognition from WAV
    if wav_path and os.path.exists(wav_path):
        track = await recognize_speech_lyrics(wav_path)
        if track:
            return track

    return None
