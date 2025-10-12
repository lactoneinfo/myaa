from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional
import opml  # type: ignore[import-untyped]
import feedparser  # type: ignore[import-untyped]

JST = timezone(timedelta(hours=9))


def opml_feeds(path: str) -> list[str]:
    doc = opml.parse(path)
    urls: list[str] = []

    def walk(nodes):
        for n in nodes:
            url = getattr(n, "xmlUrl", None)
            if url:
                urls.append(url)
            if getattr(n, "outlines", None):
                walk(n.outlines)

    walk(doc)
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _entry_time(e) -> Optional[datetime]:
    st = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
    if not st:
        return None
    dt = datetime(*st[:6]).replace(tzinfo=timezone.utc).astimezone(JST)
    return dt


def fetch_new_last_24h(feeds: List[str]) -> List[Tuple[str, str, Optional[datetime]]]:
    since = datetime.now(JST) - timedelta(days=1)
    items: List[Tuple[str, str, Optional[datetime]]] = []
    for url in feeds:
        d = feedparser.parse(url)
        for e in d.entries:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            if not title or not link:
                continue
            ts = _entry_time(e)
            if ts and ts >= since:
                items.append((title, link, ts))
    return items


def pick_titles_last_24h(opml_path: str, pick: int = 3):
    """OPMLの全フィードから24h以内の新着を集め、総数とランダムpick件のタイトル配列を返す。"""
    feeds = opml_feeds(opml_path)
    items = fetch_new_last_24h(feeds)  # [(title, link, ts)]
    total = len(items)
    if total == 0:
        return 0, []
    k = min(pick, total)
    sample = random.sample(items, k)
    titles = [t for (t, _link, _ts) in sample]
    return total, titles


def fetch_all_last_24h(
    opml_path: str,
) -> List[Tuple[str, str, Optional[datetime], str]]:
    """
    OPML内の全フィードから、24h以内の新着を (title, link, ts, summary) の配列で返す。
    summary が無い場合は空文字にする。
    """
    feeds = opml_feeds(opml_path)
    since = datetime.now(JST) - timedelta(days=1)
    items: List[Tuple[str, str, Optional[datetime], str]] = []
    for url in feeds:
        d = feedparser.parse(url)
        for e in d.entries:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            if not title or not link:
                continue
            ts = _entry_time(e)
            if not ts or ts < since:
                continue
            summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
            summary = summary.strip()
            items.append((title, link, ts, summary))
    items.sort(key=lambda x: x[2] or datetime.min.replace(tzinfo=JST), reverse=True)
    return items
