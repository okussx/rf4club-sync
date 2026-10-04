import os
from pathlib import Path


def _default_data_dir():
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "RF4Club Sync"
    return Path.home() / ".rf4club-sync"


DATA_DIR = Path(os.getenv("RF4CLUB_DATA_DIR", str(_default_data_dir()))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)

REFERENCE_RESOLUTION = (1920, 1080)
KEEP_REGION = (760, 900, 400, 150)
FISH_HEADER_REGION = (650, 20, 620, 180)
TROPHY_LABEL_REGION = (560, 0, 800, 260)
STATISTICS_TRIGGER_REGION = (650, 0, 650, 125)
STATISTICS_SUMMARY_REGION = (150, 120, 1680, 215)
STATISTICS_RECORDS_REGION = (240, 325, 1500, 625)

KEEP_TRIGGER_WORDS = ("keep", "tut", "tutun")
TROPHY_WORDS = ("trophy", "odul", "ganimet", "trofe", "kupa")
SUPER_TROPHY_WORDS = (
    "rare trophy",
    "super trophy",
    "super odul",
    "super ganimet",
    "super trofe",
    "super kupa",
)
VALUABLE_WORDS = ("valuable", "degerli", "değerli")
STATISTICS_TITLE_WORDS = ("oyuncu bilgileri", "player information")
STATISTICS_TAB_WORDS = ("istatistikler", "statistics")

KEEP_MIN_CONFIDENCE = 0.35
FISH_NAME_MIN_CONFIDENCE = 0.40
VALUABLE_MIN_CONFIDENCE = 0.25
OCR_SCALE = 2
POLL_INTERVAL_SECONDS = 0.45
KEEP_REARM_DELAY_SECONDS = 1.25
STATISTICS_TRIGGER_POLL_SECONDS = 3.0
STATISTICS_SYNC_INTERVAL_SECONDS = 5 * 60

GAME_PROCESS_NAME = "rf4_x64.exe"
API_BASE_URL = os.getenv("RF4CLUB_API_URL", "https://rf4club.com").rstrip("/")
DEVICE_NAME = os.getenv("RF4CLUB_DEVICE_NAME", "RF4Club Sync")
DEVICE_TOKEN_FILE = str(DATA_DIR / "device.json")
SYNC_SOUND_ENABLED = os.getenv("RF4CLUB_SYNC_SOUND", "1") != "0"

CATCH_LOG_FILE = str(DATA_DIR / "rf4_catches.csv")
RAW_OCR_LOG_FILE = str(DATA_DIR / "rf4_raw_ocr_log.csv")
TROPHY_SCREENSHOT_DIR = str(DATA_DIR / "trophy_screenshots")
PENDING_SYNC_DIR = str(DATA_DIR / "pending_sync")
STATISTICS_STATE_FILE = str(DATA_DIR / "statistics-state.json")

HTTP_TIMEOUT_SECONDS = 30
MAX_PENDING_RETRIES_PER_CYCLE = 5
