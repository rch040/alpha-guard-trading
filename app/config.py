import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TRADING_ENV = os.getenv("TRADING_ENV", "SANDBOX").upper()
    MOCK_MODE = os.getenv("MOCK_MODE", "True").lower() == "true"

    # Tiger OpenAPI
    TIGER_ID = os.getenv("TIGER_ID", "")
    TIGER_ACCOUNT = os.getenv("TIGER_ACCOUNT", "")
    TIGER_LICENSE = os.getenv("TIGER_LICENSE", "TBHK")
    TIGER_PRIVATE_KEY_PATH = os.getenv("TIGER_PRIVATE_KEY_PATH", "/app/keys/tiger_private_key.pem")

    # Gemini AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # 硬性風控參數
    MAX_SINGLE_STOCK_PCT = float(os.getenv("MAX_SINGLE_STOCK_PCT", "0.50"))
    WATCHLIST = [s.strip().upper() for s in os.getenv("DEFAULT_WATCHLIST", "NVDA,TSLA,QQQ,AAPL").split(",") if s.strip()]
    os.makedirs("data", exist_ok=True)
    DB_PATH = os.path.join("data", "alpha_guard.db")