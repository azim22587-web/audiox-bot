import asyncio
import sys
import os
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def run_tests():
    print("🧪 1. Testing imports...")
    from config import BOT_TOKEN, FFMPEG_PATH, TEMP_DIR
    from database import init_db, add_user, cache_track, get_cached_track, get_users_count, cache_video, get_cached_video
    from services.ffmpeg_helper import extract_audio_sample, convert_to_mp3, convert_to_round_video_note, get_video_duration
    from services.music_service import search_tracks, format_duration
    from services.downloader_service import is_social_url, extract_urls
    from utils.keyboards import get_search_results_keyboard, get_track_format_keyboard, get_media_actions_keyboard
    from handlers import all_routers
    print(f"   ✅ All modules imported successfully! FFmpeg path: {FFMPEG_PATH}")

    print("🧪 2. Testing SQLite database and caching (Tracks & Round Videos)...")
    await init_db()
    await add_user(1234567, "testuser", "Test")
    user_count = await get_users_count()
    assert user_count >= 1, "User count should be >= 1"
    
    await cache_track("test_id_123", "FILE_ID_SAMPLE", "Test Song", "Test Artist", 180)
    cached = await get_cached_track("test_id_123")
    assert cached is not None and cached[0] == "FILE_ID_SAMPLE", "Cached track mismatch"

    await cache_video("round_test_key", "ROUND_FILE_ID", "Round Test")
    cached_round = await get_cached_video("round_test_key")
    assert cached_round is not None and cached_round[0] == "ROUND_FILE_ID", "Cached round video mismatch"
    print("   ✅ Database & Caching passed successfully!")

    print("🧪 3. Testing music & concert search engine (Munisa Rizayeva)...")
    results = await search_tracks("Munisa Rizayeva", limit=3)
    assert len(results) > 0, "Should return at least 1 search result"
    print(f"   ✅ Search found {len(results)} tracks/concerts:")
    for r in results:
        print(f"      - {r.title} ({r.artist}) [{r.duration_str}] -> {r.url}")

    print("🧪 4. Testing Keyboards with Round Video (Yumaloq) buttons...")
    fmt_kb = get_track_format_keyboard("sample_id")
    has_round_btn = any("dl_round:sample_id" in btn.callback_data for row in fmt_kb.inline_keyboard for btn in row)
    assert has_round_btn, "Format keyboard must include dl_round button"

    act_kb = get_media_actions_keyboard("video", "sample_id")
    has_make_round_btn = any("make_round_vid:sample_id" in btn.callback_data for row in act_kb.inline_keyboard for btn in row)
    assert has_make_round_btn, "Media action keyboard must include make_round_vid button"
    print("   ✅ Round video keyboard buttons verified successfully!")

    print("🧪 5. Testing FFmpeg Round Video Note conversion...")
    test_in = TEMP_DIR / "test_input.mp4"
    test_round_out = TEMP_DIR / "test_round_out.mp4"
    
    cmd_gen = [
        FFMPEG_PATH, "-y",
        "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100",
        "-t", "3",
        "-c:v", "libx264", "-c:a", "aac",
        str(test_in)
    ]
    subprocess.run(cmd_gen, capture_output=True, check=True)
    
    success = await convert_to_round_video_note(test_in, test_round_out, max_duration=60, size=384)
    assert success and os.path.exists(test_round_out) and os.path.getsize(test_round_out) > 1024, "Round video conversion failed"
    dur = get_video_duration(test_round_out)
    assert dur >= 2, f"Round video duration should be >= 2, got {dur}"
    print(f"   ✅ Round video note conversion passed successfully! Generated size: {os.path.getsize(test_round_out)} bytes, duration: {dur}s")

    for p in [test_in, test_round_out]:
        if os.path.exists(p):
            os.remove(p)

    print("\n🎉 BARCHA TESTLAR 100% MUVAFFAQIYATLI YAKUNLANDI! AudioX boti to'liq tayyor.")

if __name__ == "__main__":
    asyncio.run(run_tests())
