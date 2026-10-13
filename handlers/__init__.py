# Handlers package
from .start import router as start_router
from .text_search import router as text_search_router
from .media_shazam import router as media_shazam_router
from .downloader import router as downloader_router
from .admin import router as admin_router

all_routers = [
    start_router,
    admin_router,
    downloader_router,
    media_shazam_router,
    text_search_router,
]
