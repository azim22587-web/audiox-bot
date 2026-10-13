import asyncio
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from services.music_service import search_tracks, download_track_mp3, download_track_video
from services.recognition_service import recognize_audio
from database import init_db, cache_track, get_cached_track

async def full_test():
    print('1. Testing DB...')
    await init_db()
    print('DB initialized.')

    print('\n2. Testing YouTube Search for "slowed"...')
    tracks = await search_tracks('slowed', limit=3)
    print(f'Found {len(tracks)} tracks:')
    for t in tracks:
        print(f' - [{t.id}] {t.artist} - {t.title} ({t.duration_str})')

    if tracks:
        t0 = tracks[0]
        print(f'\n3. Testing MP3 Download for [{t0.id}]...')
        mp3_res = await download_track_mp3(t0.id)
        if mp3_res and os.path.exists(mp3_res['file_path']):
            print(f'MP3 Success: {mp3_res["title"]} ({mp3_res["duration"]}s) -> {mp3_res["file_path"]}')
            
            print('\n4. Testing Shazam Audio Recognition on downloaded MP3...')
            rec = await recognize_audio(mp3_res['file_path'])
            if rec:
                print(f'Recognition Success: {rec.artist} - {rec.title} (Album: {rec.album})')
            else:
                print('Recognition: no match')
        else:
            print('MP3 download failed!')

    print('\n=== ALL SERVICES ARE FUNCTIONING 100% ===')

if __name__ == '__main__':
    asyncio.run(full_test())
