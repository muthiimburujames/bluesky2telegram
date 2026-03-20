"""
F1 BlueSky to Telegram Bot
Monitors BlueSky for Formula 1 content and posts to a Telegram channel.
Designed to run on GitHub Actions (free tier) on a schedule.

Features:
  - Rich text: clickable links and @mentions from BlueSky facets
  - RSS feed monitoring from F1 news websites
  - Reddit r/formula1 hot posts (with score filtering)
  - FIA official documents (steward decisions, technical directives)
  - YouTube F1 channels via RSS feeds
  - Skip reposts/boosts to avoid duplicates
  - Duplicate link detection (same article shared by multiple accounts)
  - Smart truncation at sentence boundaries
  - Error recovery with automatic catch-up
  - Popular post highlighting (high engagement)
  - Multi-image albums, video thumbnails
  - Inline buttons (View on BlueSky / Share)
  - Auto-categorization (Technical, Breaking, Transfer, etc.)
  - Self-reply thread detection
  - Welcome message and bot commands
"""

import os
import json
import time
import hashlib
import re
import urllib.parse
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ──────────────────────────────────────────────────────────────
#  Configuration
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
BSKY_PUBLIC_API = "https://public.api.bsky.app"
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "2"))
MAX_POSTS_PER_RUN = int(os.environ.get("MAX_POSTS_PER_RUN", "10"))
STATE_FILE = Path(__file__).parent / "state" / "sent_posts.json"

# Engagement threshold — posts with likes >= this get a "Popular" label
POPULAR_THRESHOLD = int(os.environ.get("POPULAR_THRESHOLD", "50"))

# ──────────────────────────────────────────────────────────────
#  F1 BlueSky accounts to follow
# ──────────────────────────────────────────────────────────────

F1_ACCOUNTS = [
  "f1docs.bsky.social",
  "chrismedlandf1.bsky.social",
  "somersf1.co.uk",
  "jeppe.bsky.social",
  "f1subreddit.bsky.social",
  "scarbstech.bsky.social",
  "thomasmaheronf1.bsky.social",
  "andrewbensonf1.bsky.social",
  "fdataanalysis.bsky.social",
  "f1tv.bsky.social",
]

extra = os.environ.get("EXTRA_BSKY_ACCOUNTS", "")
if extra.strip():
    F1_ACCOUNTS.extend([a.strip() for a in extra.split(",") if a.strip()])

# ──────────────────────────────────────────────────────────────
#  Search keywords
# ──────────────────────────────────────────────────────────────

ENABLE_KEYWORD_SEARCH = os.environ.get("ENABLE_KEYWORD_SEARCH", "false").lower() == "true"
F1_SEARCH_KEYWORDS = ["Formula 1", "Formula1", "#F1"]

# ──────────────────────────────────────────────────────────────
#  RSS Feeds
#  Configure via the RSS_FEEDS GitHub variable.
#  Format: comma-separated feed URLs, e.g.:
#  https://www.motorsport.com/rss/f1/news,https://www.autosport.com/rss/f1/news/
# ──────────────────────────────────────────────────────────────

RSS_FEEDS_RAW = os.environ.get("RSS_FEEDS", "")
RSS_FEEDS = [url.strip() for url in RSS_FEEDS_RAW.split(",") if url.strip()]

# ──────────────────────────────────────────────────────────────
#  Reddit r/formula1
#  Configure via the REDDIT_SUBREDDITS GitHub variable.
#  Default: r/formula1. Format: comma-separated subreddit names
#  e.g.: formula1,F1Technical,FormulaFeeders
# ──────────────────────────────────────────────────────────────

REDDIT_SUBS_RAW = os.environ.get("REDDIT_SUBREDDITS", "formula1")
REDDIT_SUBREDDITS = [s.strip() for s in REDDIT_SUBS_RAW.split(",") if s.strip()]
# Minimum upvotes for a Reddit post to be forwarded (filters noise)
REDDIT_MIN_SCORE = int(os.environ.get("REDDIT_MIN_SCORE", "100"))

# ──────────────────────────────────────────────────────────────
#  FIA Documents (race weekend steward decisions, technical directives)
#  Enabled by default. Set FIA_DOCUMENTS=false to disable.
# ──────────────────────────────────────────────────────────────

FIA_DOCUMENTS_ENABLED = os.environ.get("FIA_DOCUMENTS", "true").lower() == "true"

# ──────────────────────────────────────────────────────────────
#  YouTube F1 Channels
#  YouTube channels have built-in RSS feeds. Add them to your
#  RSS_FEEDS variable using this format:
#  https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
#
#  Useful F1 YouTube channel IDs:
#    Chain Bear:    UCB_qr75-ydFVKSF9s5xFvHw
#    Peter Windsor: UC_ULpnIIQBPSx55F5GwjRhA
#    Tech Tuesday:  (via official F1 channel)
#  These flow through the existing RSS pipeline automatically.
# ──────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
#  Post categorization
# ──────────────────────────────────────────────────────────────

CATEGORY_RULES = {
    "Breaking": [
        r"\bbreaking\b", r"\bconfirmed\b", r"\bjust in\b",
        r"\bannounce[ds]?\b", r"\bofficial\b.*\bstatement\b",
    ],
    "Technical": [
        r"\baero\b", r"\bdownforce\b", r"\bfloor\b", r"\bsidepod",
        r"\bdiffuser\b", r"\brear wing\b", r"\bfront wing\b",
        r"\bsuspension\b", r"\bpower unit\b", r"\bupgrade[ds]?\b",
        r"\bbargeboard\b", r"\bunderbody\b", r"\bbrake duct\b",
        r"\bcooling\b", r"\btelemetry\b", r"\btyre deg", r"\bend ?plate\b",
    ],
    "Transfer": [
        r"\brumou?r", r"\breportedly\b", r"\bunderstood to\b",
        r"\bsources say\b", r"\bcould move\b", r"\blinked with\b",
        r"\bset to join\b", r"\bin talks\b", r"\bdriver market\b",
        r"\bsigning\b", r"\bcontract\b.*\bextension\b",
    ],
    "Race": [
        r"\bwins\b.*\bgrand prix\b", r"\bpodium\b", r"\brace result",
        r"\bclassification\b", r"\bchequ?ered flag\b", r"\bvictory\b",
    ],
    "Regulation": [
        r"\bFIA\b", r"\bregulation", r"\brule change",
        r"\bpenalt(y|ies)\b", r"\bstewards?\b", r"\bprotest\b",
        r"\bcost cap\b", r"\btechnical directive\b",
    ],
}


def categorize_post(text: str) -> str:
    text_lower = text.lower()
    for category, patterns in CATEGORY_RULES.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return category
    return "News"


# ──────────────────────────────────────────────────────────────
#  State management
# ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    return {"sent_ids": [], "last_run": None, "last_update_id": 0,
            "sent_links": [], "last_error": False}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["sent_ids"] = state["sent_ids"][-500:]
    # Track recently sent external links for duplicate detection
    state["sent_links"] = state.get("sent_links", [])[-200:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def post_id_hash(uri: str) -> str:
    return hashlib.sha256(uri.encode()).hexdigest()[:16]


def link_hash(url: str) -> str:
    """Normalize and hash a URL for duplicate link detection."""
    # Strip tracking params, trailing slashes, www prefix
    url = re.sub(r'[?#].*', '', url).rstrip('/').lower()
    url = re.sub(r'^https?://(www\.)?', '', url)
    return hashlib.sha256(url.encode()).hexdigest()[:16]


# ──────────────────────────────────────────────────────────────
#  BlueSky API helpers
# ──────────────────────────────────────────────────────────────

def resolve_handle(handle: str) -> str | None:
    try:
        resp = requests.get(
            f"{BSKY_PUBLIC_API}/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": handle}, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("did")
    except requests.RequestException as e:
        print(f"  ⚠ Could not resolve {handle}: {e}")
    return None


def get_author_feed(did: str, limit: int = 30) -> list[dict]:
    try:
        resp = requests.get(
            f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.getAuthorFeed",
            params={"actor": did, "limit": limit, "filter": "posts_and_author_threads"},
            timeout=15)
        if resp.status_code == 200:
            return resp.json().get("feed", [])
    except requests.RequestException as e:
        print(f"  ⚠ Feed fetch error: {e}")
    return []


def search_posts(query: str, limit: int = 25) -> list[dict]:
    try:
        resp = requests.get(
            f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.searchPosts",
            params={"q": query, "limit": limit, "sort": "latest"},
            timeout=15)
        if resp.status_code == 200:
            return resp.json().get("posts", [])
    except requests.RequestException as e:
        print(f"  ⚠ Search error for '{query}': {e}")
    return []


# ──────────────────────────────────────────────────────────────
#  Rich text: convert BlueSky facets to Telegram HTML
# ──────────────────────────────────────────────────────────────

def escape_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def render_rich_text(text: str, facets: list[dict]) -> str:
    """Convert BlueSky post text + facets into Telegram HTML.

    Facets contain byte-indexed annotations for links and mentions.
    We sort them, process from end to start (to preserve indices),
    and insert HTML tags.
    """
    if not facets:
        return escape_html(text)

    # BlueSky uses byte offsets, so we work with the byte representation
    text_bytes = text.encode("utf-8")

    # Collect insertions: (byte_start, byte_end, html_open, html_close)
    insertions = []
    for facet in facets:
        idx = facet.get("index", {})
        byte_start = idx.get("byteStart", 0)
        byte_end = idx.get("byteEnd", 0)
        if byte_start >= byte_end:
            continue

        for feature in facet.get("features", []):
            ftype = feature.get("$type", "")
            if ftype == "app.bsky.richtext.facet#link":
                uri = feature.get("uri", "")
                if uri:
                    insertions.append((byte_start, byte_end, f'<a href="{uri}">', '</a>'))
            elif ftype == "app.bsky.richtext.facet#mention":
                did = feature.get("did", "")
                # We'll link to the handle text in the post
                handle_text = text_bytes[byte_start:byte_end].decode("utf-8", errors="replace")
                clean_handle = handle_text.lstrip("@")
                profile_url = f"https://bsky.app/profile/{clean_handle}"
                insertions.append((byte_start, byte_end, f'<a href="{profile_url}">', '</a>'))

    if not insertions:
        return escape_html(text)

    # Sort by byte_start descending so we can insert from end without shifting
    insertions.sort(key=lambda x: x[0], reverse=True)

    # Build result by working on the byte array
    result_bytes = bytearray(text_bytes)
    # We need to escape HTML FIRST, then insert tags
    # Strategy: split text into segments, escape each, wrap annotated ones

    # Actually, let's use a simpler approach: build from left to right
    insertions.sort(key=lambda x: x[0])  # sort ascending
    result_parts = []
    prev_end = 0

    for byte_start, byte_end, open_tag, close_tag in insertions:
        # Add escaped text before this facet
        before = text_bytes[prev_end:byte_start].decode("utf-8", errors="replace")
        result_parts.append(escape_html(before))

        # Add the facet text wrapped in tags
        facet_text = text_bytes[byte_start:byte_end].decode("utf-8", errors="replace")
        result_parts.append(f"{open_tag}{escape_html(facet_text)}{close_tag}")

        prev_end = byte_end

    # Add remaining text after last facet
    remaining = text_bytes[prev_end:].decode("utf-8", errors="replace")
    result_parts.append(escape_html(remaining))

    return "".join(result_parts)


# ──────────────────────────────────────────────────────────────
#  Smart text truncation
# ──────────────────────────────────────────────────────────────

def smart_truncate(text: str, max_len: int) -> str:
    """Truncate text at a sentence boundary when possible."""
    if len(text) <= max_len:
        return text

    # Try to break at a sentence boundary
    truncated = text[:max_len]
    # Look for the last sentence-ending punctuation
    for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        last_pos = truncated.rfind(sep)
        if last_pos > max_len * 0.4:  # Don't cut too short
            return truncated[:last_pos + 1] + "..."

    # Fall back to word boundary
    last_space = truncated.rfind(' ')
    if last_space > max_len * 0.5:
        return truncated[:last_space] + "..."

    return truncated + "..."


# ──────────────────────────────────────────────────────────────
#  Post parsing
# ──────────────────────────────────────────────────────────────

def parse_post(feed_item: dict) -> dict | None:
    # Skip reposts/boosts — these have a "reason" field with type "repost"
    reason = feed_item.get("reason", {})
    if reason.get("$type", "") == "app.bsky.feed.defs#reasonRepost":
        return None

    post = feed_item.get("post", feed_item)
    record = post.get("record", {})

    created_at_str = record.get("createdAt", "")
    if not created_at_str:
        return None
    try:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    if created_at < cutoff:
        return None

    text = record.get("text", "").strip()
    if not text:
        return None

    uri = post.get("uri", "")
    author = post.get("author", {})
    author_did = author.get("did", "")
    handle = author.get("handle", "unknown")
    display_name = author.get("displayName", handle)

    # Self-reply detection
    is_self_reply = False
    reply_info = record.get("reply", {})
    if reply_info:
        parent_uri = reply_info.get("parent", {}).get("uri", "")
        if parent_uri and author_did and parent_uri.startswith(f"at://{author_did}/"):
            is_self_reply = True
        elif parent_uri:
            return None

    # BlueSky web link
    bsky_link = ""
    if uri.startswith("at://"):
        parts = uri.replace("at://", "").split("/")
        if len(parts) >= 3:
            bsky_link = f"https://bsky.app/profile/{handle}/post/{parts[-1]}"

    # Extract facets (rich text annotations for links and mentions)
    facets = record.get("facets", [])

    # Engagement metrics
    like_count = post.get("likeCount", 0)
    repost_count = post.get("repostCount", 0)
    reply_count = post.get("replyCount", 0)

    # Embedded images
    images = []
    embed = post.get("embed", {})
    embed_type = embed.get("$type", "")
    if "image" in embed_type:
        for img in embed.get("images", []):
            url = img.get("fullsize", "") or img.get("thumb", "")
            if url:
                images.append(url)

    # Embedded video
    video_thumbnail = ""
    has_video = False
    if "video" in embed_type:
        has_video = True
        video_thumbnail = embed.get("thumbnail", "")

    # External links
    external_url = external_title = external_thumb = ""
    if "external" in embed_type:
        ext = embed.get("external", {})
        external_url = ext.get("uri", "")
        external_title = ext.get("title", "")
        external_thumb = ext.get("thumb", "")

    # recordWithMedia (quote post + images/video)
    if "recordWithMedia" in embed_type:
        media = embed.get("media", {})
        media_type = media.get("$type", "")
        if "image" in media_type:
            for img in media.get("images", []):
                url = img.get("fullsize", "") or img.get("thumb", "")
                if url:
                    images.append(url)
        if "video" in media_type:
            has_video = True
            video_thumbnail = media.get("thumbnail", "")

    return {
        "uri": uri, "text": text, "handle": handle,
        "display_name": display_name, "created_at": created_at,
        "bsky_link": bsky_link, "images": images,
        "has_video": has_video, "video_thumbnail": video_thumbnail,
        "external_url": external_url, "external_title": external_title,
        "external_thumb": external_thumb, "is_self_reply": is_self_reply,
        "category": categorize_post(text), "facets": facets,
        "like_count": like_count, "repost_count": repost_count,
        "reply_count": reply_count,
    }


# ──────────────────────────────────────────────────────────────
#  Telegram posting
# ──────────────────────────────────────────────────────────────

def format_telegram_message(post: dict, as_caption: bool = False) -> str:
    max_len = 1024 if as_caption else 4096
    lines = []

    # Category + special labels
    tags = []
    if post.get("category") and post["category"] != "News":
        tags.append(f'[{post["category"]}]')
    if post.get("is_self_reply"):
        tags.append("[Thread]")
    if post.get("has_video") and post.get("bsky_link"):
        tags.append(f'[Video - <a href="{post["bsky_link"]}">watch on BlueSky</a>]')
    elif post.get("has_video"):
        tags.append("[Video]")

    # Popular post indicator
    likes = post.get("like_count", 0)
    reposts = post.get("repost_count", 0)
    if likes >= POPULAR_THRESHOLD:
        tags.append(f"[Popular - {likes} likes]")

    if tags:
        lines.append("<b>" + " ".join(tags) + "</b>")
        lines.append("")

    # Post text with rich text (clickable links and mentions)
    rich_text = render_rich_text(post["text"], post.get("facets", []))
    lines.append(rich_text)

    # External link
    if post["external_url"]:
        lines.append("")
        title = escape_html(post["external_title"]) if post["external_title"] else "Link"
        lines.append(f'<a href="{post["external_url"]}">{title}</a>')

    # Author handle
    lines.append("")
    if post["bsky_link"]:
        lines.append(f'<a href="{post["bsky_link"]}">@{escape_html(post["handle"])}</a>')
    else:
        lines.append(f'@{escape_html(post["handle"])}')
    # Source
    if post.get("is_reddit"):
        source_label = "Source: Reddit"
    elif post.get("is_fia"):
        source_label = "Source: FIA"
    elif post.get("is_rss"):
        source_label = "Source: RSS"
    else:
        source_label = "Source: BlueSky"
    lines.append(source_label)

    message = "\n".join(lines)

    if len(message) > max_len:
        # Rebuild with smart-truncated text
        # Calculate how much space the non-text parts take
        text_line_idx = 2 if tags else 0  # position of the text in lines
        non_text_parts = lines[:text_line_idx] + lines[text_line_idx + 1:]
        non_text_len = len("\n".join(non_text_parts)) + 2  # +2 for the joining newlines
        available = max_len - non_text_len - 5
        truncated_text = smart_truncate(escape_html(post["text"]), available)
        lines[text_line_idx] = truncated_text
        message = "\n".join(lines)

    return message


def build_inline_buttons(post: dict) -> dict | None:
    if not post.get("bsky_link"):
        return None
    share_text = post["text"][:100] + ("..." if len(post["text"]) > 100 else "")
    share_url = ("https://t.me/share/url?"
                 + urllib.parse.urlencode({"url": post["bsky_link"], "text": share_text}))
    view_label = "Read Article" if post.get("is_rss") else \
                 "View on Reddit" if post.get("is_reddit") else \
                 "View Document" if post.get("is_fia") else \
                 "View on BlueSky"
    return {
        "inline_keyboard": [[
            {"text": view_label, "url": post["bsky_link"]},
            {"text": "Share", "url": share_url},
        ]]
    }


def send_telegram_album(caption: str, photo_urls: list[str]) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return False
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    media = []
    for i, url in enumerate(photo_urls[:10]):
        item = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)
    try:
        resp = requests.post(f"{base_url}/sendMediaGroup",
                             json={"chat_id": TELEGRAM_CHANNEL_ID, "media": media}, timeout=30)
        if resp.status_code == 200:
            return True
        print(f"  ❌ Telegram API error {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"  ❌ Telegram send error: {e}")
    return False


def send_telegram_message(text: str, photo_url: str = "", reply_markup: dict = None) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        return False
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    try:
        if photo_url:
            payload = {"chat_id": TELEGRAM_CHANNEL_ID, "photo": photo_url,
                       "caption": text, "parse_mode": "HTML"}
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            resp = requests.post(f"{base_url}/sendPhoto", json=payload, timeout=30)
        else:
            payload = {"chat_id": TELEGRAM_CHANNEL_ID, "text": text,
                       "parse_mode": "HTML", "disable_web_page_preview": False}
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            resp = requests.post(f"{base_url}/sendMessage", json=payload, timeout=30)
        if resp.status_code == 200:
            return True
        print(f"  ❌ Telegram API error {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"  ❌ Telegram send error: {e}")
    return False


# ──────────────────────────────────────────────────────────────
#  Welcome message & bot profile setup
# ──────────────────────────────────────────────────────────────

def setup_bot_profile():
    if not TELEGRAM_BOT_TOKEN:
        return
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    description = (
        "Your automated Formula 1 news feed, powered by BlueSky.\n\n"
        "This bot monitors top F1 journalists and media outlets on BlueSky "
        "and delivers their posts directly to the channel.\n\n"
        "Posts are auto-categorized as Breaking, Technical, Transfer, "
        "Race, Regulation, or general News.")
    try:
        requests.post(f"{base_url}/setMyDescription",
                      json={"description": description}, timeout=10)
    except requests.RequestException:
        pass
    short_desc = "Automated F1 news from BlueSky journalists and media"
    try:
        requests.post(f"{base_url}/setMyShortDescription",
                      json={"short_description": short_desc}, timeout=10)
    except requests.RequestException:
        pass
    commands = [
        {"command": "start", "description": "About this bot"},
        {"command": "sources", "description": "View monitored BlueSky accounts"},
    ]
    try:
        requests.post(f"{base_url}/setMyCommands",
                      json={"commands": commands}, timeout=10)
    except requests.RequestException:
        pass


def handle_bot_commands():
    if not TELEGRAM_BOT_TOKEN:
        return
    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    state = load_state()
    last_update_id = state.get("last_update_id", 0)
    try:
        resp = requests.get(f"{base_url}/getUpdates",
                            params={"offset": last_update_id + 1, "timeout": 0, "limit": 20},
                            timeout=15)
        if resp.status_code != 200:
            return
        updates = resp.json().get("result", [])
    except requests.RequestException:
        return

    for update in updates:
        update_id = update.get("update_id", 0)
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id", "")
        if not chat_id:
            last_update_id = max(last_update_id, update_id)
            continue

        if text.startswith("/start"):
            welcome = (
                "<b>Welcome to the F1 BlueSky News Bot!</b>\n\n"
                "This bot automatically monitors Formula 1 journalists "
                "and media outlets on BlueSky and delivers their posts "
                "to our Telegram channel.\n\n"
                "Posts are auto-categorized:\n"
                "  <b>[Breaking]</b> - Confirmed news and announcements\n"
                "  <b>[Technical]</b> - Car upgrades, aero analysis\n"
                "  <b>[Transfer]</b> - Driver market rumours and moves\n"
                "  <b>[Race]</b> - Race results and podiums\n"
                "  <b>[Regulation]</b> - FIA rules and penalties\n\n"
                "Use /sources to see which accounts we monitor.")
            try:
                requests.post(f"{base_url}/sendMessage",
                              json={"chat_id": chat_id, "text": welcome, "parse_mode": "HTML"},
                              timeout=10)
            except requests.RequestException:
                pass
        elif text.startswith("/sources"):
            sources = "<b>Monitored BlueSky Accounts:</b>\n\n"
            for acct in F1_ACCOUNTS:
                sources += f'  <a href="https://bsky.app/profile/{acct}">@{acct}</a>\n'
            sources += (f"\nTotal: {len(F1_ACCOUNTS)} accounts\n"
                        f"Keyword search: {'ON' if ENABLE_KEYWORD_SEARCH else 'OFF'}")
            try:
                requests.post(f"{base_url}/sendMessage",
                              json={"chat_id": chat_id, "text": sources, "parse_mode": "HTML",
                                    "disable_web_page_preview": True}, timeout=10)
            except requests.RequestException:
                pass
        last_update_id = max(last_update_id, update_id)

    if updates:
        state["last_update_id"] = last_update_id
        save_state(state)


# ──────────────────────────────────────────────────────────────
#  Post filtering and deduplication
# ──────────────────────────────────────────────────────────────

def deduplicate_posts(posts: list[dict]) -> list[dict]:
    """Remove duplicates by URI."""
    seen = set()
    unique = []
    for p in posts:
        if p["uri"] not in seen:
            seen.add(p["uri"])
            unique.append(p)
    return unique


def filter_duplicate_links(posts: list[dict], sent_links: set) -> list[dict]:
    """If multiple posts share the same external URL, keep only the first.
    Also skip posts whose external URL was already sent in a recent run."""
    seen_links = set(sent_links)
    filtered = []
    for p in posts:
        ext_url = p.get("external_url", "")
        if ext_url:
            lh = link_hash(ext_url)
            if lh in seen_links:
                print(f"     🔗 Skipping duplicate link: {ext_url[:60]}... (by @{p['handle']})")
                continue
            seen_links.add(lh)
        filtered.append(p)
    return filtered


# ──────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────

def collect_posts_from_accounts() -> list[dict]:
    all_posts = []
    for handle in F1_ACCOUNTS:
        print(f"  📡 Fetching posts from @{handle}...")
        did = resolve_handle(handle)
        if not did:
            print("     ⚠ Could not resolve handle, skipping")
            continue
        for item in get_author_feed(did):
            parsed = parse_post(item)
            if parsed:
                all_posts.append(parsed)
        time.sleep(0.5)
    return all_posts


def collect_posts_from_search() -> list[dict]:
    if not ENABLE_KEYWORD_SEARCH:
        return []
    all_posts = []
    for keyword in F1_SEARCH_KEYWORDS:
        print(f"  🔍 Searching for '{keyword}'...")
        for post_data in search_posts(keyword):
            parsed = parse_post(post_data)
            if parsed:
                all_posts.append(parsed)
        time.sleep(0.5)
    return all_posts


def collect_posts_from_rss() -> list[dict]:
    """Fetch recent articles from configured RSS feeds.

    Returns posts in the same format as BlueSky posts so they flow
    through the same deduplication, formatting, and sending pipeline.
    """
    if not RSS_FEEDS:
        return []

    all_posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    for feed_url in RSS_FEEDS:
        print(f"  📰 Fetching RSS: {feed_url[:60]}...")
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"     ⚠ RSS parse error: {e}")
            continue

        feed_title = feed.feed.get("title", feed_url)

        for entry in feed.entries[:20]:  # Check last 20 entries per feed
            # Parse published date
            published = None
            for date_field in ("published_parsed", "updated_parsed"):
                parsed_time = entry.get(date_field)
                if parsed_time:
                    try:
                        published = datetime(*parsed_time[:6], tzinfo=timezone.utc)
                    except (TypeError, ValueError):
                        pass
                    break

            if not published:
                # No parseable date — skip to be safe
                continue

            if published < cutoff:
                continue

            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            link = entry.get("link", "").strip()

            if not title:
                continue

            # Clean HTML tags from summary
            clean_summary = re.sub(r'<[^>]+>', '', summary).strip()
            # Limit summary length
            if len(clean_summary) > 300:
                clean_summary = smart_truncate(clean_summary, 300)

            # Build the post text: title + summary if available
            text = title
            if clean_summary and clean_summary.lower() != title.lower():
                text = f"{title}\n\n{clean_summary}"

            # Try to find an image from the entry
            image_url = ""
            # Check media:content or media:thumbnail
            for media in entry.get("media_content", []):
                if media.get("medium") == "image" or "image" in media.get("type", ""):
                    image_url = media.get("url", "")
                    break
            if not image_url:
                for media in entry.get("media_thumbnail", []):
                    image_url = media.get("url", "")
                    break
            # Check enclosures
            if not image_url:
                for enc in entry.get("enclosures", []):
                    if "image" in enc.get("type", ""):
                        image_url = enc.get("href", "") or enc.get("url", "")
                        break

            # Create a unique URI for deduplication (RSS entries don't have AT URIs)
            entry_id = entry.get("id", "") or link or title
            uri = f"rss:{hashlib.sha256(entry_id.encode()).hexdigest()[:32]}"

            all_posts.append({
                "uri": uri,
                "text": text,
                "handle": feed_title,
                "display_name": feed_title,
                "created_at": published,
                "bsky_link": link,  # Re-use bsky_link field for the article URL
                "images": [image_url] if image_url else [],
                "has_video": False,
                "video_thumbnail": "",
                "external_url": link,
                "external_title": "",
                "external_thumb": "",
                "is_self_reply": False,
                "category": categorize_post(text),
                "facets": [],
                "like_count": 0,
                "repost_count": 0,
                "reply_count": 0,
                "is_rss": True,
            })

        time.sleep(0.3)

    return all_posts


def collect_posts_from_reddit() -> list[dict]:
    """Fetch hot posts from configured Reddit subreddits using the public .json endpoint.

    No API key needed — Reddit serves JSON for any subreddit URL with .json appended.
    We filter by minimum score to avoid noise.
    """
    if not REDDIT_SUBREDDITS:
        return []

    all_posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    headers = {"User-Agent": "F1TelegramBot/1.0 (GitHub Actions)"}

    for subreddit in REDDIT_SUBREDDITS:
        print(f"  🟠 Fetching Reddit r/{subreddit}...")
        try:
            resp = requests.get(
                f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25",
                headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"     ⚠ Reddit returned {resp.status_code}")
                continue
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"     ⚠ Reddit error: {e}")
            continue

        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            if post.get("stickied"):
                continue  # Skip pinned/megathread posts

            score = post.get("score", 0)
            if score < REDDIT_MIN_SCORE:
                continue

            created_utc = post.get("created_utc", 0)
            created_at = datetime.fromtimestamp(created_utc, tz=timezone.utc)
            if created_at < cutoff:
                continue

            title = post.get("title", "").strip()
            selftext = post.get("selftext", "").strip()
            permalink = post.get("permalink", "")
            url = post.get("url", "")
            link = f"https://www.reddit.com{permalink}" if permalink else url

            if not title:
                continue

            # Build post text: title + summary for self posts
            text = title
            if selftext and not post.get("is_self", False):
                pass  # Link posts — just title
            elif selftext:
                clean = selftext[:300]
                if len(selftext) > 300:
                    clean = smart_truncate(clean, 300)
                text = f"{title}\n\n{clean}"

            # Get thumbnail/preview image
            image_url = ""
            preview = post.get("preview", {})
            if preview:
                images = preview.get("images", [])
                if images:
                    source = images[0].get("source", {})
                    image_url = source.get("url", "").replace("&amp;", "&")

            # If it's a link post to an article, use it as external_url
            external_url = ""
            if not post.get("is_self", False) and url and "reddit.com" not in url:
                external_url = url

            uri = f"reddit:{post.get('id', hashlib.sha256(title.encode()).hexdigest()[:16])}"
            author = post.get("author", "unknown")

            all_posts.append({
                "uri": uri,
                "text": text,
                "handle": f"r/{subreddit}",
                "display_name": f"r/{subreddit} (u/{author})",
                "created_at": created_at,
                "bsky_link": link,
                "images": [image_url] if image_url else [],
                "has_video": False,
                "video_thumbnail": "",
                "external_url": external_url,
                "external_title": "",
                "external_thumb": "",
                "is_self_reply": False,
                "category": categorize_post(text),
                "facets": [],
                "like_count": score,
                "repost_count": 0,
                "reply_count": post.get("num_comments", 0),
                "is_rss": False,
                "is_reddit": True,
            })

        time.sleep(1)  # Be respectful to Reddit

    return all_posts


def collect_posts_from_fia() -> list[dict]:
    """Fetch latest FIA F1 documents from the FIA website.

    Uses the FIA documents API endpoint to get steward decisions,
    technical directives, and other official documents.
    """
    if not FIA_DOCUMENTS_ENABLED:
        return []

    print("  📋 Fetching FIA documents...")
    all_posts = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    # The FIA documents page for F1 current season
    fia_url = "https://www.fia.com/documents/championships/fia-formula-one-world-championship-14/season/season-2026-2072"

    try:
        resp = requests.get(fia_url, timeout=15,
                            headers={"User-Agent": "F1TelegramBot/1.0"})
        if resp.status_code != 200:
            print(f"     ⚠ FIA returned {resp.status_code}")
            return []

        # Parse document links from the HTML
        # FIA document entries follow a pattern with document titles and PDF links
        html = resp.text

        # Find document entries — they contain links to PDFs and document titles
        # Pattern: look for document listing items
        doc_pattern = re.findall(
            r'<a[^>]*href="(/sites/default/files/[^"]*\.pdf)"[^>]*>.*?</a>',
            html, re.DOTALL
        )
        title_pattern = re.findall(
            r'class="document-title[^"]*"[^>]*>(.*?)</(?:div|span|a)',
            html, re.DOTALL
        )

        # Also try a more general pattern for document links
        if not doc_pattern:
            doc_pattern = re.findall(
                r'href="(https?://[^"]*fia[^"]*\.pdf)"',
                html
            )

        # Try to find structured document data (some FIA pages use JSON-LD or data attributes)
        json_match = re.search(r'var\s+documents\s*=\s*(\[.*?\]);', html, re.DOTALL)
        if json_match:
            try:
                docs_data = json.loads(json_match.group(1))
                for doc in docs_data[:15]:
                    title = doc.get("title", "") or doc.get("name", "")
                    pdf_url = doc.get("url", "") or doc.get("file", "")
                    pub_date_str = doc.get("date", "") or doc.get("published", "")

                    if not title:
                        continue

                    # Try to parse the date
                    published = None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                        try:
                            published = datetime.strptime(pub_date_str, fmt).replace(tzinfo=timezone.utc)
                            break
                        except (ValueError, TypeError):
                            continue
                    if not published:
                        published = datetime.now(timezone.utc)

                    if published < cutoff:
                        continue

                    link = pdf_url if pdf_url.startswith("http") else f"https://www.fia.com{pdf_url}"
                    uri = f"fia:{hashlib.sha256(title.encode()).hexdigest()[:16]}"

                    all_posts.append({
                        "uri": uri,
                        "text": f"FIA Document: {title.strip()}",
                        "handle": "FIA",
                        "display_name": "FIA",
                        "created_at": published,
                        "bsky_link": link,
                        "images": [],
                        "has_video": False,
                        "video_thumbnail": "",
                        "external_url": link,
                        "external_title": title.strip(),
                        "external_thumb": "",
                        "is_self_reply": False,
                        "category": "Regulation",
                        "facets": [],
                        "like_count": 0,
                        "repost_count": 0,
                        "reply_count": 0,
                        "is_rss": False,
                        "is_fia": True,
                    })
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: extract whatever document links we can find from raw HTML
        if not all_posts and (doc_pattern or title_pattern):
            titles = title_pattern if title_pattern else [f"FIA Document {i+1}" for i in range(len(doc_pattern))]
            for i, pdf_link in enumerate(doc_pattern[:10]):
                title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else f"FIA Document"
                link = pdf_link if pdf_link.startswith("http") else f"https://www.fia.com{pdf_link}"
                uri = f"fia:{hashlib.sha256(link.encode()).hexdigest()[:16]}"

                all_posts.append({
                    "uri": uri,
                    "text": f"FIA Document: {title}",
                    "handle": "FIA",
                    "display_name": "FIA",
                    "created_at": datetime.now(timezone.utc),  # No date available in fallback
                    "bsky_link": link,
                    "images": [],
                    "has_video": False,
                    "video_thumbnail": "",
                    "external_url": link,
                    "external_title": title,
                    "external_thumb": "",
                    "is_self_reply": False,
                    "category": "Regulation",
                    "facets": [],
                    "like_count": 0,
                    "repost_count": 0,
                    "reply_count": 0,
                    "is_rss": False,
                    "is_fia": True,
                })

    except requests.RequestException as e:
        print(f"     ⚠ FIA fetch error: {e}")

    print(f"     Found {len(all_posts)} FIA documents")
    return all_posts


def main():
    print("=" * 60)
    print("🏁 F1 BlueSky → Telegram Bot")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Lookback: {LOOKBACK_HOURS} hours")
    print(f"   Accounts: {len(F1_ACCOUNTS)}")
    print(f"   Keyword search: {'ON' if ENABLE_KEYWORD_SEARCH else 'OFF'}")
    print(f"   RSS feeds: {len(RSS_FEEDS)}")
    print(f"   Reddit: {', '.join('r/' + s for s in REDDIT_SUBREDDITS)} (min score: {REDDIT_MIN_SCORE})")
    print(f"   FIA documents: {'ON' if FIA_DOCUMENTS_ENABLED else 'OFF'}")
    print("=" * 60)

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set.")
        return
    if not TELEGRAM_CHANNEL_ID:
        print("❌ TELEGRAM_CHANNEL_ID not set.")
        return

    setup_bot_profile()
    handle_bot_commands()

    state = load_state()
    sent_ids = set(state.get("sent_ids", []))
    sent_links = set(state.get("sent_links", []))

    # Error recovery: if last run had an error, extend lookback to catch up
    effective_lookback = LOOKBACK_HOURS
    if state.get("last_error"):
        effective_lookback = LOOKBACK_HOURS * 2
        print(f"⚡ Error recovery mode — extending lookback to {effective_lookback}h")
        # Temporarily patch the global for parse_post's cutoff check
        # Will be adjusted below
    # We handle this by passing it through; parse_post uses the global,
    # so we temporarily adjust it
    original_lookback = LOOKBACK_HOURS

    try:
        if state.get("last_error"):
            # Monkey-patch for this run only
            import builtins
            globals()["LOOKBACK_HOURS"] = effective_lookback
            print(f"⚡ Error recovery — lookback extended to {effective_lookback}h")

        print(f"📋 Previously sent: {len(sent_ids)} posts tracked")

        print("\n📡 Fetching from BlueSky accounts...")
        posts = collect_posts_from_accounts()
        print("\n🔍 Searching keywords...")
        posts.extend(collect_posts_from_search())
        print("\n📰 Fetching RSS feeds...")
        posts.extend(collect_posts_from_rss())
        print("\n🟠 Fetching Reddit...")
        posts.extend(collect_posts_from_reddit())
        print("\n📋 Fetching FIA documents...")
        posts.extend(collect_posts_from_fia())

        # Deduplicate by URI
        posts = deduplicate_posts(posts)
        posts.sort(key=lambda p: p["created_at"])
        print(f"\n📊 Found {len(posts)} posts within lookback window")

        # Filter out already-sent posts
        new_posts = [p for p in posts if post_id_hash(p["uri"]) not in sent_ids]
        print(f"🆕 New posts to send: {len(new_posts)}")

        # Filter duplicate links (same article shared by multiple accounts)
        new_posts = filter_duplicate_links(new_posts, sent_links)
        print(f"📰 After link dedup: {len(new_posts)}")

        if len(new_posts) > MAX_POSTS_PER_RUN:
            print(f"⚠ Capping to {MAX_POSTS_PER_RUN} posts this run")
            new_posts = new_posts[:MAX_POSTS_PER_RUN]

        sent_count = 0
        for post in new_posts:
            cat = f" [{post['category']}]" if post["category"] != "News" else ""
            popular = f" ♥{post['like_count']}" if post["like_count"] >= POPULAR_THRESHOLD else ""
            print(f"\n  📤 Sending{cat}{popular}: @{post['handle']} — {post['text'][:60]}...")

            photos = post["images"]
            buttons = build_inline_buttons(post)
            success = False

            if len(photos) > 1:
                msg = format_telegram_message(post, as_caption=True)
                print(f"     📸 Album with {len(photos)} images...")
                success = send_telegram_album(msg, photos)
                if not success:
                    print("     ⚠ Album failed, retrying single image...")
                    success = send_telegram_message(msg, photo_url=photos[0], reply_markup=buttons)

            elif len(photos) == 1:
                msg = format_telegram_message(post, as_caption=True)
                success = send_telegram_message(msg, photo_url=photos[0], reply_markup=buttons)

            elif post.get("has_video") and post.get("video_thumbnail"):
                msg = format_telegram_message(post, as_caption=True)
                print("     🎬 Video thumbnail...")
                success = send_telegram_message(msg, photo_url=post["video_thumbnail"], reply_markup=buttons)

            elif post.get("has_video"):
                msg = format_telegram_message(post, as_caption=False)
                success = send_telegram_message(msg, reply_markup=buttons)

            elif post["external_thumb"]:
                msg = format_telegram_message(post, as_caption=True)
                success = send_telegram_message(msg, photo_url=post["external_thumb"], reply_markup=buttons)

            else:
                msg = format_telegram_message(post, as_caption=False)
                success = send_telegram_message(msg, reply_markup=buttons)

            if not success and (photos or post.get("video_thumbnail") or post["external_thumb"]):
                print("     ⚠ Retrying without images...")
                msg = format_telegram_message(post, as_caption=False)
                success = send_telegram_message(msg, reply_markup=buttons)

            if success:
                sent_count += 1
                state["sent_ids"].append(post_id_hash(post["uri"]))
                # Track external links for cross-account dedup
                if post.get("external_url"):
                    state.setdefault("sent_links", []).append(link_hash(post["external_url"]))
                print("     ✅ Sent!")

            time.sleep(3)

        state["last_error"] = False
        save_state(state)
        print(f"\n{'=' * 60}")
        print(f"✅ Done! Sent {sent_count}/{len(new_posts)} posts to Telegram.")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        state["last_error"] = True
        save_state(state)
        raise  # Re-raise so GitHub Actions marks the run as failed
    finally:
        # Restore original lookback
        globals()["LOOKBACK_HOURS"] = original_lookback


if __name__ == "__main__":
    main()
