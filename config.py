import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8080").strip().rstrip("/")
HOST = os.getenv("HOST", "0.0.0.0").strip()
PORT = int(os.getenv("PORT", "8080").strip())
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow").strip()
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "10").strip())
DIGEST_MINUTE = int(os.getenv("DIGEST_MINUTE", "0").strip())

DB_PATH = str(BASE_DIR / "reminders.db")
STATIC_DIR = str(BASE_DIR / "static")
