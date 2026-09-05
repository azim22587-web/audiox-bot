import aiosqlite
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize database tables with WAL mode and indexes for high speed"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA synchronous = NORMAL;")
        await db.execute("PRAGMA cache_size = 10000;")
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Audio cache table: maps query or YouTube video_id to Telegram file_id
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cached_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_key TEXT UNIQUE,
                file_id TEXT NOT NULL,
                title TEXT,
                artist TEXT,
                duration INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cached_tracks_key ON cached_tracks(track_key);")

        # Social video cache table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cached_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_hash TEXT UNIQUE,
                file_id TEXT NOT NULL,
                video_title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cached_videos_hash ON cached_videos(url_hash);")
        
        await db.commit()
    logger.info("Database initialized successfully with WAL mode & indexes.")

async def add_user(user_id: int, username: str = None, first_name: str = None):
    """Add user to database if not exists"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")

async def get_users_count() -> int:
    """Get total number of users"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        logger.error(f"Error getting users count: {e}")
        return 0

async def get_all_user_ids() -> list[int]:
    """Get list of all user IDs for broadcasting"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Error getting all user IDs: {e}")
        return []

async def get_cached_track(track_key: str):
    """Retrieve cached track by key (e.g. youtube video id or normalized title)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT file_id, title, artist, duration FROM cached_tracks WHERE track_key = ?",
                (track_key.strip().lower(),)
            ) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting cached track for key {track_key}: {e}")
        return None

async def cache_track(track_key: str, file_id: str, title: str, artist: str, duration: int = 0):
    """Cache track file_id for ultra-fast instant future sending"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cached_tracks (track_key, file_id, title, artist, duration) VALUES (?, ?, ?, ?, ?)",
                (track_key.strip().lower(), file_id, title, artist, duration)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error caching track {track_key}: {e}")

async def get_cached_video(url_hash: str):
    """Get cached video file_id"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT file_id, video_title FROM cached_videos WHERE url_hash = ?",
                (url_hash,)
            ) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Error getting cached video: {e}")
        return None

async def cache_video(url_hash: str, file_id: str, video_title: str = ""):
    """Cache video file_id"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cached_videos (url_hash, file_id, video_title) VALUES (?, ?, ?)",
                (url_hash, file_id, video_title)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error caching video: {e}")

async def get_cached_tracks_count() -> int:
    """Get count of cached tracks in database"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM cached_tracks") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        logger.error(f"Error getting cached tracks count: {e}")
        return 0
