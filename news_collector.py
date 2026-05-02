#!/usr/bin/env python3
"""Daily Tech News Collector — fetch RSS feeds and compile a markdown digest."""

import json
import os
import re
import time
from datetime import date, datetime
from html import unescape
from pathlib import Path

import feedparser
import requests

HERE = Path(__file__).parent
FEEDS_FILE = HERE / "feeds.json"
README_FILE = HERE / "README.md"

# How many entries per feed
MAX_PER_FEED = 10
# Cache TTL in seconds (4 hours)
CACHE_TTL = 14400


def load_feeds() -> list[dict]:
    with open(FEEDS_FILE) as f:
        return json.load(f)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip() if text else ""


def fetch_feed(feed_cfg: dict) -> list[dict]:
    """Fetch and parse an RSS feed, return list of articles."""
    url = feed_cfg["url"]
    name = feed_cfg["name"]
    lang = feed_cfg.get("lang", "en")

    print(f"  Fetching {name} ({url})...")

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "DailyTechNews/1.0"})
        resp.raise_for_status()
        raw = resp.content
    except Exception as e:
        print(f"  ❌ HTTP error for {name}: {e}")
        return []

    feed = feedparser.parse(raw)
    articles = []

    for entry in feed.entries[:MAX_PER_FEED]:
        title = strip_html(entry.get("title", ""))
        if not title:
            continue

        # Best-effort link
        link = entry.get("link", "")

        # Publication date
        pub_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = time.strftime("%Y-%m-%d %H:%M", entry.published_parsed)

        # Description / summary
        summary = strip_html(entry.get("summary", "") or entry.get("description", ""))
        # Truncate long summaries
        if len(summary) > 200:
            summary = summary[:197] + "..."

        articles.append({
            "title": unescape(title),
            "link": link,
            "date": pub_date or "",
            "summary": unescape(summary) if summary else "",
            "source": name,
            "lang": lang,
        })

    print(f"  ✅ Got {len(articles)} articles from {name}")
    return articles


def format_articles(articles: list[dict], heading: str) -> str:
    """Format a list of articles as markdown."""
    if not articles:
        return ""

    lines = [f"## {heading}\n"]
    for art in articles:
        title = art["title"]
        # Truncate very long titles
        if len(title) > 100:
            title = title[:97] + "..."

        source_tag = f"`{art['source']}`"
        link = f"[{title}]({art['link']})" if art["link"] else title
        summary = f"\n> {art['summary']}" if art["summary"] else ""

        lines.append(f"- {source_tag} {link}{summary}")

    lines.append("")
    return "\n".join(lines)


def collect_news() -> str:
    """Collect news from all feeds and return the markdown digest."""
    feeds = load_feeds()
    today = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"📡 Collecting tech news for {today}...\n")

    all_articles = []
    en_articles = []
    zh_articles = []

    for feed_cfg in feeds:
        articles = fetch_feed(feed_cfg)
        all_articles.extend(articles)
        for art in articles:
            if art["lang"] == "zh":
                zh_articles.append(art)
            else:
                en_articles.append(art)

    sections = [
        f"# 📰 每日科技日报 — {today}\n\n> 自动收集于 {now_str} | 共 {len(all_articles)} 条\n",
    ]

    if zh_articles:
        sections.append(format_articles(zh_articles, "🇨🇳 中文科技"))
    if en_articles:
        sections.append(format_articles(en_articles, "🌍 国际科技"))

    sections.append("---\n*🤖 由 Daily Tech News Collector 自动生成*")

    print(f"\n✅ Done! {len(all_articles)} articles collected.")
    return "\n".join(sections)


def update_readme(digest: str):
    """Replace the news section in README.md between markers."""
    marker_start = "<!-- NEWS_START -->"
    marker_end = "<!-- NEWS_END -->"

    new_content = f"{marker_start}\n\n{digest}\n\n{marker_end}"

    if README_FILE.exists():
        content = README_FILE.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(marker_start) + r".*?" + re.escape(marker_end),
            re.DOTALL,
        )
        if pattern.search(content):
            content = pattern.sub(new_content, content)
        else:
            content += f"\n\n{new_content}\n"
    else:
        content = f"# Daily Tech News\n\n{new_content}\n"

    README_FILE.write_text(content, encoding="utf-8")
    print(f"📝 Updated {README_FILE}")


if __name__ == "__main__":
    digest = collect_news()
    update_readme(digest)
    print("\n🎉 Done!")
