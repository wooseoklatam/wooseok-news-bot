import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import feedparser
import requests


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

SEEN_FILE = Path("data/seen.json")

MAX_SEEN = 1000

# Durante la primera ejecución puede enviar hasta 8 noticias.
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
        f"&hl={search['hl']}"
        f"&gl={search['gl']}"
        f"&ceid={search['ceid']}"
    )


def load_seen() -> list[str]:
    if not SEEN_FILE.exists():
        return []

    try:
        data = json.loads(SEEN_FILE.read_text(encoding="utf-8"))

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        return []


def save_seen(seen: list[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)

    unique_seen = list(dict.fromkeys(seen))
    trimmed = unique_seen[-MAX_SEEN:]

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

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


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
    title = html.unescape(title)
    title = re.sub(r"<[^>]+>", "", title)
    return title.strip()


def split_title_and_source(title: str) -> tuple[str, str]:
    """
    Google News normalmente devuelve:
    Título de la noticia - Nombre del medio
    """

    if " - " not in title:
        return title, "Fuente original"

    article_title, source = title.rsplit(" - ", 1)

    return article_title.strip(), source.strip()


def clean_source(source: str, link: str) -> str:
    if source and source != "Fuente original":
        return source

    try:
        domain = urlparse(link).netloc
        return domain.replace("www.", "") or "Fuente original"

    except ValueError:
        return "Fuente original"


def escape_html(text: str) -> str:
    return html.escape(text, quote=False)


def send_telegram(
    message: str,
    article_link: str,
    search_query: str,
) -> None:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    google_search_url = (
        "https://www.google.com/search?q="
        + quote_plus(search_query)
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "💗 Abrir noticia",
                    "url": article_link,
                }
            ],
            [
                {
                    "text": "🔎 Buscar más sobre Wooseok",
                    "url": google_search_url,
                }
            ],
        ]
    }

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": keyboard,
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if not payload.get("ok"):
        raise RuntimeError(
            f"Telegram rechazó el mensaje: {payload}"
        )


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
            raw_title = clean_title(
                entry.get("title", "Sin título")
            )

            link = entry.get("link", "").strip()

            if not link:
                continue

            title, source = split_title_and_source(raw_title)

            collected.append(
                {
                    "id": entry_id(entry),
                    "title": title,
                    "source": clean_source(source, link),
                    "link": link,
                    "date": parse_date(entry),
                    "search": search["label"],
                    "query": search["query"],
                }
            )

    collected.sort(key=lambda item: item["date"])

    return collected


def create_message(item: dict[str, Any]) -> str:
    date_text = item["date"].astimezone().strftime(
        "%d/%m/%Y • %I:%M %p"
    )

    title = escape_html(item["title"])
    source = escape_html(item["source"])
    search = escape_html(item["search"])

    return (
        "୨୧ ────── <b>NUEVA NOTICIA</b> ────── ୨୧\n\n"
        f"💗 <b>{title}</b>\n\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"🎀 <b>Fuente:</b> {source}\n"
        f"🌐 <b>Búsqueda:</b> {search}\n"
        f"🕰 <b>Fecha:</b> {date_text}\n"
        "┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        "<i>Wooseok News Bot ♡</i>"
    )


def main() -> int:
    validate_config()

    seen = load_seen()
    seen_set = set(seen)

    news = collect_news()

    new_items = [
        item
        for item in news
        if item["id"] not in seen_set
    ]

    new_items = new_items[-MAX_MESSAGES_PER_RUN:]

    if not new_items:
        print("No hay noticias nuevas.")
        return 0

    for item in new_items:
        message = create_message(item)

        send_telegram(
            message=message,
            article_link=item["link"],
            search_query='"Byeon Woo Seok" OR 변우석',
        )

        seen.append(item["id"])
        seen_set.add(item["id"])

        print(f"Enviada: {item['title']}")

    save_seen(seen)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
