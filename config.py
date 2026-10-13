import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin Telegram IDs (comma-separated list, e.g. "12345678,87654321")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]

# Admin / Creator Telegram Username for ads and credits (e.g. "my_username")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip().lstrip("@")

# Audio Recognition API Keys
AUDD_API_KEY = os.getenv("AUDD_API_KEY", "").strip()
ACRCLOUD_HOST = os.getenv("ACRCLOUD_HOST", "").strip()
ACRCLOUD_KEY = os.getenv("ACRCLOUD_KEY", "").strip()
ACRCLOUD_SECRET = os.getenv("ACRCLOUD_SECRET", "").strip()

# Directories
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "database.sqlite3"

# FFmpeg Detection
def get_ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.exists(ffmpeg_exe):
            return ffmpeg_exe
    except Exception:
        pass

    import shutil
    ffmpeg_sys = shutil.which("ffmpeg")
    if ffmpeg_sys:
        return ffmpeg_sys

    return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_path()
