#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import VK articles into a static GitHub Pages site.

Usage:
    python tools/import_vk.py
    python tools/import_vk.py --skip-media
    python tools/import_vk.py --skip-translate
    python tools/import_vk.py --verify-only
"""

from __future__ import annotations

import argparse
import hashlib
import html as htmlmod
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "img"
VIDEO_DIR = ROOT / "video"
DATA_DIR = ROOT / "data"
CACHE_PATH = DATA_DIR / "translations.json"
REPORT_PATH = DATA_DIR / "import-report.json"

ARTICLES = [
    ("brodilka-sverhu-rt", "https://vk.ru/@dreamkilled-brodilka-sverhu-rt"),
    ("brodilka-sverhu-tb", "https://vk.ru/@dreamkilled-brodilka-sverhu-tb"),
    ("brodilka-sboku", "https://vk.ru/@dreamkilled-brodilka-sboku"),
    ("ot-pervogo", "https://vk.ru/@dreamkilled-ot-pervogo"),
    ("brodilki-ot-3-lica", "https://vk.ru/@dreamkilled-brodilki-ot-3-lica"),
    ("golovolomki", "https://vk.ru/@dreamkilled-golovolomki"),
    ("kvesty", "https://vk.ru/@dreamkilled-kvesty"),
    ("guitar-hero", "https://vk.ru/@dreamkilled-guitar-hero"),
    ("sostavlenie-muzyki", "https://vk.ru/@dreamkilled-sostavlenie-muzyki"),
    ("phizika-pesochnica", "https://vk.ru/@dreamkilled-phizika-pesochnica"),
    ("zashita-bashnyami", "https://vk.ru/@dreamkilled-zashita-bashnyami"),
    ("stratezhki", "https://vk.ru/@dreamkilled-stratezhki"),
    ("gonki", "https://vk.ru/@dreamkilled-gonki"),
    ("letalki", "https://vk.ru/@dreamkilled-letalki"),
    ("novelly", "https://vk.ru/@dreamkilled-novelly"),
    ("zapusk-flash", "https://vk.ru/@dreamkilled-zapusk-flash"),
    ("poisk-indie", "https://vk.ru/@dreamkilled-poisk-indie"),
]

SLUGS = {slug for slug, _ in ARTICLES}
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)

PAGE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

MEDIA_HEADERS = {
    "User-Agent": UA,
    "Referer": "https://vk.ru/",
    "Accept": "*/*",
}

TRANS_URL = "https://clients5.google.com/translate_a/t"
ALLOWED_INLINE = {"a", "strong", "em", "b", "i", "u", "s", "br"}
DOT_LEADER_RE = re.compile(r"\s+(?:\.\s*){3,}")

SERIES_TITLE_RU = "Во что сыграть? 400 инди игр!"
SERIES_TITLE_EN = "What to Play? 400 Indie Games!"
SERIES_SUBTITLE_RU = (
    "Подборки разделены по жанрам. Не строго, но уже удобнее гигантского списка.",
    "Самые-самые в подборке отмечены ★.",
)
SERIES_SUBTITLE_EN = (
    "The collections are grouped by genre. Not strictly, but already more convenient than a giant list.",
    "The very best in each collection are marked with ★.",
)

ARTICLE_META = {
    "brodilka-sverhu-rt": {
        "title_ru": "Вид сверху. Бои в реальном времени.",
        "title_en": "Top-down. Real-time combat.",
        "excerpt_ru": "На обложке: Radio the Universe.",
        "excerpt_en": "Cover: Radio the Universe.",
    },
    "brodilka-sverhu-tb": {
        "title_ru": "Вид сверху. Пошаговые бои.",
        "title_en": "Top-down. Turn-based combat.",
        "excerpt_ru": "На обложке: Battle Brothers.",
        "excerpt_en": "Cover: Battle Brothers.",
    },
    "brodilka-sboku": {
        "title_ru": "Бродилки. Вид сбоку.",
        "title_en": "Side-scrolling action.",
        "excerpt_ru": "На обложке: Tail of Iron.",
        "excerpt_en": "Cover: Tail of Iron.",
    },
    "ot-pervogo": {
        "title_ru": "Вид из глаз.",
        "title_en": "First-person view.",
        "excerpt_ru": "На обложке: Super HOT.",
        "excerpt_en": "Cover: Super HOT.",
    },
    "brodilki-ot-3-lica": {
        "title_ru": "Бродилки от третьего лица.",
        "title_en": "Third-person exploration.",
        "excerpt_ru": "На обложке: Tiny and Big in: Grandpa's leftovers.",
        "excerpt_en": "Cover: Tiny and Big in: Grandpa's leftovers.",
    },
    "golovolomki": {
        "title_ru": "Головоломки.",
        "title_en": "Puzzles.",
        "excerpt_ru": "На обложке: FEZ.",
        "excerpt_en": "Cover: FEZ.",
    },
    "kvesty": {
        "title_ru": "Квесты.",
        "title_en": "Adventure games.",
        "excerpt_ru": "На обложке: Night in the Woods.",
        "excerpt_en": "Cover: Night in the Woods.",
    },
    "guitar-hero": {
        "title_ru": "Ритм.",
        "title_en": "Rhythm.",
        "excerpt_ru": "На обложке: Super Crazy Guitar Maniac Deluxe.",
        "excerpt_en": "Cover: Super Crazy Guitar Maniac Deluxe.",
    },
    "sostavlenie-muzyki": {
        "title_ru": "Составление музыки.",
        "title_en": "Music making.",
        "excerpt_ru": "На обложке: Incredibox.",
        "excerpt_en": "Cover: Incredibox.",
    },
    "phizika-pesochnica": {
        "title_ru": "Физические песочницы.",
        "title_en": "Physics sandboxes.",
        "excerpt_ru": "На обложке: Universe Sandbox.",
        "excerpt_en": "Cover: Universe Sandbox.",
    },
    "zashita-bashnyami": {
        "title_ru": "Защита башнями.",
        "title_en": "Tower defense.",
        "excerpt_ru": "На обложке: Kingdom Rush.",
        "excerpt_en": "Cover: Kingdom Rush.",
    },
    "stratezhki": {
        "title_ru": "Стратежки.",
        "title_en": "Strategy games.",
        "excerpt_ru": "На обложке: Starsector.",
        "excerpt_en": "Cover: Starsector.",
    },
    "gonki": {
        "title_ru": "Гонки.",
        "title_en": "Racing.",
        "excerpt_ru": "На обложке: Nitronic Rush.",
        "excerpt_en": "Cover: Nitronic Rush.",
    },
    "letalki": {
        "title_ru": "Леталки.",
        "title_en": "Flight games.",
        "excerpt_ru": "На обложке: Sky Rogue.",
        "excerpt_en": "Cover: Sky Rogue.",
    },
    "novelly": {
        "title_ru": "Новеллы.",
        "title_en": "Visual novels.",
        "excerpt_ru": "На обложке: Slay the Princess.",
        "excerpt_en": "Cover: Slay the Princess.",
    },
    "zapusk-flash": {
        "title_ru": "Запуск и поиск Flash игр.",
        "title_en": "Running and finding Flash games.",
        "excerpt_ru": "Сейчас запустить флешки трудно, но реально.",
        "excerpt_en": "Running Flash games is hard nowadays, but possible.",
    },
    "poisk-indie": {
        "title_ru": "Где искать инди игры?",
        "title_en": "Where to find indie games?",
        "excerpt_ru": "Ответы для тех, кто хочет поискать игры сам.",
        "excerpt_en": "Answers for those who want to find games on their own.",
    },
}

MONTHS = {
    "янв": "Jan",
    "фев": "Feb",
    "мар": "Mar",
    "апр": "Apr",
    "май": "May",
    "мая": "May",
    "июн": "Jun",
    "июл": "Jul",
    "авг": "Aug",
    "сен": "Sep",
    "окт": "Oct",
    "ноя": "Nov",
    "дек": "Dec",
}


def log(*args):
    print(*args, flush=True)


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", text or ""))


def esc(text: str) -> str:
    return htmlmod.escape(text or "", quote=True)


def strip_tags(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def truncate(text: str, limit: int = 180) -> str:
    text = normalize_space(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:—- ")
    return cut + "…"


def guess_ext(url: str, default: str = "jpg") -> str:
    path = urlparse(url).path.lower()
    for ext in ("jpg", "jpeg", "png", "webp", "gif", "mp4", "webm"):
        if path.endswith("." + ext):
            return "jpg" if ext == "jpeg" else ext
    if "/doc" in path:
        return "gif"
    return default


def fetch_html(url: str) -> tuple[str, str]:
    last_error = "unknown"
    candidates = [url]
    if "vk.ru" in url:
        candidates.append(url.replace("vk.ru", "vk.com"))
    if "vk.com" in url:
        candidates.append(url.replace("vk.com", "vk.ru"))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        for attempt in range(3):
            try:
                response = requests.get(
                    candidate, headers=PAGE_HEADERS, timeout=60
                )
                for encoding in ("cp1251", "utf-8"):
                    text = response.content.decode(encoding, errors="replace")
                    if "article_view" in text and "article_layer__content" in text:
                        return text, candidate
                last_error = f"HTTP {response.status_code}, article not found"
            except Exception as exc:  # noqa: BLE001
                last_error = repr(exc)
            time.sleep(1 + attempt)
    raise RuntimeError(f"cannot fetch {url}: {last_error}")


def normalize_href(href: str | None) -> str | None:
    if not href:
        return None
    href = htmlmod.unescape(href.strip())
    if not href or href.startswith("javascript:"):
        return None

    parsed = urlparse(href)
    path_lower = parsed.path.lower()
    if path_lower.endswith("/away.php") or path_lower.endswith("away.php"):
        target = parse_qs(parsed.query).get("to", [None])[0]
        if target:
            return normalize_href(unquote(target))

    vk_article = re.match(
        r"^(?:https?://)?(?:m\.)?vk\.(?:com|ru)/@([A-Za-z0-9_-]+)"
        r"(?:\?([^#]*))?/?$",
        href,
    )
    if vk_article:
        slug = vk_article.group(1)
        query = vk_article.group(2) or ""
        anchor = parse_qs(query).get("anchor", [None])[0]
        local_slug = (
            slug[len("dreamkilled-"):]
            if slug.startswith("dreamkilled-")
            else slug
        )
        if local_slug in SLUGS:
            return f"/ru/{local_slug}/" + (f"#{anchor}" if anchor else "")
        return f"https://vk.ru/@{slug}" + (f"?anchor={anchor}" if anchor else "")

    relative_article = re.match(
        r"^/@([A-Za-z0-9_-]+)(?:\?([^#]*))?$", href
    )
    if relative_article:
        slug = relative_article.group(1)
        query = relative_article.group(2) or ""
        anchor = parse_qs(query).get("anchor", [None])[0]
        local_slug = (
            slug[len("dreamkilled-"):]
            if slug.startswith("dreamkilled-")
            else slug
        )
        if local_slug in SLUGS:
            return f"/ru/{local_slug}/" + (f"#{anchor}" if anchor else "")
        return f"https://vk.ru/@{slug}" + (f"?anchor={anchor}" if anchor else "")

    if href.startswith("?anchor="):
        anchor = parse_qs(href[1:]).get("anchor", [None])[0]
        return f"#{anchor}" if anchor else None
    if href.startswith("#"):
        return href

    if href.startswith("/"):
        return "https://vk.ru" + href

    if parsed.scheme in ("http", "https", "mailto", "tel"):
        return href

    return href


def sanitize_inline(el):
    for comment in el.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for svg in el.find_all(["svg", "path"]):
        if svg.parent is not None:
            svg.decompose()
    for span in el.find_all("span"):
        if span.parent is None:
            continue
        if "article_anchor_button" in (span.get("class") or []):
            span.decompose()
        else:
            span.unwrap()

    for child in list(el.find_all(True)):
        if child.parent is None:
            continue
        name = child.name.lower()
        if name in ("svg", "path"):
            child.decompose()
            continue
        if name not in ALLOWED_INLINE:
            child.unwrap()
            continue
        if name == "a":
            new_href = normalize_href(child.get("href"))
            if not new_href:
                child.unwrap()
                continue
            attrs = {"href": new_href}
            if not new_href.startswith(("/", "#", "mailto:", "tel:")):
                attrs["target"] = "_blank"
                attrs["rel"] = "noopener noreferrer nofollow"
            child.attrs = attrs
        else:
            child.attrs = {}
    return el


def sanitize_inner(el) -> str:
    sanitize_inline(el)
    return "".join(str(child) for child in el.contents).strip()


def extract_heading(el) -> dict:
    anchor = el.find("span", class_="article_anchor_button")
    anchor_id = None
    if anchor is not None:
        anchor_id = anchor.get("id")
        anchor.decompose()
    for svg in el.find_all("svg"):
        svg.decompose()
    html_str = sanitize_inner(el)
    return {
        "type": el.name.lower(),
        "id": anchor_id or el.get("id"),
        "html": html_str,
    }


def photo_from_item(item) -> dict | None:
    candidates: list[tuple[int, int, str]] = []
    if isinstance(item, list):
        if item and isinstance(item[0], str):
            width = item[1] if len(item) > 1 and isinstance(item[1], int) else 0
            height = item[2] if len(item) > 2 and isinstance(item[2], int) else 0
            candidates.append((width, height, item[0]))
    elif isinstance(item, dict):
        for value in item.values():
            if not (isinstance(value, list) and value and isinstance(value[0], str)):
                continue
            url = value[0]
            width = 0
            height = 0
            if len(value) > 1 and isinstance(value[1], int):
                width = value[1]
            if len(value) > 2 and isinstance(value[2], int):
                height = value[2]
            match = re.search(r"[?&]cs=(\d+)x(\d+)", url)
            if match:
                width = int(match.group(1))
                height = int(match.group(2))
            candidates.append((width, height, url))

    if not candidates:
        return None
    candidates.sort(key=lambda value: (-value[0], -value[1]))
    urls: list[str] = []
    for _, _, url in candidates:
        if url not in urls:
            urls.append(url)
    width, height, primary = candidates[0]
    return {
        "urls": urls,
        "width": width,
        "height": height,
        "key": primary.split("?")[0],
    }


def caption_parts(value: str) -> tuple[str, str]:
    if not value:
        return "", ""
    fragment = BeautifulSoup(value, "html.parser")
    html_str = sanitize_inner(fragment)
    text = normalize_space(fragment.get_text(" ", strip=True))
    return html_str, text


def parse_figure(fig) -> dict | None:
    caption_el = fig.find("figcaption")
    caption_html = sanitize_inner(caption_el) if caption_el else ""
    caption_text = (
        normalize_space(caption_el.get_text(" ", strip=True))
        if caption_el
        else ""
    )
    captions: list[str] = []
    if caption_el is not None and caption_el.get("data-captions"):
        try:
            parsed = json.loads(caption_el.get("data-captions"))
            if isinstance(parsed, list):
                captions = [
                    value if isinstance(value, str) else ""
                    for value in parsed
                ]
        except Exception:  # noqa: BLE001
            captions = []

    video = fig.find("video")
    if video is not None:
        source = video.find("source")
        src = source.get("src") if source else video.get("src")
        if not src:
            return None
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = "https://vk.ru" + src
        poster = video.get("poster")
        if poster and poster.startswith("//"):
            poster = "https:" + poster
        return {
            "type": "video",
            "src": src,
            "poster": poster,
            "caption": caption_html,
            "caption_text": caption_text,
            "key": src,
        }

    sizes_el = fig.select_one("[data-sizes]")
    photos: list[dict] = []
    if sizes_el is not None:
        try:
            raw = sizes_el.get("data-sizes", "").replace("&quot;", '"')
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    photo = photo_from_item(item)
                    if photo:
                        photos.append(photo)
        except Exception:  # noqa: BLE001
            photos = []

    if photos:
        if captions:
            for index, photo in enumerate(photos):
                value = captions[index] if index < len(captions) else ""
                photo["caption"], photo["caption_text"] = caption_parts(value)
        else:
            photos[0]["caption"] = caption_html
            photos[0]["caption_text"] = caption_text
            for photo in photos[1:]:
                photo["caption"] = ""
                photo["caption_text"] = ""
        return {
            "type": "photos",
            "photos": photos,
            "caption": caption_html,
            "caption_text": caption_text,
        }

    img = fig.find("img")
    if img is not None and img.get("src"):
        src = img["src"]
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = "https://vk.ru" + src
        return {
            "type": "gif",
            "src": src,
            "caption": caption_html,
            "caption_text": caption_text,
            "key": src,
        }
    return None


def iter_blocks(container):
    for child in list(container.children):
        if getattr(child, "name", None) is None:
            continue
        name = child.name.lower()
        if name in ("h2", "h3", "p", "ul", "ol", "figure", "video", "blockquote"):
            yield child
        elif name == "div":
            nested = child.find_all(
                ["h2", "h3", "p", "ul", "ol", "figure", "video", "blockquote"],
                recursive=False,
            )
            if nested:
                yield from iter_blocks(child)
            else:
                yield child


def parse_article(slug: str, url: str, order: int) -> dict:
    source_html, used_url = fetch_html(url)
    soup = BeautifulSoup(source_html, "html.parser")
    body = soup.select_one(".article_view")
    if body is None:
        raise RuntimeError(f"article body not found: {url}")

    title_el = body.find("h1")
    if title_el is not None:
        for span in title_el.find_all("span", class_="article_anchor_button"):
            span.decompose()
        title_ru = normalize_space(title_el.get_text(" ", strip=True))
    else:
        title_ru = normalize_space(
            (soup.select_one('meta[property="og:title"]') or {}).get("content", "")
        )

    date_el = soup.select_one(".article_layer__header_date_published")
    date_ru = normalize_space(date_el.get_text(" ", strip=True)) if date_el else ""

    og_el = soup.select_one('meta[property="og:image"]')
    og_image = og_el.get("content") if og_el else ""
    if og_image.startswith("http://"):
        og_image = "https://" + og_image[7:]

    match = re.search(r"\((?:ч|№)\s*(\d+)\)", title_ru, re.IGNORECASE)
    part = int(match.group(1)) if match else order

    blocks: list[dict] = []
    cover: dict | None = None

    for el in iter_blocks(body):
        name = el.name.lower()
        if name in ("h2", "h3"):
            blocks.append(extract_heading(el))
        elif name == "p":
            html_str = sanitize_inner(el)
            if html_str:
                blocks.append({"type": "p", "html": html_str})
        elif name in ("ul", "ol"):
            items = []
            for li in el.find_all("li", recursive=False):
                item_html = sanitize_inner(li)
                if item_html:
                    items.append(item_html)
            if items:
                blocks.append({"type": "list", "tag": name, "items": items})
        elif name == "blockquote":
            html_str = sanitize_inner(el)
            if html_str:
                blocks.append({"type": "blockquote", "html": html_str})
        elif name == "figure":
            media = parse_figure(el)
            if media:
                if cover is None and media["type"] in ("gif", "video"):
                    cover = media
                    cover["kind"] = "cover"
                blocks.append(media)
        elif name == "video":
            source = el.find("source")
            src = source.get("src") if source else el.get("src")
            if src:
                if src.startswith("/"):
                    src = "https://vk.ru" + src
                poster = el.get("poster")
                if poster and poster.startswith("//"):
                    poster = "https:" + poster
                media = {
                    "type": "video",
                    "src": src,
                    "poster": poster,
                    "caption": "",
                    "caption_text": "",
                    "key": src,
                }
                if cover is None:
                    cover = media
                    cover["kind"] = "cover"
                blocks.append(media)
        elif name == "div":
            html_str = sanitize_inner(el)
            if html_str:
                blocks.append({"type": "p", "html": html_str})

    generic_excerpt_markers = (
        "Список инди игр",
        "Приятного ознакомления",
        "Запихнуть",
        "серия статей",
        "Ссылки на другие части",
        "Ссылки на статьи",
    )
    excerpt_ru = ""
    fallback_excerpt = ""
    for block in blocks:
        if block["type"] != "p":
            continue
        text = strip_tags(block["html"])
        letters = len(re.findall(r"[0-9A-Za-zА-Яа-яЁё]", text))
        if len(text) < 15 or letters < 12 or " " not in text.strip():
            continue
        if not fallback_excerpt:
            fallback_excerpt = text
        if any(
            marker.lower() in text.lower()
            for marker in generic_excerpt_markers
        ):
            continue
        excerpt_ru = text
        break
    if not excerpt_ru:
        excerpt_ru = fallback_excerpt
    if not excerpt_ru:
        excerpt_ru = "Подборка инди-игр с описаниями и скриншотами."
    excerpt_ru = truncate(excerpt_ru, 180)

    meta = ARTICLE_META.get(slug)
    if meta:
        title_ru = meta["title_ru"]
        title_en = meta["title_en"]
        excerpt_ru = meta["excerpt_ru"]
        excerpt_en = meta["excerpt_en"]
    else:
        title_en = (
            f"{SERIES_TITLE_EN} (Part {part})"
            if match
            else title_ru
        )
        excerpt_en = ""

    return {
        "slug": slug,
        "url": url,
        "used_url": used_url,
        "order": order,
        "part": part,
        "title_ru": title_ru,
        "title_en": title_en,
        "date_ru": date_ru,
        "date_en": translate_date(date_ru),
        "date_iso": date_iso(date_ru),
        "og_image": og_image,
        "cover": cover,
        "blocks": blocks,
        "excerpt_ru": excerpt_ru,
        "excerpt_en": excerpt_en,
        "thumb_key": f"thumb:{slug}",
    }


def translate_date(date_ru: str) -> str:
    match = re.search(r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})", date_ru)
    if not match:
        return date_ru
    day, month, year = match.groups()
    month_en = MONTHS.get(month.lower(), month)
    return f"{day} {month_en} {year}"


def date_iso(date_ru: str) -> str:
    match = re.search(r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})", date_ru)
    if not match:
        return ""
    day, month, year = match.groups()
    month_en = MONTHS.get(month.lower())
    order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    if month_en not in order:
        return ""
    return f"{int(year):04d}-{order.index(month_en) + 1:02d}-{int(day):02d}"


# ---------------------------------------------------------------------------
# Media collection / download
# ---------------------------------------------------------------------------


def media_tasks(articles: list[dict]) -> tuple[list[dict], dict[str, str]]:
    tasks: list[dict] = []
    mapping: dict[str, str] = {}

    def add(key: str, urls: list[str], dest: Path, kind: str):
        urls = [url for url in (urls or []) if url]
        if not key or not urls or key in mapping:
            return
        mapping[key] = dest.relative_to(ROOT).as_posix()
        tasks.append({"key": key, "urls": urls, "dest": dest, "kind": kind})

    for article in articles:
        slug = article["slug"]
        order = article["order"]

        thumb_urls = []
        if article.get("og_image"):
            thumb_urls.append(article["og_image"])
        add(
            article["thumb_key"],
            thumb_urls,
            IMG_DIR / slug / "thumb.jpg",
            "image",
        )

        cover = article.get("cover")
        if cover:
            if cover["type"] == "gif":
                add(
                    cover["key"],
                    [cover["src"]],
                    IMG_DIR / slug / "cover.gif",
                    "image",
                )
            elif cover["type"] == "video":
                add(
                    cover["key"],
                    [cover["src"]],
                    VIDEO_DIR / slug / "cover.mp4",
                    "video",
                )
                if cover.get("poster"):
                    add(
                        cover["key"] + ":poster",
                        [cover["poster"]],
                        IMG_DIR / slug / "cover-poster.jpg",
                        "image",
                    )

        media_number = 0
        for block in article["blocks"]:
            if block["type"] == "photos":
                for photo in block["photos"]:
                    media_number += 1
                    ext = guess_ext(photo["urls"][0])
                    add(
                        photo["key"],
                        photo["urls"],
                        IMG_DIR / slug / f"{order:02d}-{media_number:02d}.{ext}",
                        "image",
                    )
            elif block["type"] == "gif":
                media_number += 1
                ext = guess_ext(block["src"], default="gif")
                add(
                    block["key"],
                    [block["src"]],
                    IMG_DIR / slug / f"{order:02d}-{media_number:02d}.{ext}",
                    "image",
                )
            elif block["type"] == "video":
                media_number += 1
                add(
                    block["key"],
                    [block["src"]],
                    VIDEO_DIR / slug / f"{order:02d}-{media_number:02d}.mp4",
                    "video",
                )
                if block.get("poster"):
                    add(
                        block["key"] + ":poster",
                        [block["poster"]],
                        IMG_DIR / slug / f"{order:02d}-{media_number:02d}-poster.jpg",
                        "image",
                    )

    return tasks, mapping


def valid_media_bytes(data: bytes, kind: str, content_type: str) -> bool:
    content_type = (content_type or "").lower()
    if "text/html" in content_type or "application/json" in content_type:
        return False
    if kind == "video":
        if content_type.startswith("video/"):
            return True
        return b"ftyp" in data[:32] or data[:4] == b"\x1a\x45\xdf\xa3"
    if content_type.startswith("image/"):
        return True
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return False


def download_one(task: dict) -> tuple[str, str] | None:
    dest: Path = task["dest"]
    if dest.exists() and dest.stat().st_size > 0:
        return None

    ensure_dir(dest.parent)
    last_error = ""
    for url in task["urls"]:
        for attempt in range(3):
            try:
                response = requests.get(
                    url,
                    headers=MEDIA_HEADERS,
                    timeout=90,
                    stream=True,
                )
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}"
                    time.sleep(0.5 * (attempt + 1))
                    continue
                content_type = response.headers.get("content-type", "")
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as handle:
                    for chunk in response.iter_content(65536):
                        if chunk:
                            handle.write(chunk)
                head = tmp.read_bytes()[:64]
                if not head or not valid_media_bytes(head, task["kind"], content_type):
                    tmp.unlink(missing_ok=True)
                    last_error = f"invalid media ({content_type})"
                    time.sleep(0.5 * (attempt + 1))
                    continue
                tmp.replace(dest)
                return None
            except Exception as exc:  # noqa: BLE001
                last_error = repr(exc)
                time.sleep(0.5 * (attempt + 1))
    return task["key"], last_error


def download_media(tasks: list[dict], workers: int = 8) -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    if not tasks:
        return failures
    log(f"downloading {len(tasks)} media files...")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_one, task): task for task in tasks}
        for index, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result:
                failures.append(result)
            if index % 25 == 0 or index == len(tasks):
                log(f"  media {index}/{len(tasks)}")
    return failures


def resolve_media(articles: list[dict], mapping: dict[str, str]):
    def path_for(key: str | None):
        return mapping.get(key) if key else None

    for article in articles:
        article["thumb_path"] = path_for(article["thumb_key"])
        cover = article.get("cover")
        if cover:
            if cover["type"] == "gif":
                cover["path"] = path_for(cover["key"])
            elif cover["type"] == "video":
                cover["path"] = path_for(cover["key"])
                cover["poster_path"] = path_for(cover["key"] + ":poster")
        for block in article["blocks"]:
            if block["type"] == "photos":
                for photo in block["photos"]:
                    photo["path"] = path_for(photo["key"])
            elif block["type"] == "gif":
                block["path"] = path_for(block["key"])
            elif block["type"] == "video":
                block["path"] = path_for(block["key"])
                block["poster_path"] = path_for(block["key"] + ":poster")

        if not article["thumb_path"]:
            for block in article["blocks"]:
                if block["type"] == "photos":
                    for photo in block["photos"]:
                        if photo.get("path"):
                            article["thumb_path"] = photo["path"]
                            break
                if article["thumb_path"]:
                    break
                if block["type"] == "gif" and block.get("path"):
                    article["thumb_path"] = block["path"]
                    break
                if block["type"] == "video" and block.get("poster_path"):
                    article["thumb_path"] = block["poster_path"]
                    break
        if not article["thumb_path"] and cover:
            if cover.get("poster_path"):
                article["thumb_path"] = cover["poster_path"]
            elif cover.get("path") and cover["type"] != "video":
                article["thumb_path"] = cover["path"]


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_cache(cache: dict):
    ensure_dir(DATA_DIR)
    tmp = CACHE_PATH.with_suffix(".json.part")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(CACHE_PATH)


def cache_get(cache: dict, source: str) -> str | None:
    item = cache.get(sha1(source))
    if isinstance(item, dict):
        return item.get("en")
    return None


def cache_set(cache: dict, source: str, translation: str):
    cache[sha1(source)] = {"src": source, "en": translation}


def translate_batch(session: requests.Session, texts: list[str]) -> list[str]:
    params = [
        ("client", "dict-chrome-ex"),
        ("sl", "ru"),
        ("tl", "en"),
    ] + [("q", text) for text in texts]

    last_error = "unknown"
    for attempt in range(4):
        try:
            response = session.get(
                TRANS_URL,
                params=params,
                headers={"User-Agent": UA},
                timeout=90,
            )
            if response.status_code == 429:
                last_error = "HTTP 429"
                time.sleep(5 * (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            if isinstance(data, str):
                data = [data]
            if not isinstance(data, list) or len(data) != len(texts):
                raise ValueError(
                    f"unexpected translation response: {type(data).__name__}"
                )
            result = []
            for item in data:
                if isinstance(item, list):
                    item = item[0] if item and isinstance(item[0], str) else ""
                result.append(item if isinstance(item, str) else "")
            return result
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(last_error)


def tag_signature(html_str: str) -> list[str]:
    soup = BeautifulSoup(html_str, "html.parser")
    return [
        tag.name
        for tag in soup.find_all(["a", "strong", "em", "b", "i", "br"])
    ]


def restore_links(source: str, translation: str) -> str:
    source_soup = BeautifulSoup(source, "html.parser")
    result_soup = BeautifulSoup(translation, "html.parser")
    source_links = source_soup.find_all("a")
    result_links = result_soup.find_all("a")
    if len(source_links) != len(result_links):
        return translation
    for original, translated in zip(source_links, result_links):
        if original.get("href"):
            translated["href"] = original["href"]
        for attribute in ("rel", "target", "title"):
            if original.get(attribute) and not translated.get(attribute):
                translated[attribute] = original[attribute]
    return str(result_soup)


def collect_translation_sources(articles: list[dict]) -> set[str]:
    sources: set[str] = set()

    def add(value: str):
        if value and has_cyrillic(value) and value.strip():
            sources.add(value)

    for article in articles:
        if not article.get("excerpt_en"):
            add(article["excerpt_ru"])
        cover = article.get("cover")
        if cover:
            add(cover.get("caption", ""))
        for block in article["blocks"]:
            if block["type"] in ("p", "h2", "h3", "blockquote"):
                add(block["html"])
            elif block["type"] == "list":
                for item in block["items"]:
                    add(item)
            elif block["type"] == "photos":
                for photo in block.get("photos", []):
                    add(photo.get("caption", ""))
            elif block["type"] in ("gif", "video"):
                add(block.get("caption", ""))
    return sources


def translate_all(
    articles: list[dict], skip_translate: bool = False
) -> list[tuple[str, str]]:
    cache = load_cache()
    sources = collect_translation_sources(articles)
    missing = [
        source
        for source in sources
        if cache_get(cache, source) is None
    ]
    missing.sort()
    log(f"translation sources: {len(sources)}, missing: {len(missing)}")

    failures: list[tuple[str, str]] = []
    if skip_translate or not missing:
        return failures

    batches: list[list[str]] = []
    batch: list[str] = []
    chars = 0
    for source in missing:
        if batch and (chars + len(source) > 3500 or len(batch) >= 25):
            batches.append(batch)
            batch = []
            chars = 0
        batch.append(source)
        chars += len(source) + 1
    if batch:
        batches.append(batch)

    session = requests.Session()
    for index, current_batch in enumerate(batches, 1):
        try:
            translations = translate_batch(session, current_batch)
            for source, translation in zip(current_batch, translations):
                if tag_signature(source) != tag_signature(translation):
                    failures.append((source, "tag structure changed"))
                    continue
                cache_set(cache, source, restore_links(source, translation))
            save_cache(cache)
            log(f"  translate {index}/{len(batches)} ({len(current_batch)} blocks)")
        except Exception as exc:  # noqa: BLE001
            log(f"  batch {index} failed: {exc}")
            for source in current_batch:
                try:
                    translation = translate_batch(session, [source])[0]
                    if tag_signature(source) != tag_signature(translation):
                        failures.append((source, "tag structure changed"))
                        continue
                    cache_set(cache, source, restore_links(source, translation))
                except Exception as inner:  # noqa: BLE001
                    failures.append((source, repr(inner)))
            save_cache(cache)
        time.sleep(0.25)
    return failures


def tr_html(value: str, cache: dict, lang: str) -> str:
    if lang != "en" or not value:
        return value
    translation = cache_get(cache, value)
    if not translation:
        return value
    translation = translation.replace('href="/ru/', 'href="/en/')
    translation = translation.replace("href='/ru/", "href='/en/")
    return translation


def tr_plain(value: str, cache: dict, lang: str) -> str:
    if lang != "en" or not value:
        return value
    translation = cache_get(cache, value)
    if not translation:
        return value
    return normalize_space(strip_tags(translation))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def url_path(relative: str | None) -> str | None:
    if not relative:
        return None
    return "/" + relative.lstrip("/")


def render_caption(
    html_str: str,
    plain_text: str,
    cache: dict,
    lang: str,
    *,
    class_name: str = "",
) -> str:
    if not html_str:
        return ""
    rendered = tr_html(html_str, cache, lang)
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<figcaption{class_attr}>{rendered}</figcaption>"


def media_caption_plain(
    block: dict, article: dict, cache: dict, lang: str
) -> str:
    caption_html = block.get("caption", "")
    value = ""
    if caption_html:
        value = normalize_space(strip_tags(tr_html(caption_html, cache, lang)))
    if not value:
        value = tr_plain(block.get("caption_text", ""), cache, lang)
    if lang == "en" and has_cyrillic(value):
        value = ""
    if not value:
        value = article["title_en"] if lang == "en" else article["title_ru"]
    return value


def photo_caption(
    photo: dict, cache: dict, lang: str
) -> tuple[str, str]:
    caption_html = photo.get("caption", "")
    caption_text = photo.get("caption_text", "")
    if caption_html:
        rendered = tr_html(caption_html, cache, lang)
        plain = normalize_space(strip_tags(rendered))
    elif caption_text:
        plain = tr_plain(caption_text, cache, lang)
        rendered = esc(plain)
    else:
        return "", ""
    if lang == "en" and has_cyrillic(plain):
        return "", ""
    return rendered, plain


def render_photos(
    block: dict, article: dict, cache: dict, lang: str
) -> str:
    fallback_alt = article["title_en"] if lang == "en" else article["title_ru"]
    slides = []
    slide_captions: list[tuple[str, str]] = []
    for photo in block["photos"]:
        path = url_path(photo.get("path"))
        if not path:
            continue
        width = photo.get("width") or ""
        height = photo.get("height") or ""
        size_attrs = ""
        if width and height:
            size_attrs = f' width="{width}" height="{height}"'
        caption_html, caption_plain = photo_caption(photo, cache, lang)
        alt = esc(truncate(caption_plain or fallback_alt, 120))
        slides.append(
            '<button type="button" class="photo-button carousel__slide"'
            f' data-full="{esc(path)}" data-caption="{esc(caption_plain)}"'
            f' data-caption-html="{esc(caption_html)}"'
            f' aria-label="{alt}">'
            f'<img src="{esc(path)}"{size_attrs} alt="{alt}"'
            ' loading="lazy" decoding="async">'
            "</button>"
        )
        slide_captions.append((caption_html, caption_plain))

    if not slides:
        unavailable = "Photo unavailable." if lang == "en" else "Фото недоступно."
        open_label = "Open on VK" if lang == "en" else "Открыть в VK"
        return (
            f'<div class="media-missing">{unavailable} '
            f'<a href="{esc(article["url"])}" target="_blank" '
            f'rel="noopener noreferrer">{open_label}</a></div>'
        )

    if len(slides) == 1:
        caption_html, caption_plain = slide_captions[0]
        caption = (
            f"<figcaption>{caption_html}</figcaption>"
            if caption_plain
            else ""
        )
        return f'<figure class="article-figure">{slides[0]}{caption}</figure>'

    first = block["photos"][0]
    aspect = ""
    if first.get("width") and first.get("height"):
        aspect = (
            f' style="--aspect: {int(first["width"])} / {int(first["height"])}"'
        )
    first_html, first_plain = slide_captions[0]
    hidden = "" if first_plain else " hidden"
    caption = (
        f'<figcaption class="carousel__caption"{hidden}>'
        f"{first_html}</figcaption>"
    )
    prev_label = "Previous photo" if lang == "en" else "Предыдущее фото"
    next_label = "Next photo" if lang == "en" else "Следующее фото"
    return (
        '<figure class="article-figure article-figure--carousel">'
        '<div class="carousel">'
        f'<div class="carousel__viewport"{aspect}>'
        '<div class="carousel__track">'
        + "".join(slides)
        + "</div></div>"
        '<button type="button" class="carousel__arrow carousel__arrow--prev"'
        f' aria-label="{prev_label}">&#8249;</button>'
        '<button type="button" class="carousel__arrow carousel__arrow--next"'
        f' aria-label="{next_label}">&#8250;</button>'
        f'<div class="carousel__counter">1/{len(slides)}</div>'
        "</div>"
        f"{caption}"
        "</figure>"
    )


def render_gif(
    block: dict, article: dict, cache: dict, lang: str, *, intro: bool = False
) -> str:
    path = url_path(block.get("path"))
    figure_class = "article-figure article-figure--gif"
    if intro:
        figure_class += " article-intro__figure"
    caption = render_caption(
        block.get("caption", ""),
        block.get("caption_text", ""),
        cache,
        lang,
    )
    if not path:
        unavailable = "Media unavailable." if lang == "en" else "Медиа недоступно."
        open_label = "Open on VK" if lang == "en" else "Открыть в VK"
        return (
            f'<div class="media-missing">{unavailable} '
            f'<a href="{esc(article["url"])}" target="_blank" '
            f'rel="noopener noreferrer">{open_label}</a></div>'
        )
    alt = esc(truncate(media_caption_plain(block, article, cache, lang), 120))
    return (
        f'<figure class="{figure_class}">'
        f'<a href="{esc(path)}" target="_blank" rel="noopener noreferrer">'
        f'<img src="{esc(path)}" alt="{alt}" loading="lazy" decoding="async">'
        "</a>"
        f"{caption}"
        "</figure>"
    )


def render_video(
    block: dict, article: dict, cache: dict, lang: str, *, intro: bool = False
) -> str:
    path = url_path(block.get("path"))
    poster = url_path(block.get("poster_path"))
    figure_class = "article-figure article-figure--video"
    if intro:
        figure_class += " article-intro__figure"
    caption = render_caption(
        block.get("caption", ""),
        block.get("caption_text", ""),
        cache,
        lang,
    )
    if not path:
        if poster:
            watch_label = (
                "Watch video on VK" if lang == "en" else "Смотреть видео на VK"
            )
            return (
                f'<figure class="{figure_class}">'
                f'<img src="{esc(poster)}" alt="" loading="lazy">'
                '<p class="media-missing">'
                f'<a href="{esc(article["url"])}" target="_blank" '
                f'rel="noopener noreferrer">{watch_label}</a></p>'
                f"{caption}</figure>"
            )
        unavailable = "Video unavailable." if lang == "en" else "Видео недоступно."
        open_label = "Open on VK" if lang == "en" else "Открыть в VK"
        return (
            f'<div class="media-missing">{unavailable} '
            f'<a href="{esc(article["url"])}" target="_blank" '
            f'rel="noopener noreferrer">{open_label}</a></div>'
        )
    poster_attr = f' poster="{esc(poster)}"' if poster else ""
    return (
        f'<figure class="{figure_class}">'
        '<video autoplay loop muted playsinline preload="metadata"'
        f"{poster_attr}>"
        f'<source src="{esc(path)}" type="video/mp4">'
        "</video>"
        f"{caption}"
        "</figure>"
    )


def render_cover(article: dict, cache: dict, lang: str) -> str:
    cover = article.get("cover")
    title = article["title_ru"] if lang == "ru" else article["title_en"]
    if cover:
        if cover["type"] == "gif":
            path = url_path(cover.get("path"))
            if path:
                caption = render_caption(
                    cover.get("caption", ""),
                    cover.get("caption_text", ""),
                    cache,
                    lang,
                )
                return (
                    '<figure class="article-cover">'
                    f'<img src="{esc(path)}" alt="{esc(title)}"'
                    ' decoding="async">'
                    f"{caption}</figure>"
                )
        elif cover["type"] == "video":
            path = url_path(cover.get("path"))
            poster = url_path(cover.get("poster_path"))
            if path:
                poster_attr = f' poster="{esc(poster)}"' if poster else ""
                caption = render_caption(
                    cover.get("caption", ""),
                    cover.get("caption_text", ""),
                    cache,
                    lang,
                )
                return (
                    '<figure class="article-cover article-cover--video">'
                    '<video autoplay loop muted playsinline preload="metadata"'
                    f"{poster_attr}>"
                    f'<source src="{esc(path)}" type="video/mp4">'
                    "</video>"
                    f"{caption}</figure>"
                )
    thumb = url_path(article.get("thumb_path"))
    if thumb:
        return (
            '<figure class="article-cover">'
            f'<img src="{esc(thumb)}" alt="{esc(title)}" loading="lazy"></figure>'
        )
    return ""


def render_toc_list(block: dict, cache: dict, lang: str) -> str:
    items = []
    for item_html in block["items"]:
        rendered = tr_html(item_html, cache, lang)
        soup = BeautifulSoup(rendered, "html.parser")
        link = soup.find("a")
        action_html = ""
        if link is not None:
            action_html = str(link)
            link.extract()
        for node in soup.find_all(string=True):
            text = str(node)
            if DOT_LEADER_RE.search(text):
                node.replace_with(DOT_LEADER_RE.sub(" ", text))
        title = normalize_space(soup.get_text(" ", strip=True))
        if not action_html:
            marker = title.find("→")
            if marker >= 0:
                action_html = esc(title[marker:].strip())
                title = title[:marker].strip()
        if not title:
            title = normalize_space(strip_tags(rendered))
        items.append(
            '<li class="toc__item">'
            f'<span class="toc__title">{esc(title)}</span>'
            '<span class="toc__leader" aria-hidden="true"></span>'
            f'<span class="toc__action">{action_html}</span>'
            "</li>"
        )
    return f'<ul class="toc">{"".join(items)}</ul>'


def render_block(block: dict, article: dict, cache: dict, lang: str) -> str:
    block_type = block["type"]
    if block_type == "p":
        return f"<p>{tr_html(block['html'], cache, lang)}</p>"
    if block_type in ("h2", "h3"):
        heading_id = block.get("id")
        id_attr = f' id="{esc(heading_id)}"' if heading_id else ""
        return (
            f"<{block_type}{id_attr}>"
            f"{tr_html(block['html'], cache, lang)}"
            f"</{block_type}>"
        )
    if block_type == "blockquote":
        return f"<blockquote>{tr_html(block['html'], cache, lang)}</blockquote>"
    if block_type == "list":
        if any(DOT_LEADER_RE.search(item) for item in block["items"]):
            return render_toc_list(block, cache, lang)
        items = "".join(
            f"<li>{tr_html(item, cache, lang)}</li>" for item in block["items"]
        )
        return f"<{block['tag']}>{items}</{block['tag']}>"
    if block_type == "photos":
        return render_photos(block, article, cache, lang)
    if block_type == "gif":
        return render_gif(block, article, cache, lang)
    if block_type == "video":
        return render_video(block, article, cache, lang)
    return ""


def is_decorative_separator(block: dict) -> bool:
    if block.get("type") != "p":
        return False
    text = strip_tags(block.get("html", ""))
    return (
        len(text) >= 40
        and text.count("•") >= 6
        and ("/" in text or "\\" in text)
    )


def intro_layout(article: dict) -> tuple[int, int] | None:
    blocks = article.get("blocks", [])
    cover_index = next(
        (i for i, block in enumerate(blocks) if block.get("kind") == "cover"),
        None,
    )
    if cover_index is None:
        return None
    for end_index in range(cover_index + 1, len(blocks)):
        if is_decorative_separator(blocks[end_index]):
            if end_index > cover_index + 1:
                return cover_index, end_index
            return None
    return None


def render_article_body(article: dict, cache: dict, lang: str) -> str:
    blocks = article["blocks"]
    layout = intro_layout(article)
    if layout is None:
        return "\n".join(
            render_block(block, article, cache, lang) for block in blocks
        )

    cover_index, end_index = layout
    cover = blocks[cover_index]
    if cover["type"] == "gif":
        cover_html = render_gif(cover, article, cache, lang, intro=True)
    elif cover["type"] == "video":
        cover_html = render_video(cover, article, cache, lang, intro=True)
    else:
        cover_html = render_block(cover, article, cache, lang)
    intro_text = "\n".join(
        render_block(block, article, cache, lang)
        for block in blocks[cover_index + 1 : end_index]
    )

    parts = [
        render_block(block, article, cache, lang)
        for block in blocks[:cover_index]
    ]
    parts.append(
        '<div class="article-intro">'
        f'<div class="article-intro__media">{cover_html}</div>'
        f'<div class="article-intro__text">{intro_text}</div>'
        "</div>"
    )
    tail_blocks = blocks[end_index:]
    has_lead_games = any(block["type"] == "h3" for block in tail_blocks)
    seen_first_game = False
    for block in tail_blocks:
        if block["type"] == "h3":
            seen_first_game = True
        elif (
            has_lead_games
            and not seen_first_game
            and block["type"] == "h2"
        ):
            continue
        parts.append(render_block(block, article, cache, lang))

    return "\n".join(part for part in parts if part)


def lightbox_markup(lang: str) -> str:
    if lang == "en":
        close_label = "Close"
        prev_label = "Previous photo"
        next_label = "Next photo"
        dialog_label = "Photo viewer"
    else:
        close_label = "Закрыть"
        prev_label = "Предыдущее фото"
        next_label = "Следующее фото"
        dialog_label = "Просмотр фото"
    return (
        '<div class="lightbox" id="lightbox" aria-hidden="true" role="dialog" '
        f'aria-modal="true" aria-label="{dialog_label}">'
        f'<button type="button" class="lightbox__close" aria-label="{close_label}">'
        "&times;</button>"
        f'<button type="button" class="lightbox__arrow lightbox__arrow--prev" '
        f'aria-label="{prev_label}">&#8249;</button>'
        '<img class="lightbox__image" alt="">'
        f'<button type="button" class="lightbox__arrow lightbox__arrow--next" '
        f'aria-label="{next_label}">&#8250;</button>'
        '<div class="lightbox__counter"></div>'
        '<div class="lightbox__caption"></div>'
        "</div>"
    )


def topbar(lang: str, href: str, switch_href: str) -> str:
    home = f"/{lang}/"
    brand_label = "Все статьи" if lang == "ru" else "All articles"
    switch_label = "EN" if lang == "ru" else "RU"
    switch_lang = "en" if lang == "ru" else "ru"
    return (
        '<header class="topbar"><div class="topbar__inner">'
        f'<a class="brand" href="{home}">{brand_label}</a>'
        '<nav class="lang-switch">'
        f'<a href="{esc(switch_href)}" hreflang="{switch_lang}">{switch_label}</a>'
        "</nav></div></header>"
    )


def footer(lang: str) -> str:
    if lang == "en":
        text = "Micro-reviews of indie games."
    else:
        text = "Микро-обзоры инди-игр."
    return (
        '<footer class="footer"><div class="footer__inner">'
        f"<span>{esc(text)}</span>"
        f'<a href="/{lang}/">{ "All articles" if lang == "en" else "Все статьи" }</a>'
        "</div></footer>"
    )


def head(
    lang: str,
    title: str,
    description: str,
    og_image: str | None = None,
) -> str:
    image_tag = ""
    if og_image:
        image_tag = f'<meta property="og:image" content="{esc(og_image)}">'
    locale = "ru_RU" if lang == "ru" else "en_US"
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="dark">\n'
        '<meta name="theme-color" content="#141414">\n'
        f"<title>{esc(title)}</title>\n"
        f'<meta name="description" content="{esc(description)}">\n'
        f'<meta property="og:title" content="{esc(title)}">\n'
        f'<meta property="og:description" content="{esc(description)}">\n'
        '<meta property="og:type" content="website">\n'
        f'<meta property="og:locale" content="{locale}">\n'
        f"{image_tag}\n"
        '<link rel="stylesheet" href="/style.css">\n'
        "</head>\n"
    )


def render_article(
    article: dict,
    articles: list[dict],
    cache: dict,
    lang: str,
) -> str:
    index = articles.index(article)
    prev_article = articles[index - 1] if index > 0 else None
    next_article = articles[index + 1] if index < len(articles) - 1 else None

    title = article["title_ru"] if lang == "ru" else article["title_en"]
    excerpt = article["excerpt_ru"]
    if lang == "en":
        excerpt = article.get("excerpt_en") or tr_plain(
            article["excerpt_ru"], cache, lang
        )
    description = truncate(f"{title} {excerpt}", 180)

    body = render_article_body(article, cache, lang)

    switch_href = f"/{'en' if lang == 'ru' else 'ru'}/{article['slug']}/"
    source_prefix = "Оригинал на " if lang == "ru" else "Original on "
    prev_label = "Предыдущая" if lang == "ru" else "Previous"
    next_label = "Следующая" if lang == "ru" else "Next"

    nav_parts = []
    if prev_article:
        prev_title = (
            prev_article["title_ru"]
            if lang == "ru"
            else prev_article["title_en"]
        )
        nav_parts.append(
            f'<a class="article-nav__link article-nav__link--prev" '
            f'href="/{lang}/{prev_article["slug"]}/">'
            f'<span>{prev_label}</span>{esc(prev_title)}</a>'
        )
    else:
        nav_parts.append("<span></span>")
    if next_article:
        next_title = (
            next_article["title_ru"]
            if lang == "ru"
            else next_article["title_en"]
        )
        nav_parts.append(
            f'<a class="article-nav__link article-nav__link--next" '
            f'href="/{lang}/{next_article["slug"]}/">'
            f'<span>{next_label}</span>{esc(next_title)}</a>'
        )
    else:
        nav_parts.append("<span></span>")

    nav_content = "".join(nav_parts)
    top_nav = (
        '<nav class="article-nav article-nav--top">'
        f"{nav_content}"
        "</nav>\n"
    )
    bottom_nav = (
        '<nav class="article-nav">'
        f"{nav_content}"
        "</nav>\n"
    )

    thumb = url_path(article.get("thumb_path"))
    og_image = thumb or None

    return (
        head(lang, f"{title} — Dreamkilled", description, og_image)
        + f"<body>\n{topbar(lang, f'/{lang}/', switch_href)}\n"
        + '<main class="container">\n'
        + top_nav
        + '<article class="article">\n'
        + f'<h1 class="article__title">{esc(title)}</h1>\n'
        + f'\n<div class="article__body">\n{body}\n'
        + f'<p class="article__source">{source_prefix}'
        + f'<a href="{esc(article["url"])}" target="_blank" '
        + 'rel="noopener noreferrer">VK</a></p>\n'
        + "</div>\n"
        + "</article>\n"
        + bottom_nav
        + "</main>\n"
        + footer(lang)
        + "\n"
        + lightbox_markup(lang)
        + '\n<script src="/script.js" defer></script>\n</body>\n</html>\n'
    )


def render_card(article: dict, cache: dict, lang: str) -> str:
    title = article["title_ru"] if lang == "ru" else article["title_en"]
    excerpt = article["excerpt_ru"]
    if lang == "en":
        excerpt = article.get("excerpt_en") or tr_plain(
            article["excerpt_ru"], cache, lang
        )
    excerpt = truncate(excerpt, 170)
    part_label = f"Часть {article['part']}" if lang == "ru" else f"Part {article['part']}"
    thumb = url_path(article.get("thumb_path"))

    if thumb:
        thumb_html = (
            '<div class="card__thumb">'
            f'<img src="{esc(thumb)}" alt="" loading="lazy" decoding="async">'
            "</div>"
        )
    else:
        thumb_html = (
            '<div class="card__thumb card__thumb--empty">'
            f'<span>{esc(part_label)}</span></div>'
        )

    return (
        f'<a class="card" href="/{lang}/{article["slug"]}/">'
        + thumb_html
        + '<div class="card__body">'
        + f'<div class="card__part">{esc(part_label)}</div>'
        + f'<h2 class="card__title">{esc(title)}</h2>'
        + f'<p class="card__excerpt">{esc(excerpt)}</p>'
        + "</div></a>"
    )


def render_index(
    articles: list[dict], cache: dict, lang: str
) -> str:
    if lang == "ru":
        title = SERIES_TITLE_RU
        subtitle_lines = SERIES_SUBTITLE_RU
        page_title = f"{title} — Dreamkilled"
    else:
        title = SERIES_TITLE_EN
        subtitle_lines = SERIES_SUBTITLE_EN
        page_title = f"{title} — Dreamkilled"
    subtitle = " ".join(subtitle_lines)
    subtitle_html = "<br>".join(esc(line) for line in subtitle_lines)
    cards = "\n".join(render_card(article, cache, lang) for article in articles)
    switch_href = "/en/" if lang == "ru" else "/ru/"
    return (
        head(lang, page_title, subtitle)
        + f"<body>\n{topbar(lang, f'/{lang}/', switch_href)}\n"
        + '<main class="container">\n'
        + f'<h1 class="page-title">{esc(title)}</h1>\n'
        + f'<p class="page-subtitle">{subtitle_html}</p>\n'
        + f'<div class="cards">\n{cards}\n</div>\n'
        + "</main>\n"
        + footer(lang)
        + "\n</body>\n</html>\n"
    )


def render_root() -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="dark">\n'
        '<meta name="theme-color" content="#141414">\n'
        "<title>Во что сыграть? — Dreamkilled</title>\n"
        '<meta name="description" content="Рекомендую 400 инди игр! Подборки инди-игр по жанрам.">\n'
        '<link rel="stylesheet" href="/style.css">\n'
        "</head>\n<body>\n"
        '<main class="landing"><div class="landing__inner">\n'
        '<h1 class="landing__title">Во что сыграть?</h1>\n'
        '<p class="landing__subtitle">Рекомендую 400 инди игр!</p>\n'
        '<div class="landing__links">\n'
        '<a class="landing__link" href="/ru/">Русский</a>\n'
        '<a class="landing__link" href="/en/">English</a>\n'
        "</div></div></main>\n"
        "</body>\n</html>\n"
    )


def render_404() -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="dark">\n'
        '<meta name="theme-color" content="#141414">\n'
        "<title>Страница не найдена — Dreamkilled</title>\n"
        '<link rel="stylesheet" href="/style.css">\n'
        "</head>\n<body>\n"
        '<main class="landing"><div class="landing__inner">\n'
        '<p class="landing__eyebrow">404</p>\n'
        '<h1 class="landing__title">Страница не найдена</h1>\n'
        '<p class="landing__subtitle">Возможно, ссылка устарела.</p>\n'
        '<div class="landing__links">'
        '<a class="landing__link" href="/">На главную</a>'
        "</div>\n</div></main>\n</body>\n</html>\n"
    )


def write_text(path: Path, text: str):
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def render_all(articles: list[dict], cache: dict):
    for article in articles:
        for lang in ("ru", "en"):
            page = render_article(article, articles, cache, lang)
            write_text(ROOT / lang / article["slug"] / "index.html", page)
            log(f"  page {lang}/{article['slug']}/index.html")
    write_text(ROOT / "ru" / "index.html", render_index(articles, cache, "ru"))
    write_text(ROOT / "en" / "index.html", render_index(articles, cache, "en"))
    write_text(ROOT / "index.html", render_root())
    write_text(ROOT / "404.html", render_404())
    write_text(ROOT / ".nojekyll", "")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify(articles: list[dict], media_failures, translation_failures):
    log("\nverification")
    page_count = 0
    broken_links: list[str] = []
    missing_src: list[str] = []
    remote_src: list[str] = []

    for lang in ("ru", "en"):
        for article in articles:
            path = ROOT / lang / article["slug"] / "index.html"
            if not path.exists():
                broken_links.append(str(path.relative_to(ROOT)))
                continue
            page_count += 1
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            for tag in soup.find_all(src=True):
                src = tag["src"]
                if src.startswith("http") or src.startswith("//"):
                    remote_src.append(f"{path.name}: {src}")
                    continue
                if src.startswith("/"):
                    target = ROOT / src.lstrip("/")
                    if not target.exists():
                        missing_src.append(f"{path.relative_to(ROOT)} -> {src}")
            for tag in soup.find_all(href=True):
                href = tag["href"]
                if href.startswith(("http", "#", "mailto:", "tel:")):
                    continue
                if href.startswith("/"):
                    parsed_href = urlparse(href)
                    path_part = parsed_href.path
                    target = ROOT / path_part.lstrip("/")
                    if path_part.endswith("/") or target.is_dir():
                        target = target / "index.html"
                    if not target.exists():
                        broken_links.append(
                            f"{path.relative_to(ROOT)} -> {href}"
                        )
                    elif parsed_href.fragment:
                        target_text = target.read_text(encoding="utf-8")
                        if f'id="{parsed_href.fragment}"' not in target_text:
                            broken_links.append(
                                f"{path.relative_to(ROOT)} -> {href} "
                                "(missing anchor)"
                            )

    for path in [
        ROOT / "ru" / "index.html",
        ROOT / "en" / "index.html",
        ROOT / "index.html",
        ROOT / "404.html",
    ]:
        if path.exists():
            page_count += 1

    cyrillic_en = 0
    for article in articles:
        path = ROOT / "en" / article["slug"] / "index.html"
        if not path.exists():
            continue
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        body = soup.select_one(".article__body")
        if body:
            cyrillic_en += len(re.findall(r"[\u0400-\u04FF]", body.get_text(" ")))

    image_count = (
        len([path for path in IMG_DIR.rglob("*") if path.is_file()])
        if IMG_DIR.exists()
        else 0
    )
    video_count = (
        len([path for path in VIDEO_DIR.rglob("*") if path.is_file()])
        if VIDEO_DIR.exists()
        else 0
    )

    log(f"  pages: {page_count}")
    log(f"  media files: {image_count} img, {video_count} video")
    log(f"  missing local media: {len(missing_src)}")
    log(f"  broken local links: {len(broken_links)}")
    log(f"  remote src (should be 0): {len(remote_src)}")
    log(f"  cyrillic chars in EN bodies: {cyrillic_en}")
    log(f"  media download failures: {len(media_failures)}")
    log(f"  translation failures: {len(translation_failures)}")

    for item in missing_src[:20]:
        log("    missing:", item)
    for item in broken_links[:20]:
        log("    broken:", item)
    for item in remote_src[:10]:
        log("    remote:", item)
    for item in media_failures[:10]:
        log("    media fail:", item)
    for item, error in translation_failures[:10]:
        log("    translation fail:", error, repr(item[:80]))

    report = {
        "pages": page_count,
        "images": image_count,
        "videos": video_count,
        "missing_local_media": missing_src,
        "broken_local_links": broken_links,
        "remote_src": remote_src,
        "cyrillic_chars_in_en": cyrillic_en,
        "media_failures": media_failures,
        "translation_failures": [
            {"source": item[:500], "error": error}
            for item, error in translation_failures
        ],
    }
    ensure_dir(DATA_DIR)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


ANCHOR_LINK_RE = re.compile(
    r'href="(/(?:ru|en)/([a-z0-9-]+)/)#([^"]+)"'
)


def fix_anchor_links():
    cached_ids: dict[Path, set[str]] = {}

    def target_ids(path: Path) -> set[str]:
        if path not in cached_ids:
            text = path.read_text(encoding="utf-8")
            cached_ids[path] = set(re.findall(r'id="([^"]+)"', text))
        return cached_ids[path]

    for lang in ("ru", "en"):
        for path in (ROOT / lang).glob("*/index.html"):
            text = path.read_text(encoding="utf-8")

            def replace(match: re.Match) -> str:
                prefix = match.group(1)
                slug = match.group(2)
                anchor = htmlmod.unescape(match.group(3))
                target = ROOT / lang / slug / "index.html"
                if target.exists() and anchor in target_ids(target):
                    return match.group(0)
                return f'href="{prefix}"'

            fixed = ANCHOR_LINK_RE.sub(replace, text)
            if fixed != text:
                path.write_text(fixed, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-media", action="store_true")
    parser.add_argument("--skip-translate", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--parse-only", action="store_true")
    args = parser.parse_args()

    ensure_dir(IMG_DIR)
    ensure_dir(VIDEO_DIR)
    ensure_dir(DATA_DIR)

    if args.verify_only:
        articles = parse_all(use_cache_only=True)
        resolve_media(articles, media_tasks(articles)[1])
        cache = load_cache()
        render_all(articles, cache)
        fix_anchor_links()
        verify(articles, [], [])
        return

    articles = parse_all()
    tasks, mapping = media_tasks(articles)

    if args.parse_only:
        photo_count = sum(
            len(block["photos"])
            for article in articles
            for block in article["blocks"]
            if block["type"] == "photos"
        )
        carousel_count = sum(
            1
            for article in articles
            for block in article["blocks"]
            if block["type"] == "photos" and len(block["photos"]) > 1
        )
        log(
            f"parsed: {len(articles)} articles, {photo_count} photos, "
            f"{carousel_count} carousels, {len(tasks)} media tasks"
        )
        for article in articles:
            log(
                f"  {article['order']:02d} {article['slug']}: "
                f"{len(article['blocks'])} blocks, "
                f"cover={article['cover']['type'] if article.get('cover') else '-'}, "
                f"thumb={'yes' if article.get('og_image') else 'no'}"
            )
        return

    if args.skip_media:
        log("skipping media downloads")
        media_failures = []
    else:
        media_failures = download_media(tasks)

    mapping = {
        key: relative
        for key, relative in mapping.items()
        if (ROOT / relative).exists()
    }
    resolve_media(articles, mapping)
    translation_failures = translate_all(articles, skip_translate=args.skip_translate)
    cache = load_cache()
    render_all(articles, cache)
    fix_anchor_links()
    verify(articles, media_failures, translation_failures)


def parse_all(use_cache_only: bool = False) -> list[dict]:
    articles = []
    for order, (slug, url) in enumerate(ARTICLES, 1):
        log(f"[{order}/{len(ARTICLES)}] {slug}")
        try:
            article = parse_article(slug, url, order)
            articles.append(article)
            log(
                f"  title: {article['title_ru']} | "
                f"part {article['part']} | blocks {len(article['blocks'])}"
            )
        except Exception as exc:  # noqa: BLE001
            if use_cache_only:
                raise
            log(f"  ERROR: {exc}")
    if len(articles) != len(ARTICLES):
        log(f"WARNING: parsed {len(articles)} of {len(ARTICLES)} articles")
    return articles


if __name__ == "__main__":
    main()
