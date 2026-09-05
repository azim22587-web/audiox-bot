import asyncio
import sys
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def run_tests():
    print("🧪 1. Testing imports...")
    from config import BOT_TOKEN, FFMPEG_PATH, TEMP_DIR
    from database import init_db, add_user, cache_track, get_cached_track, get_users_count
    from services.ffmpeg_helper import extract_audio_sample, convert_to_mp3
    from services.music_service import search_tracks, format_duration
    from services.downloader_service import is_social_url, extract_urls
    from handlers import all_routers
    print(f"   ✅ All modules imported successfully! FFmpeg path: {FFMPEG_PATH}")

    print("🧪 2. Testing SQLite database and caching...")
    await init_db()
    await add_user(1234567, "testuser", "Test")
    user_count = await get_users_count()
    assert user_count >= 1, "User count should be >= 1"
    
    await cache_track("test_id_123", "FILE_ID_SAMPLE", "Test Song", "Test Artist", 180)
    cached = await get_cached_track("test_id_123")
    assert cached is not None and cached[0] == "FILE_ID_SAMPLE", "Cached track mismatch"
    print("   ✅ Database & Caching passed successfully!")

    print("🧪 3. Testing music search engine...")
    results = await search_tracks("Yulduz Usmonova", limit=2)
    assert len(results) > 0, "Should return at least 1 search result"
    print(f"   ✅ Search found {len(results)} tracks:")
    for r in results:
        print(f"      - {r.title} ({r.artist}) [{r.duration_str}] -> {r.url}")

    print("🧪 4. Testing URL extractor...")
    assert is_social_url("https://www.instagram.com/reel/C7-xyz/"), "Instagram URL detection failed"
    assert is_social_url("https://vt.tiktok.com/ZSxyz/"), "TikTok URL detection failed"
    assert is_social_url("https://youtu.be/dQw4w9WgXcQ"), "YouTube URL detection failed"
    print("   ✅ URL detection passed successfully!")

    print("\n🎉 Barcha testlar muvaffaqiyatli yakunlandi! Bot to'liq tayyor va xatosiz ishlaydi.")

if __name__ == "__main__":
    asyncio.run(run_tests())
