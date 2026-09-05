import html
from config import ADMIN_USERNAME

def format_caption(title: str, artist: str = "", bot_username: str = "") -> str:
    """
    Format standard beautiful media caption including bot username, creator and advertising contacts.
    """
    safe_title = html.escape(title)
    safe_artist = html.escape(artist) if artist else ""

    lines = []
    if safe_title and safe_artist:
        lines.append(f"🎵 <b>{safe_title}</b>")
        lines.append(f"👤 <i>{safe_artist}</i>")
    elif safe_title:
        lines.append(f"🎬 <b>{safe_title}</b>")

    lines.append("")
    if bot_username:
        lines.append(f"🤖 <b>Bot:</b> @{bot_username}")
    
    if ADMIN_USERNAME:
        lines.append(f"👨‍💻 <b>Bot yaratuvchisi:</b> @{ADMIN_USERNAME}")
        lines.append(f"📢 <b>Reklama va murojaat:</b> @{ADMIN_USERNAME}")
    else:
        lines.append("📢 <b>Reklama va murojaat uchun admin bilan bog'laning</b>")

    return "\n".join(lines)
