import requests
from app.config import Config

def send_telegram_alert(message: str) -> bool:
    if not Config.TELEGRAM_BOT_TOKEN or not Config.TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=8)
        return resp.status_code == 200
    except Exception:
        return False