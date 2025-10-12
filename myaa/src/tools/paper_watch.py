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


def _get_authors(e) -> list[str]:
    out: list[str] = []
    try:
        if getattr(e, "authors", None):
            for a in e.authors:
                nm = getattr(a, "name", "") or str(a)
                if nm and nm not in out:
                    out.append(nm)
        if not out:
            nm = getattr(e, "author", "") or ""
            if nm:
                out.append(nm)
    except Exception:
        pass
    return out


def _get_org(e) -> str:
    for key in ("arxiv_affiliation", "dc_creator", "source", "source_title"):
        v = getattr(e, key, None)
        if isinstance(v, str) and v.strip():
            return v.strip()
    ad = getattr(e, "author_detail", None)
    if isinstance(ad, dict):
        for k in ("affiliation", "organization", "org"):
            v = ad.get(k) or ""
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def fetch_all_last_24h_rich(opml_path: str) -> list[dict]:
    """
    24h以内の新着を、各要素が
      {
        "title": str,
        "url": str,
        "ts": datetime (JST) or None,
        "abstract": str,
        "authors": [str, ...],
        "org": str
      }
    の辞書配列で返す（新しい順）。
    """
    feeds = opml_feeds(opml_path)
    since = datetime.now(JST) - timedelta(days=1)
    items: list[dict] = []
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
            abstract = (
                getattr(e, "summary", "") or getattr(e, "description", "") or ""
            ).strip()
            authors = _get_authors(e)
            org = _get_org(e)
            items.append(
                {
                    "title": title,
                    "url": link,
                    "ts": ts,
                    "abstract": abstract,
                    "authors": authors,
                    "org": org,
                }
            )
    items.sort(key=lambda x: x["ts"] or datetime.min.replace(tzinfo=JST), reverse=True)
    return items
