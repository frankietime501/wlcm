# config.py
import os

# Env-var override works in Docker; falls back to literal for local runs
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "123456789012345678"))

DB_PATH = os.getenv("DB_PATH", "bot_data.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

FONT_BOLD = "fonts/bold.ttf"
FONT_REGULAR = "fonts/regular.ttf"
FONT_SERIF = "fonts/serif_bold.ttf"
FONT_DISPLAY = "fonts/anton.ttf"
FONT_TYPEWRITER = "fonts/special_elite.ttf"

ID_CODE_PREFIX = os.getenv("ID_CODE_PREFIX", "FBTXX")