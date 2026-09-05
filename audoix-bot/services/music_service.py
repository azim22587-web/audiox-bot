import asyncio
import logging
import os
import re
import html
import time
from pathlib import Path
import aiohttp
import yt_dlp
from mutagen.easyid3 import EasyID3
from config import FFMPEG_PATH, TEMP_DIR
from services.ffmpeg_helper import ensure_video_under_50mb

logger = logging.getLogger(__name__)

# In-memory search cache for instant 0.001s responses
SEARCH_CACHE = {}
CACHE_TTL = 3600 * 24  # 24 hours

# Persistent aiohttp session for InnerTube API
_HTTP_SESSION: aiohttp.ClientSession | None = None

async def get_http_session() -> aiohttp.ClientSession:
    global _HTTP_SESSION
    if _HTTP_SESSION is None or _HTTP_SESSION.closed:
        timeout = aiohttp.ClientTimeout(total=8, connect=3)
        connector = aiohttp.TCPConnector(limit=50, keepalive_timeout=60, ttl_dns_cache=300)
        _HTTP_SESSION = aiohttp.ClientSession(timeout=timeout, connector=connector)
    return _HTTP_SESSION

class MusicTrack:
    def __init__(self, track_id: str, title: str, artist: str, duration: int, duration_str: str, url: str, thumbnail: str = ""):
        self.id = track_id
        self.title = title.strip()
        self.artist = artist.strip()
        self.duration = duration
        self.duration_str = duration_str
        self.url = url
        self.thumbnail = thumbnail

    @property
    def safe_title(self) -> str:
        return html.escape(self.title)

    @property
    def safe_artist(self) -> str:
        return html.escape(self.artist)

def parse_duration_str(dur_str: str) -> int:
    """Parse '3:45' or '1:12:30' string to seconds"""
    if not dur_str:
        return 0
    parts = dur_str.strip().split(':')
    try:
        if len(parts) == 1:
            return int(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except Exception:
        pass
    return 0

def format_duration(seconds: int) -> str:
    if not seconds:
        return "0:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def clean_song_title(raw_title: str, uploader: str = "Audoix") -> tuple[str, str]:
    """Extract clean song title and artist from raw YouTube title"""
    raw_title = raw_title.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    
    # Remove hashtags (#new, #2025, #klip etc.)
    raw_title = re.sub(r'#\w+', '', raw_title)

    if ' - ' in raw_title:
        parts = raw_title.split(' - ', 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    elif ' – ' in raw_title:
        parts = raw_title.split(' – ', 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    elif ' | ' in raw_title:
        parts = raw_title.split(' | ', 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    else:
        title = raw_title
        artist = uploader.replace(" - Topic", "").replace("VEVO", "").strip()

    # Strip extraneous tags
    title = re.sub(
        r'[\(\[](Official|Audio|Video|Music Video|Lyrics|HD|HQ|Visualizer|4K|Clip|Remix|Klip|Premyera|Premyere|mp3|Original|Tarona|RizaNova).*?[\)\]]',
        '',
        title,
        flags=re.IGNORECASE
    ).strip()
    
    # Remove dangling quotes or trailing symbols
    title = re.sub(r'\s+', ' ', title).strip(' -|/:,"\'')
    artist = re.sub(r'\s+', ' ', artist).strip(' -|/:,"\'')

    return title or raw_title.strip(), artist or "Audoix"

async def _search_innertube(query: str, limit: int = 5) -> list[MusicTrack]:
    """Ultra-fast Direct YouTube InnerTube API search (~0.15s - 0.3s)"""
    url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json',
    }
    payload = {
        'context': {
            'client': {
                'clientName': 'WEB',
                'clientVersion': '2.20240101.00.00',
                'hl': 'uz',
                'gl': 'UZ',
            }
        },
        'query': query
    }
    
    session = await get_http_session()
    async with session.post(url, json=payload, headers=headers) as resp:
        if resp.status != 200:
            return []
        
        data = await resp.json()
        tracks = []
        contents = (
            data.get('contents', {})
            .get('twoColumnSearchResultsRenderer', {})
            .get('primaryContents', {})
            .get('sectionListRenderer', {})
            .get('contents', [])
        )
        
        for section in contents:
            item_section = section.get('itemSectionRenderer', {}).get('contents', [])
            for item in item_section:
                if 'videoRenderer' in item:
                    vr = item['videoRenderer']
                    vid_id = vr.get('videoId', '')
                    if not vid_id or len(vid_id) > 15:
                        continue
                    
                    raw_title = vr.get('title', {}).get('runs', [{}])[0].get('text', '')
                    if not raw_title:
                        continue
                    
                    dur_text = vr.get('lengthText', {}).get('simpleText', '')
                    duration_sec = parse_duration_str(dur_text)
                    
                    # Ignore live streams or very long playlists > 30 min
                    if duration_sec > 1800 or (not dur_text and 'LIVE' in raw_title.upper()):
                        continue
                    
                    owner_text = vr.get('ownerText', {}).get('runs', [{}])[0].get('text', 'Audoix')
                    title, artist = clean_song_title(raw_title, owner_text)
                    
                    track_url = f"https://www.youtube.com/watch?v={vid_id}"
                    tracks.append(MusicTrack(
                        track_id=vid_id,
                        title=title,
                        artist=artist,
                        duration=duration_sec,
                        duration_str=dur_text or format_duration(duration_sec),
                        url=track_url
                    ))
                    
                    if len(tracks) >= limit:
                        return tracks
                        
        return tracks

def _search_ytdlp_fallback(query: str, limit: int = 5) -> list[MusicTrack]:
    """High-speed fallback search using yt-dlp flat extraction"""
    ydl_opts = {
        'format': 'bestaudio/best',
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
        'socket_timeout': 6,
        'nocheckcertificate': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        search_results = ydl.extract_info(f"ytsearch{limit + 3}:{query}", download=False)
        tracks = []
        if search_results and 'entries' in search_results:
            for entry in search_results['entries']:
                if not entry or entry.get('_type') == 'playlist':
                    continue
                
                t_id = entry.get('id', '')
                if not t_id or len(t_id) > 15:
                    continue

                duration = int(entry.get('duration') or 0)
                if duration > 1800:
                    continue

                raw_title = entry.get('title', 'Musiqa')
                uploader = entry.get('uploader', 'Audoix')
                title, artist = clean_song_title(raw_title, uploader)

                url = f"https://www.youtube.com/watch?v={t_id}"
                tracks.append(MusicTrack(
                    track_id=t_id,
                    title=title,
                    artist=artist,
                    duration=duration,
                    duration_str=format_duration(duration),
                    url=url
                ))

                if len(tracks) >= limit:
                    break
        return tracks

async def search_tracks(query: str, limit: int = 5) -> list[MusicTrack]:
    """
    Lightning-fast search for music/video tracks:
    1. Check RAM Cache (0.001s)
    2. Direct InnerTube API (0.15s - 0.3s)
    3. yt-dlp flat search fallback
    """
    norm_query = query.strip().lower()
    
    # 1. Check RAM Cache
    if norm_query in SEARCH_CACHE:
        cached_time, cached_results = SEARCH_CACHE[norm_query]
        if time.time() - cached_time < CACHE_TTL:
            return cached_results

    # 2. Try Direct InnerTube API
    try:
        results = await _search_innertube(query, limit=limit)
        if results:
            SEARCH_CACHE[norm_query] = (time.time(), results)
            return results
    except Exception as e:
        logger.warning(f"InnerTube search failed, falling back to yt-dlp: {e}")

    # 3. Fallback to yt-dlp
    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(None, _search_ytdlp_fallback, query, limit)
        if results:
            SEARCH_CACHE[norm_query] = (time.time(), results)
        return results
    except Exception as e:
        logger.error(f"Error searching tracks for '{query}': {e}")
        return []

async def download_track_mp3(track_id_or_url: str, title: str = "", artist: str = "") -> dict | None:
    """Robust multi-tier audio stream download with automatic fallback strategies"""
    if not track_id_or_url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={track_id_or_url}"
        unique_id = track_id_or_url
    else:
        url = track_id_or_url
        unique_id = re.sub(r'\W+', '_', track_id_or_url)[-12:]

    output_template = str(TEMP_DIR / f"track_{unique_id}.%(ext)s")
    final_mp3_path = str(TEMP_DIR / f"track_{unique_id}.mp3")

    def _try_download(opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            nonlocal title, artist
            extracted_title = info.get('title', 'Musiqa')
            extracted_uploader = info.get('uploader', 'Audoix')
            duration = int(info.get('duration') or 0)
            
            if not title:
                title, artist = clean_song_title(extracted_title, extracted_uploader)

            if os.path.exists(final_mp3_path) and os.path.getsize(final_mp3_path) > 1024:
                try:
                    try:
                        audio = EasyID3(final_mp3_path)
                    except Exception:
                        audio = EasyID3()
                        audio.save(final_mp3_path)
                    audio['title'] = title
                    audio['artist'] = artist
                    audio['album'] = "Audoix Music"
                    audio.save()
                except Exception as ex:
                    logger.debug(f"ID3 tagging note: {ex}")

                return {
                    'file_path': final_mp3_path,
                    'title': title or "Musiqa",
                    'artist': artist or "Audoix",
                    'duration': duration
                }
        return None

    def _download_all_attempts():
        # Attempt 1: Fast modern audio format with client rotation
        opts_1 = {
            'format': 'ba[ext=m4a]/ba[ext=webm]/ba/b[height<=360]/b',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'writethumbnail': False,
            'socket_timeout': 10,
            'nocheckcertificate': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'tv_embedded', 'web']}},
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }
            ],
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        try:
            res = _try_download(opts_1)
            if res:
                return res
        except Exception as e1:
            logger.warning(f"Audio download attempt 1 failed ({e1}), trying attempt 2...")

        # Attempt 2: Universal standard format without restrictive extractor args
        opts_2 = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'socket_timeout': 15,
            'nocheckcertificate': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }
            ],
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        try:
            res = _try_download(opts_2)
            if res:
                return res
        except Exception as e2:
            logger.warning(f"Audio download attempt 2 failed ({e2}), trying attempt 3...")

        # Attempt 3: Fallback stream download (140/251/18/best)
        opts_3 = {
            'format': '140/251/18/best',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'socket_timeout': 20,
            'nocheckcertificate': True,
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }
            ],
            'max_filesize': 50 * 1024 * 1024,
            'quiet': True,
            'no_warnings': True,
        }
        try:
            return _try_download(opts_3)
        except Exception as e3:
            logger.error(f"Audio download attempt 3 failed: {e3}")
            return None

    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _download_all_attempts)
    except Exception as e:
        logger.error(f"Error downloading track {track_id_or_url}: {e}")
        return None

async def download_track_video(track_id_or_url: str) -> dict | None:
    """Multi-tier video stream download with automatic format and size management"""
    if not track_id_or_url.startswith("http"):
        url = f"https://www.youtube.com/watch?v={track_id_or_url}"
        unique_id = track_id_or_url
    else:
        url = track_id_or_url
        unique_id = re.sub(r'\W+', '_', track_id_or_url)[-12:]

    output_template = str(TEMP_DIR / f"vid_{unique_id}.%(ext)s")
    final_video_path = str(TEMP_DIR / f"vid_{unique_id}.mp4")

    def _try_download_video(opts: dict):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Video')
            duration = int(info.get('duration') or 0)
            
            actual_path = None
            if os.path.exists(final_video_path) and os.path.getsize(final_video_path) > 1024:
                actual_path = final_video_path
            else:
                for f in TEMP_DIR.glob(f"vid_{unique_id}.*"):
                    if f.suffix.lower() in ['.mp4', '.mkv', '.webm', '.mov'] and f.stat().st_size > 1024:
                        actual_path = str(f)
                        break

            if actual_path:
                return {
                    'file_path': actual_path,
                    'title': title,
                    'duration': duration,
                    'unique_id': unique_id
                }
        return None

    def _download_all_video_attempts():
        # Attempt 1: Fast direct MP4 360p/480p/720p
        opts_1 = {
            'format': '18/bestvideo[height<=720][filesize<48M][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][filesize<48M]/best[height<=480]/best',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'merge_output_format': 'mp4',
            'socket_timeout': 12,
            'nocheckcertificate': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'tv_embedded', 'web']}},
            'quiet': True,
            'no_warnings': True,
        }
        try:
            res = _try_download_video(opts_1)
            if res:
                return res
        except Exception as e1:
            logger.warning(f"Video download attempt 1 failed ({e1}), trying attempt 2...")

        # Attempt 2: Universal best MP4
        opts_2 = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_template,
            'ffmpeg_location': FFMPEG_PATH,
            'merge_output_format': 'mp4',
            'socket_timeout': 18,
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
        }
        try:
            return _try_download_video(opts_2)
        except Exception as e2:
            logger.error(f"Video download attempt 2 failed: {e2}")
            return None

    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(None, _download_all_video_attempts)
        if res and res.get('file_path') and os.path.exists(res['file_path']):
            res['file_path'] = await ensure_video_under_50mb(res['file_path'])
            return res
    except Exception as e:
        logger.error(f"Error downloading video {track_id_or_url}: {e}")
        return None
