import asyncio
import os
import subprocess
import logging
from pathlib import Path
from config import FFMPEG_PATH, TEMP_DIR

logger = logging.getLogger(__name__)

async def extract_audio_sample(input_path: str | Path, output_path: str | Path, duration: int = 25) -> bool:
    """
    Extract a clean 128k MP3 sample of `duration` seconds for audio recognition.
    """
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_path),
        "-t", str(duration),
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "44100",
        "-ac", "2",
        "-ab", "128k",
        str(output_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.communicate()
        return process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f"Error extracting audio sample: {e}")
        return False

async def convert_to_wav(input_path: str | Path, output_path: str | Path, duration: int = 30) -> bool:
    """
    Convert audio to 16kHz mono WAV for speech/audio recognition.
    """
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_path),
        "-t", str(duration),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.communicate()
        return process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f"Error converting to wav: {e}")
        return False

async def convert_to_mp3(input_path: str | Path, output_path: str | Path) -> bool:
    """
    Convert any video or audio file to standard high-quality MP3 (192kbps).
    """
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-ar", "44100",
        "-ac", "2",
        "-ab", "192k",
        str(output_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.communicate()
        return process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        logger.error(f"Error converting to mp3: {e}")
        return False

async def ensure_video_under_50mb(input_path: str | Path) -> str:
    """
    Ensure video is strictly under 49MB for Telegram Bot API limit.
    If it's > 49MB, automatically compresses it using fast FFmpeg.
    """
    if not os.path.exists(input_path):
        return str(input_path)

    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    if file_size_mb <= 49.0:
        return str(input_path)

    compressed_output = str(input_path).rsplit(".", 1)[0] + "_cmp.mp4"
    logger.info(f"Video size {file_size_mb:.2f}MB exceeds 49MB limit. Compressing to fit Telegram limit...")

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_path),
        "-vf", "scale=-2:'min(480,ih)'",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "96k",
        "-fs", "48M",
        compressed_output
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await process.communicate()
        if process.returncode == 0 and os.path.exists(compressed_output) and os.path.getsize(compressed_output) > 0:
            return compressed_output
    except Exception as e:
        logger.error(f"Error compressing video: {e}")

    return str(input_path)
