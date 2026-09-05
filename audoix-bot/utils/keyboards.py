from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_search_results_keyboard(tracks_data: list) -> InlineKeyboardMarkup:
    """
    Generate inline keyboard with numbers corresponding to search results.
    e.g. [ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]
    """
    buttons_row = []
    for idx, track in enumerate(tracks_data, 1):
        # When clicking number, open format selector (Audio or Video)
        buttons_row.append(
            InlineKeyboardButton(text=f"{idx}", callback_data=f"select_track:{track.id}")
        )
    
    keyboard = [
        buttons_row,
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_search")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_track_format_keyboard(track_id: str) -> InlineKeyboardMarkup:
    """
    Format selection keyboard for selected track:
    [ 🎵 Audio (MP3) ]  [ 🎬 Video (MP4) ]
    [ 🔙 Orqaga ]
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🎵 Audio (MP3)", callback_data=f"dl_song:{track_id}"),
            InlineKeyboardButton(text="🎬 Video (MP4)", callback_data=f"dl_vid:{track_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_media_actions_keyboard(media_type: str, item_id: str) -> InlineKeyboardMarkup:
    """
    Action buttons below sent media
    """
    if media_type == "video":
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🎵 Musiqasini yuklab olish (MP3)",
                    callback_data=f"dl_audio_from_vid:{item_id}"
                )
            ]
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(
                    text="🎬 Videoni yuklab olish (MP4)",
                    callback_data=f"dl_vid:{item_id}"
                )
            ]
        ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel keyboard"""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin_broadcast")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
