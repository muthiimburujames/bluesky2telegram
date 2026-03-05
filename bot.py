"""
F1 BlueSky to Telegram Bot
Monitors BlueSky for Formula 1 content and posts to a Telegram channel.
Designed to run on GitHub Actions (free tier) on a schedule.
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ──────────────────────────────────────────────────────────────
#  Configuration (loaded from environment variables / GitHub Secrets)
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")

# BlueSky API base (public, no auth needed for reading public posts)
BSKY_PUBLIC_API = "https://public.api.bsky.app"

# How far back to look for posts (in hours). Keep this slightly larger
# than your GitHub Actions cron interval to avoid missing posts.
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "2"))

# Maximum posts to send per run (prevents flooding on first run)
MAX_POSTS_PER_RUN = int(os.environ.get("MAX_POSTS_PER_RUN", "10"))

# State file tracks which posts have already been sent
STATE_FILE = Path(__file__).parent / "state" / "sent_posts.json"

# ──────────────────────────────────────────────────────────────
#  F1 BlueSky accounts to follow
#  Edit this list to add/remove accounts!
# ──────────────────────────────────────────────────────────────

F1_ACCOUNTS = [
     # ── Official ──
    "f1docs.bsky.social",                  # Official F1 Documents
    # ── Journalists ──
    "chrismedlandf1.bsky.social",      # Chris Medland
    "albertfabrega.bsky.social",          # Abert Fabrega
    "jeppe.bsky.social",   # Jeppe Olsen
    "f1subreddit.bsky.social",         # F1 Subreddit
    "scarbstech.bsky.social",         # Scarbs Tech
    "thomasmaheronf1.bsky.social",     # Thomas Maher
    "andrewbensonf1.bsky.social",        # Andrew Benson
    "fdataanalysis.bsky.social",         # F1 Data Analysis
    "f1tv.bsky.social",                  # F1TV 
]

# Optional: add your own custom accounts via environment variable
# Format: comma-separated handles e.g. "user1.bsky.social,user2.bsky.social"
extra = os.environ.get("EXTRA_BSKY_ACCOUNTS", "")
if extra.strip():
    F1_ACCOUNTS.extend([a.strip() for a in extra.split(",") if a.strip()])

# ──────────────────────────────────────────────────────────────
#  Search keywords (used for keyword-based discovery)
#  Set ENABLE_KEYWORD_SEARCH=true in your GitHub Secrets to enable
# ──────────────────────────────────────────────────────────────

ENABLE_KEYWORD_SEARCH = os.environ.get("ENABLE_KEYWORD_SEARCH", "false").lower() == "true"

F1_SEARCH_KEYWORDS = [
    "Formula 1",
    "Formula1",
    "#F1",
]


# ──────────────────────────────────────────────────────────────
#  State management (tracks which posts we've already sent)
# ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load the set of already-sent post IDs from disk."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return data
        except (json.JSONDecodeError, KeyError):
            pass
    return {"sent_ids": [], "last_run": None}


def save_state(state: dict):
    """Persist state to disk so GitHub Actions can commit it."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Keep only last 500 IDs to prevent the file from growing forever
    state["sent_ids"] = state["sent_ids"][-500:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def post_id_hash(uri: str) -> str:
    """Create a short hash of a post URI for deduplication."""
    return hashlib.sha256(uri.encode()).hexdigest()[:16]


# ──────────────────────────────────────────────────────────────
#  BlueSky API helpers
# ──────────────────────────────────────────────────────────────

def resolve_handle(handle: str) -> str | None:
    """Resolve a BlueSky handle to a DID."""
    try:
        resp = requests.get(
            f"{BSKY_PUBLIC_API}/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": handle},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("did")
    except requests.RequestException as e:
        print(f"  ⚠ Could not resolve {handle}: {e}")
    return None


def get_author_feed(did: str, limit: int = 30) -> list[dict]:
    """Fetch recent posts from a BlueSky account."""
    try:
        resp = requests.get(
            f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.getAuthorFeed",
            params={"actor": did, "limit": limit, "filter": "posts_and_author_threads"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("feed", [])
    except requests.RequestException as e:
        print(f"  ⚠ Feed fetch error: {e}")
    return []


def search_posts(query: str, limit: int = 25) -> list[dict]:
    """Search BlueSky for posts matching a query."""
    try:
        resp = requests.get(
            f"{BSKY_PUBLIC_API}/xrpc/app.bsky.feed.searchPosts",
            params={"q": query, "limit": limit, "sort": "latest"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("posts", [])
    except requests.RequestException as e:
        print(f"  ⚠ Search error for '{query}': {e}")
    return []


# ──────────────────────────────────────────────────────────────
#  Post parsing
# ──────────────────────────────────────────────────────────────

def parse_post(feed_item: dict) -> dict | None:
    """Extract useful fields from a BlueSky feed item."""
    # Handle both feed items (from getAuthorFeed) and raw posts (from search)
    post = feed_item.get("post", feed_item)
    record = post.get("record", {})

    created_at_str = record.get("createdAt", "")
    if not created_at_str:
        return None

    # Parse timestamp
    try:
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    # Check if post is within our lookback window
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

    # Detect self-replies (author replying to their own post / thread)
    is_self_reply = False
    reply_info = record.get("reply", {})
    if reply_info:
        parent_uri = reply_info.get("parent", {}).get("uri", "")
        # A self-reply is when the parent post belongs to the same author
        # AT URI format: at://did:plc:xxx/app.bsky.feed.post/yyy
        if parent_uri and author_did and parent_uri.startswith(f"at://{author_did}/"):
            is_self_reply = True
        elif parent_uri and not author_did:
            # If we can't determine authorship, skip replies to be safe
            # (avoids posting someone else's conversation)
            return None
        else:
            # This is a reply to someone else — skip it
            return None

    # Build BlueSky web link from AT URI
    # Format: at://did:plc:xxx/app.bsky.feed.post/yyy
    bsky_link = ""
    if uri.startswith("at://"):
        parts = uri.replace("at://", "").split("/")
        if len(parts) >= 3:
            bsky_link = f"https://bsky.app/profile/{handle}/post/{parts[-1]}"

    # Check for embedded images
    images = []
    embed = post.get("embed", {})
    embed_type = embed.get("$type", "")
    if "image" in embed_type:
        for img in embed.get("images", []):
            # Prefer fullsize, fall back to thumb
            fullsize = img.get("fullsize", "")
            thumb = img.get("thumb", "")
            url = fullsize or thumb
            if url:
                images.append(url)

    # Check for embedded video
    # BlueSky serves video as HLS streams (not direct MP4), so we grab
    # the thumbnail and link to the original post for playback
    video_thumbnail = ""
    has_video = False
    if "video" in embed_type:
        has_video = True
        video_thumbnail = embed.get("thumbnail", "")

    # Check for embedded links / external cards
    external_url = ""
    external_title = ""
    external_thumb = ""
    if "external" in embed_type:
        ext = embed.get("external", {})
        external_url = ext.get("uri", "")
        external_title = ext.get("title", "")
        external_thumb = ext.get("thumb", "")

    # Handle recordWithMedia embeds (e.g. quote post + images/video)
    if "recordWithMedia" in embed_type:
        media = embed.get("media", {})
        media_type = media.get("$type", "")
        if "image" in media_type:
            for img in media.get("images", []):
                fullsize = img.get("fullsize", "")
                thumb = img.get("thumb", "")
                url = fullsize or thumb
                if url:
                    images.append(url)
        if "video" in media_type:
            has_video = True
            video_thumbnail = media.get("thumbnail", "")

    return {
        "uri": uri,
        "text": text,
        "handle": handle,
        "display_name": display_name,
        "created_at": created_at,
        "bsky_link": bsky_link,
        "images": images,
        "has_video": has_video,
        "video_thumbnail": video_thumbnail,
        "external_url": external_url,
        "external_title": external_title,
        "external_thumb": external_thumb,
        "is_self_reply": is_self_reply,
    }


# ──────────────────────────────────────────────────────────────
#  Telegram posting
# ──────────────────────────────────────────────────────────────

def format_telegram_message(post: dict, as_caption: bool = False) -> str:
    """Format a BlueSky post into a clean Telegram message.

    Layout (normal post):
      [post text]

      @handle
      Source: BlueSky

    Layout (thread reply):
      [Thread]
      [post text]

      @handle
      Source: BlueSky

    Layout (video post):
      [Video - watch on BlueSky]
      [post text]

      @handle
      Source: BlueSky

    If as_caption is True, keeps it under 1024 chars (Telegram caption limit).
    """
    max_len = 1024 if as_caption else 4096
    lines = []

    # Thread label for self-replies
    if post.get("is_self_reply"):
        lines.append("<b>[Thread]</b>")
        lines.append("")

    # Video label with link to watch on BlueSky
    if post.get("has_video") and post.get("bsky_link"):
        lines.append(f'<b>[Video - <a href="{post["bsky_link"]}">watch on BlueSky</a>]</b>')
        lines.append("")
    elif post.get("has_video"):
        lines.append("<b>[Video]</b>")
        lines.append("")

    # Post text
    lines.append(escape_html(post["text"]))

    # External link (if present, add it after the text)
    if post["external_url"]:
        lines.append("")
        if post["external_title"]:
            lines.append(f'<a href="{post["external_url"]}">{escape_html(post["external_title"])}</a>')
        else:
            lines.append(f'<a href="{post["external_url"]}">Link</a>')

    # Author handle
    if post["bsky_link"]:
        lines.append("")
        lines.append(f'<a href="{post["bsky_link"]}">@{escape_html(post["handle"])}</a>')
    else:
        lines.append("")
        lines.append(f"@{escape_html(post['handle'])}")

    # Source
    lines.append("Source: BlueSky")

    message = "\n".join(lines)

    # Trim if over the limit
    if len(message) > max_len:
        # Rebuild with truncated post text
        suffix_lines = lines[1:]  # everything after the post text
        suffix = "\n".join(suffix_lines)
        available = max_len - len(suffix) - 10  # leave room for "..."
        truncated_text = escape_html(post["text"])[:available] + "..."
        message = truncated_text + "\n" + suffix

    return message


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram's HTML parse mode."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def send_telegram_album(caption: str, photo_urls: list[str]) -> bool:
    """Send multiple photos as an album to the Telegram channel.

    Telegram's sendMediaGroup displays all images grouped together.
    The caption is attached to the first image.
    Supports 2-10 photos per album.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("  ❌ Telegram credentials not set!")
        return False

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    # Build the media array — caption goes on the first photo only
    media = []
    for i, url in enumerate(photo_urls[:10]):  # Telegram allows max 10
        item = {"type": "photo", "media": url}
        if i == 0:
            item["caption"] = caption
            item["parse_mode"] = "HTML"
        media.append(item)

    try:
        resp = requests.post(
            f"{base_url}/sendMediaGroup",
            json={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "media": media,
            },
            timeout=30,
        )

        if resp.status_code == 200:
            return True
        else:
            print(f"  ❌ Telegram API error {resp.status_code}: {resp.text[:200]}")
            return False

    except requests.RequestException as e:
        print(f"  ❌ Telegram send error: {e}")
        return False


def send_telegram_message(text: str, photo_url: str = "") -> bool:
    """Send a message (with optional photo) to the Telegram channel.

    When a photo is provided, it's sent as a photo message with the text
    as caption (image appears first, text below).
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("  ❌ Telegram credentials not set!")
        return False

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    try:
        if photo_url:
            # Send as photo — image displays first, caption below
            resp = requests.post(
                f"{base_url}/sendPhoto",
                json={
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "photo": photo_url,
                    "caption": text,
                    "parse_mode": "HTML",
                },
                timeout=30,
            )
        else:
            resp = requests.post(
                f"{base_url}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=30,
            )

        if resp.status_code == 200:
            return True
        else:
            print(f"  ❌ Telegram API error {resp.status_code}: {resp.text[:200]}")
            return False

    except requests.RequestException as e:
        print(f"  ❌ Telegram send error: {e}")
        return False


# ──────────────────────────────────────────────────────────────
#  Main logic
# ──────────────────────────────────────────────────────────────

def collect_posts_from_accounts() -> list[dict]:
    """Fetch recent posts from all configured BlueSky accounts."""
    all_posts = []

    for handle in F1_ACCOUNTS:
        print(f"  📡 Fetching posts from @{handle}...")
        did = resolve_handle(handle)
        if not did:
            print(f"     ⚠ Could not resolve handle, skipping")
            continue

        feed = get_author_feed(did)
        for item in feed:
            parsed = parse_post(item)
            if parsed:
                all_posts.append(parsed)

        # Be nice to the API
        time.sleep(0.5)

    return all_posts


def collect_posts_from_search() -> list[dict]:
    """Search BlueSky for F1-related posts."""
    all_posts = []

    if not ENABLE_KEYWORD_SEARCH:
        return all_posts

    for keyword in F1_SEARCH_KEYWORDS:
        print(f"  🔍 Searching for '{keyword}'...")
        results = search_posts(keyword)
        for post_data in results:
            parsed = parse_post(post_data)
            if parsed:
                all_posts.append(parsed)
        time.sleep(0.5)

    return all_posts


def deduplicate_posts(posts: list[dict]) -> list[dict]:
    """Remove duplicate posts based on URI."""
    seen = set()
    unique = []
    for p in posts:
        uid = p["uri"]
        if uid not in seen:
            seen.add(uid)
            unique.append(p)
    return unique


def main():
    print("=" * 60)
    print("🏁 F1 BlueSky → Telegram Bot")
    print(f"   Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"   Lookback: {LOOKBACK_HOURS} hours")
    print(f"   Accounts: {len(F1_ACCOUNTS)}")
    print(f"   Keyword search: {'ON' if ENABLE_KEYWORD_SEARCH else 'OFF'}")
    print("=" * 60)

    # Validate config
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set. Add it to GitHub Secrets.")
        return
    if not TELEGRAM_CHANNEL_ID:
        print("❌ TELEGRAM_CHANNEL_ID not set. Add it to GitHub Secrets.")
        return

    # Load state
    state = load_state()
    sent_ids = set(state.get("sent_ids", []))
    print(f"📋 Previously sent: {len(sent_ids)} posts tracked")

    # Collect posts from all sources
    print("\n📡 Fetching from BlueSky accounts...")
    posts = collect_posts_from_accounts()

    print("\n🔍 Searching keywords...")
    posts.extend(collect_posts_from_search())

    # Deduplicate and sort by time (oldest first so channel reads chronologically)
    posts = deduplicate_posts(posts)
    posts.sort(key=lambda p: p["created_at"])

    print(f"\n📊 Found {len(posts)} posts within lookback window")

    # Filter out already-sent posts
    new_posts = []
    for p in posts:
        pid = post_id_hash(p["uri"])
        if pid not in sent_ids:
            new_posts.append(p)

    print(f"🆕 New posts to send: {len(new_posts)}")

    # Limit posts per run
    if len(new_posts) > MAX_POSTS_PER_RUN:
        print(f"⚠ Capping to {MAX_POSTS_PER_RUN} posts this run")
        new_posts = new_posts[:MAX_POSTS_PER_RUN]

    # Send to Telegram
    sent_count = 0
    for post in new_posts:
        print(f"\n  📤 Sending: @{post['handle']} — {post['text'][:60]}...")

        # Determine how many images we have
        photos = post["images"]
        external_thumb = post["external_thumb"]
        video_thumbnail = post.get("video_thumbnail", "")
        has_video = post.get("has_video", False)
        success = False

        if len(photos) > 1:
            # Multiple images — send as album
            message = format_telegram_message(post, as_caption=True)
            print(f"     📸 Sending album with {len(photos)} images...")
            success = send_telegram_album(message, photos)

            if not success:
                # Fallback: try sending just the first image
                print("     ⚠ Album failed, retrying with first image only...")
                success = send_telegram_message(message, photo_url=photos[0])

        elif len(photos) == 1:
            # Single image
            message = format_telegram_message(post, as_caption=True)
            success = send_telegram_message(message, photo_url=photos[0])

        elif has_video and video_thumbnail:
            # Video post — send thumbnail image with [Video] label in text
            message = format_telegram_message(post, as_caption=True)
            print("     🎬 Video post — sending thumbnail...")
            success = send_telegram_message(message, photo_url=video_thumbnail)

        elif has_video:
            # Video post but no thumbnail available — send text only
            message = format_telegram_message(post, as_caption=False)
            print("     🎬 Video post — no thumbnail, sending text only...")
            success = send_telegram_message(message)

        elif external_thumb:
            # External link thumbnail
            message = format_telegram_message(post, as_caption=True)
            success = send_telegram_message(message, photo_url=external_thumb)

        else:
            # No images at all — text only
            message = format_telegram_message(post, as_caption=False)
            success = send_telegram_message(message)

        if not success and (photos or external_thumb or video_thumbnail):
            # Last resort: send as plain text
            print("     ⚠ Retrying without any images...")
            message = format_telegram_message(post, as_caption=False)
            success = send_telegram_message(message)

        if success:
            sent_count += 1
            pid = post_id_hash(post["uri"])
            state["sent_ids"].append(pid)
            print("     ✅ Sent!")

        # Respect Telegram rate limits (20 msgs/min to same chat)
        time.sleep(3)

    # Save state
    save_state(state)

    print(f"\n{'=' * 60}")
    print(f"✅ Done! Sent {sent_count}/{len(new_posts)} posts to Telegram.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
