import hashlib
import html
import json
import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

SEEN_FILE = Path("data/seen.json")
MAX_SEEN = 1000
MAX_MESSAGES_PER_RUN = 8

SEARCHES = [
    {
        "label": "Coreano 🇰🇷",
        "query": "변우석",
        "hl": "ko",
        "gl": "KR",
        "ceid": "KR:ko",
    },
    {
        "label": "Inglés 🌎",
        "query": '"Byeon Woo Seok"',
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    },
    {
        "label": "Español 🌎",
        "query": '"Byeon Woo Seok"',
        "hl": "es-419",
        "gl": "US",
        "ceid": "US:es-419",
    },
]


def validate_config() -> None:
    missing = []
    if not TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise RuntimeError(
            "Faltan secretos de GitHub: " + ", ".join(missing)
        )


def rss_url(search: dict[str, str]) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(search['query'])}"
        f"&hl={search['hl']}&gl={search['gl']}&ceid={search['ceid']}"
    )


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else [])
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    trimmed = list(seen)[-MAX_SEEN:]
    SEEN_FILE.write_text(
        json.dumps(trimmed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def entry_id(entry: Any) -> str:
    raw = (
        entry.get("id")
        or entry.get("link")
        or entry.get("title")
        or json.dumps(entry, sort_keys=True, default=str)
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_date(entry: Any) -> datetime:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc)


def clean_title(title: str) -> str:
    return html.unescape(title).strip()


def send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram rechazó el mensaje: {payload}")


def collect_news() -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []

    for search in SEARCHES:
        feed = feedparser.parse(rss_url(search))

        if getattr(feed, "bozo", False):
            print(
                f"Advertencia leyendo {search['label']}: "
                f"{getattr(feed, 'bozo_exception', 'error desconocido')}"
            )

        for entry in feed.entries[:15]:
            title = clean_title(entry.get("title", "Sin título"))
            link = entry.get("link", "")
            if not link:
                continue

            collected.append(
                {
                    "id": entry_id(entry),
                    "title": title,
                    "link": link,
                    "date": parse_date(entry),
                    "search": search["label"],
                }
            )

    collected.sort(key=lambda item: item["date"])
    return collected


def main() -> int:
    validate_config()
    seen = load_seen()
    news = collect_news()

    new_items = [item for item in news if item["id"] not in seen]
    new_items = new_items[-MAX_MESSAGES_PER_RUN:]

    if not new_items:
        print("No hay noticias nuevas.")
        return 0

    for item in new_items:
        date_text = item["date"].astimezone().strftime("%d/%m/%Y %I:%M %p")
        message = (
            "🚨 NUEVA NOTICIA\n\n"
            f"💙 {item['title']}\n\n"
            f"🌐 Búsqueda: {item['search']}\n"
            f"🕐 {date_text}\n\n"
            f"🔗 {item['link']}"
        )
        send_telegram(message)
        seen.add(item["id"])
        print(f"Enviada: {item['title']}")

    save_seen(seen)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
