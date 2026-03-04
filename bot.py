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
    "f1.bsky.social",                  # Official F1
    # ── Journalists ──
    "chrismedlandf1.bsky.social",      # Chris Medland
    "willbuxton.bsky.social",          # Will Buxton
    "laurenceedmondson.bsky.social",   # Laurence Edmondson (ESPN)
    "lukesmithf1.bsky.social",         # Luke Smith
    # ── Media outlets ──
    "motorsport.bsky.social",          # Motorsport.com
    "the-race.bsky.social",            # The Race
    "planetf1.bsky.social",            # PlanetF1
    "autosport.bsky.social",           # Autosport
    "racefans.bsky.social",            # RaceFans
    "racingnews365.bsky.social",       # RacingNews365
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
            params={"actor": did, "limit": limit, "filter": "posts_no_replies"},
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
    handle = author.get("handle", "unknown")
    display_name = author.get("displayName", handle)

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
            thumb = img.get("thumb", "")
            if thumb:
                images.append(thumb)

    # Check for embedded links / external cards
    external_url = ""
    external_title = ""
    external_thumb = ""
    if "external" in embed_type:
        ext = embed.get("external", {})
        external_url = ext.get("uri", "")
        external_title = ext.get("title", "")
        external_thumb = ext.get("thumb", "")

    return {
        "uri": uri,
        "text": text,
        "handle": handle,
        "display_name": display_name,
        "created_at": created_at,
        "bsky_link": bsky_link,
        "images": images,
        "external_url": external_url,
        "external_title": external_title,
        "external_thumb": external_thumb,
    }


# ──────────────────────────────────────────────────────────────
#  Telegram posting
# ──────────────────────────────────────────────────────────────

def format_telegram_message(post: dict) -> str:
    """Format a BlueSky post into a nice Telegram message."""
    lines = []

    # Header with author
    lines.append(f"🏎 <b>{escape_html(post['display_name'])}</b>")
    lines.append(f"<i>@{escape_html(post['handle'])}</i>")
    lines.append("")

    # Post text
    lines.append(escape_html(post["text"]))

    # External link card (if present)
    if post["external_url"]:
        lines.append("")
        if post["external_title"]:
            lines.append(f'🔗 <a href="{post["external_url"]}">{escape_html(post["external_title"])}</a>')
        else:
            lines.append(f'🔗 <a href="{post["external_url"]}">Link</a>')

    # BlueSky source link
    if post["bsky_link"]:
        lines.append("")
        lines.append(f'<a href="{post["bsky_link"]}">View on BlueSky</a>')

    lines.append("\n#F1 #BlueSky")

    return "\n".join(lines)


def escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram's HTML parse mode."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def send_telegram_message(text: str, photo_url: str = "") -> bool:
    """Send a message (with optional photo) to the Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("  ❌ Telegram credentials not set!")
        return False

    base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    try:
        if photo_url:
            # Send as photo with caption
            caption = text[:1024]  # Telegram caption limit
            resp = requests.post(
                f"{base_url}/sendPhoto",
                json={
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "photo": photo_url,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
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

        message = format_telegram_message(post)

        # Try to send with image if available
        photo = ""
        if post["images"]:
            photo = post["images"][0]
        elif post["external_thumb"]:
            photo = post["external_thumb"]

        success = send_telegram_message(message, photo_url=photo)

        if success:
            sent_count += 1
            pid = post_id_hash(post["uri"])
            state["sent_ids"].append(pid)
            print("     ✅ Sent!")
        else:
            # If photo send fails, retry without photo
            if photo:
                print("     ⚠ Retrying without photo...")
                success = send_telegram_message(message)
                if success:
                    sent_count += 1
                    pid = post_id_hash(post["uri"])
                    state["sent_ids"].append(pid)
                    print("     ✅ Sent (text only)!")

        # Respect Telegram rate limits (20 msgs/min to same chat)
        time.sleep(3)

    # Save state
    save_state(state)

    print(f"\n{'=' * 60}")
    print(f"✅ Done! Sent {sent_count}/{len(new_posts)} posts to Telegram.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
