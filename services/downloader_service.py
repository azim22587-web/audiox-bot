import asyncio
import hashlib
import logging
import os
import re
from pathlib import Path
import yt_dlp
from config import FFMPEG_PATH, TEMP_DIR
from services.ffmpeg_helper import ensure_video_under_50mb

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/[a-zA-Z0-9]+\.[^\s]{2,})',
    re.IGNORECASE
)

SUPPORTED_DOMAINS = [
    'instagram.com', 'instagr.am',
    'tiktok.com', 'vt.tiktok.com', 'vm.tiktok.com',
    'youtube.com', 'youtu.be',
    'pinterest.com', 'pin.it',
    'twitter.com', 'x.com',
    'facebook.com', 'fb.watch',
    'likee.video', 'likee.com',
    'threads.net'
]

def extract_urls(text: str) -> list[str]:
    """Find all URLs in message text"""
    return URL_REGEX.findall(text)

def is_social_url(text: str) -> bool:
    """Check if message contains a supported social media link"""
    urls = extract_urls(text)
    if not urls:
        return False
    url = urls[0].lower()
    return any(domain in url for domain in SUPPORTED_DOMAINS)

def get_url_hash(url: str) -> str:
    """Create a unique hash for a URL"""
    return hashlib.md5(url.strip().encode('utf-8')).hexdigest()

async def download_media_video(url: str) -> dict | None:
    """
    Download video from Instagram, TikTok, YouTube, Pinterest, etc.
    Automatically ensures video is under Telegram's 50MB limit with automatic retry strategies.
    """
    url_hash = get_url_hash(url)
    output_template = str(TEMP_DIR / f"vid_{url_hash}.%(ext)s")
    final_video_path = str(TEMP_DIR / f"vid_{url_hash}.mp4")

    def _try_dl(opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Video')
            duration = int(info.get('duration') or 0)
            
            actual_path = None
            if os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1024:
                actual_path = final_video_path
            else:
                for f in TEMP_DIR.glob(f"vid_{url_hash}.*"):
                    if f.suffix.lower() in ['.mp4', '.mkv', '.webm', '.mov'] and f.stat().st_size > 1024:
                        actual_path = str(f)
                        break

            if actual_path:
                return {
                    'file_path': actual_path,
                    'title': title,
                    'duration': duration,
                    'url_hash': url_hash
                }
        return None

    def _download():
        # Attempt 1: Optimal 720p/MP4 under 48MB
        opts_1 = {
            'format': 'bestvideo[height<=720][filesize<48M][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][filesize<48M]/best[filesize<48M]/best',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'merge_output_format': 'mp4',
            'socket_timeout': 15,
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
        }
        try:
            res = _try_dl(opts_1)
            if res:
                return res
        except Exception as e1:
            logger.warning(f"Media video download attempt 1 failed ({e1}), trying attempt 2...")

        # Attempt 2: Universal best format
        opts_2 = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'merge_output_format': 'mp4',
            'socket_timeout': 20,
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
        }
        try:
            return _try_dl(opts_2)
        except Exception as e2:
            logger.error(f"Media video download attempt 2 failed: {e2}")
            return None

    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(None, _download)
        if res and res.get('file_path') and os.path.exists(res['file_path']):
            res['file_path'] = await ensure_video_under_50mb(res['file_path'])
            return res
    except Exception as e:
        logger.error(f"Error downloading video from {url}: {e}")
        return None
