# 🏎 F1 Multi-Source → Telegram Bot

A free, automated bot that aggregates Formula 1 content from multiple sources — BlueSky, Reddit, RSS feeds, YouTube, and FIA official documents — and posts it to your Telegram channel. Runs entirely on GitHub Actions with an external scheduler for reliable 5-minute polling. No server, no always-on computer, no costs.

## What it does

- Aggregates F1 content from **5 different source types**: BlueSky accounts, Reddit, RSS feeds, YouTube channels, and FIA official documents
- Checks for new content every **5 minutes** via an external scheduler (cron-job.org)
- Renders **rich text** with clickable links and @mentions from BlueSky posts
- Sends **full-quality images**, multi-image albums, and video thumbnails
- **Auto-categorizes** posts as Breaking, Technical, Transfer, Race, Regulation, or News
- Detects **self-reply threads** so corrections and follow-ups aren't missed
- **Skips reposts/boosts** from BlueSky to avoid duplicates
- **Duplicate link detection** across all sources — if Reddit and an RSS feed share the same article, it's posted only once
- Adds **inline buttons** (View on BlueSky / View on Reddit / Read Article / View Document / Share) to every post
- **Highlights popular** BlueSky posts with high engagement
- **Smart truncation** at sentence boundaries instead of cutting mid-word
- **Error recovery** — if a run fails, the next run extends its lookback window to catch up
- Responds to **/start** and **/sources** commands when users message the bot directly
- Clean Reddit posts with **no redundant link previews**
- Runs **100% free** on GitHub Actions (public repo) + cron-job.org
- Remembers what it already sent — **no duplicates** across runs

## Content sources

### BlueSky accounts
Monitors configurable F1 journalists and media outlets on BlueSky. Includes rich text rendering (clickable links and @mentions), image albums, video thumbnails, repost filtering, and thread detection.

### Reddit r/formula1
Fetches hot and top posts from r/formula1 (and any other subreddits you configure) via RSS feeds. Reddit is where breaking news, insider leaks, and community discussion surface fastest.

### RSS feeds
Monitors any RSS/Atom feed — F1 news websites, newsletters, and more. Supports images from media enclosures and thumbnails.

### YouTube channels
YouTube channels have built-in RSS feeds. When configured, new video uploads appear in your channel with the title, description, and a link to the video.

### FIA official documents
Scrapes the FIA website for steward decisions, technical directives, penalty notices, and other official documents during race weekends. Auto-categorized as "Regulation."

## Pre-built BlueSky accounts

| Account | Who |
|---------|-----|
| `f1.bsky.social` | Official F1 |
| `chrismedlandf1.bsky.social` | Chris Medland |
| `willbuxton.bsky.social` | Will Buxton |
| `laurenceedmondson.bsky.social` | Laurence Edmondson (ESPN) |
| `lukesmithf1.bsky.social` | Luke Smith |
| `motorsport.bsky.social` | Motorsport.com |
| `the-race.bsky.social` | The Race |
| `planetf1.bsky.social` | PlanetF1 |
| `autosport.bsky.social` | Autosport |
| `racefans.bsky.social` | RaceFans |
| `racingnews365.bsky.social` | RacingNews365 |

> **Note:** Some handles may not exist yet on BlueSky — the bot skips accounts it can't find and continues with the rest. Edit the list in `bot.py` or add more via the `EXTRA_BSKY_ACCOUNTS` variable.

## How posts look in your channel

### BlueSky post (with image)
```
┌──────────────────────────────────────┐
│           [IMAGE / ALBUM]            │
├──────────────────────────────────────┤
│ [Technical] [Popular - 89 likes]     │
│                                      │
│ New floor upgrade for Ferrari shows  │
│ a revised diffuser edge. Analysis    │
│ by @scarbstech at the-race.com/...  │
│                                      │
│ @scarbstech.bsky.social             │
│ Source: BlueSky                      │
│                                      │
│ [View on BlueSky]  [Share]           │
└──────────────────────────────────────┘
```

### Reddit post (clean, no preview card)
```
┌──────────────────────────────────────┐
│                                      │
│ Verstappen penalty controversy —     │
│ stewards release full reasoning      │
│                                      │
│ @r/formula1                          │
│ Source: Reddit                       │
│                                      │
│ [View on Reddit]  [Share]            │
└──────────────────────────────────────┘
```

### FIA document
```
┌──────────────────────────────────────┐
│ [Regulation]                         │
│                                      │
│ FIA Document: Doc 42 - Decision -    │
│ Car 1 - Unsafe release              │
│                                      │
│ @FIA                                 │
│ Source: FIA                          │
│                                      │
│ [View Document]  [Share]             │
└──────────────────────────────────────┘
```

## Post categories

The bot automatically tags posts based on content:

| Tag | Triggers on |
|-----|-------------|
| **[Breaking]** | "breaking", "confirmed", "just in", "announced" |
| **[Technical]** | "aero", "downforce", "floor", "sidepod", "upgrade", "diffuser", etc. |
| **[Transfer]** | "rumour", "reportedly", "set to join", "driver market", "contract extension" |
| **[Race]** | "wins grand prix", "podium", "race result", "chequered flag" |
| **[Regulation]** | "FIA", "regulation", "penalty", "stewards", "cost cap" |

General news posts have no tag. BlueSky posts with 50+ likes also get a **[Popular]** label.

---

## Setup guide (no coding needed!)

### Step 1: Create your Telegram Bot

1. Open **Telegram** and search for **@BotFather** (look for the blue checkmark)
2. Send `/start`, then send `/newbot`
3. Choose a display name (e.g., `F1 News`)
4. Choose a username ending in `bot` (e.g., `F1MultiNews_bot`)
5. BotFather replies with a **token** like `123456789:ABCdef...` — **copy and save it!**
6. Optionally: send `/mybots` → select your bot → **Edit Bot** → **Edit Botpic** → send an F1-themed image

### Step 2: Add the bot to your Telegram Channel

**Do this from Telegram Desktop or web.telegram.org** (mobile can be unreliable):

1. Open your channel → tap the channel name → **Administrators** → **Add Administrator**
2. Search for your bot's **username** (the `@something_bot` name)
3. **Tap the bot**, grant **"Post Messages"** permission → **Save**
4. Verify the bot appears in the Administrators list

### Step 3: Find your Channel ID

- **Public channel:** Your ID is `@YourChannelName`
- **Private channel:** Forward any message from your channel to **@MyChatInfoBot** — it replies with the numeric ID

### Step 4: Verify the connection

Open this URL in your browser (replace the placeholders):
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage?chat_id=<YOUR_CHANNEL_ID>&text=Test
```
If you see `"ok": true` and "Test" appears in your channel, everything is connected.

### Step 5: Set up the GitHub repository

1. **Create a GitHub account** at [github.com](https://github.com) if you don't have one
2. Create a **new public repository** (public = unlimited free GitHub Actions minutes)
3. **Create each file directly on GitHub**: click **"Add file"** → **"Create new file"** → type the path (e.g., `.github/workflows/bluesky_monitor.yml`) → paste contents → commit
4. The folder structure should look like this:
   ```
   your-repo/
   ├── .github/
   │   └── workflows/
   │       └── bluesky_monitor.yml
   ├── state/
   │   └── sent_posts.json
   ├── bot.py
   ├── requirements.txt
   ├── .gitignore
   └── README.md
   ```

### Step 6: Add your secrets and variables

Go to your repo → **Settings** → **Secrets and variables** → **Actions**.

**Secrets** (click "New repository secret"):

| Name | Value |
|------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from Step 1 |
| `TELEGRAM_CHANNEL_ID` | Your channel ID from Step 3 |

**Variables** (click the "Variables" tab → "New repository variable"):

| Name | Default | What it does |
|------|---------|-------------|
| `LOOKBACK_HOURS` | `2` | How many hours back to check for posts |
| `MAX_POSTS_PER_RUN` | `10` | Max posts sent per cycle |
| `POPULAR_THRESHOLD` | `50` | Minimum likes for BlueSky [Popular] tag |
| `EXTRA_BSKY_ACCOUNTS` | *(empty)* | Extra BlueSky handles, comma-separated |
| `RSS_FEEDS` | *(empty)* | RSS feed URLs, comma-separated (see below) |
| `REDDIT_SUBREDDITS` | `formula1` | Subreddits to monitor, comma-separated |
| `REDDIT_MIN_SCORE` | `100` | Min upvotes (note: only works if Reddit serves score data) |
| `FIA_DOCUMENTS` | `true` | Set to `false` to disable FIA document monitoring |

> **Security note:** GitHub Secrets are encrypted and never visible in logs or to anyone viewing the repo — even on a public repository.

### Step 7: Set up the external scheduler (for reliable 5-min polling)

GitHub Actions' built-in cron is unreliable for intervals under 15 minutes. We use **cron-job.org** (free) to trigger the workflow reliably.

1. Create a **GitHub Personal Access Token**: go to [github.com/settings/tokens](https://github.com/settings/tokens) → **"Generate new token"** → **Fine-grained** → select your repo → set **Actions** permission to **Read and write** → generate and copy the token
2. Sign up at [cron-job.org](https://cron-job.org) (free)
3. Create a new cronjob with these settings:

| Field | Value |
|-------|-------|
| **Title** | F1 Bot Trigger |
| **URL** | `https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/actions/workflows/bluesky_monitor.yml/dispatches` |
| **Schedule** | Every 5 minutes |
| **Request method** | POST |

4. Add these **custom headers**:

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer github_pat_YOUR_TOKEN_HERE` |
| `Accept` | `application/vnd.github+json` |
| `Content-Type` | `application/json` |

5. Set the **request body** to: `{"ref":"main"}`
6. Save and enable

The GitHub workflow also has a 30-minute backup cron in case cron-job.org goes down.

> **Note:** Your GitHub token has an expiration date. Set a calendar reminder to renew it before it expires.

### Step 8: Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. Enable workflows if prompted
3. To test immediately: click the workflow → **"Run workflow"** → **"Run workflow"**

### 🎉 That's it!

The bot will now automatically check all sources every 5 minutes and post new F1 content to your Telegram channel.

---

## Adding content sources

### Adding RSS feeds

Add feed URLs to the `RSS_FEEDS` variable (comma-separated). Good F1 feeds:

```
https://www.motorsport.com/rss/f1/news/,https://www.autosport.com/rss/f1/news/,https://www.planetf1.com/ps-rss,https://www.the-race.com/category/formula-1/feed/,https://www.racefans.net/feed/,https://feeds.bbci.co.uk/sport/formula1/rss.xml,https://racingnews365.com/feed/news.xml
```

### Adding YouTube channels

YouTube channels have built-in RSS feeds. Find the channel ID (from the channel URL or About page), then add to `RSS_FEEDS`:

```
https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID_HERE
```

Useful F1 channel IDs:
- **Chain Bear**: `UCB_qr75-ydFVKSF9s5xFvHw`
- **Peter Windsor**: `UC_ULpnIIQBPSx55F5GwjRhA`
- **Josh Revell**: `UCPwy2q7BNjdLYu1kM_OEJVw`

### Adding Reddit subreddits

Change the `REDDIT_SUBREDDITS` variable (comma-separated):
```
formula1,F1Technical,FormulaFeeders
```

### Adding BlueSky accounts

Change the `EXTRA_BSKY_ACCOUNTS` variable (comma-separated):
```
user1.bsky.social,user2.bsky.social
```

Or edit `bot.py` directly on GitHub to modify the `F1_ACCOUNTS` list.

### Disabling FIA documents

Set the `FIA_DOCUMENTS` variable to `false`.

---

## Bot commands

When users message your bot directly, it responds to:

- `/start` — Welcome message explaining how the bot works and what categories mean
- `/sources` — Lists all monitored BlueSky accounts with links

The bot's description and profile are configured automatically.

---

## Troubleshooting

### The bot didn't post anything

1. Check **Actions** tab → latest run → expand **"Run the bot"** → read the logs
2. Verify secrets are set correctly (Settings → Secrets)
3. Make sure the bot is an **administrator** in your channel with "Post Messages" permission
4. Run the browser test from Step 4

### "Forbidden: bot is not a member of the channel chat"

Re-do Step 2 from **Telegram Desktop or web.telegram.org**. After adding, verify the bot appears in the Administrators list.

### "Could not resolve handle"

That BlueSky account doesn't exist or changed its handle. The bot skips it and continues.

### Reddit returns 403

Reddit blocks JSON API requests from cloud servers. The bot uses RSS feeds as a workaround, which are more permissive. If RSS also fails, Reddit may be temporarily blocking the GitHub Actions IP range — it will usually resolve on the next run.

### The scheduled workflow isn't triggering

If using cron-job.org: check the job's execution history for HTTP 204 (success) or errors. If using GitHub's backup cron: push a small commit to resync the schedule.

### Duplicate posts appearing

The bot has three deduplication layers (post ID tracking, repost skipping, duplicate link detection). If duplicates still appear, delete `state/sent_posts.json` on GitHub — it will be recreated.

### Git push errors in the logs

If two runs overlap, the second may fail to push state. The workflow handles this gracefully with `git pull --rebase`. The state re-syncs on the next run — no posts are lost.

### I want to stop the bot

Go to **Actions** tab → click the workflow → **"..."** menu → **"Disable workflow"**. Also disable the cron-job.org job. Re-enable anytime.

---

## How it works

Every 5 minutes, cron-job.org triggers your GitHub Actions workflow. The bot:

1. Fetches recent posts from all configured BlueSky accounts via the public API
2. Fetches hot/top posts from Reddit subreddits via RSS feeds
3. Checks all configured RSS feeds (including YouTube channels)
4. Scrapes the FIA documents page for new official documents
5. Skips reposts, deduplicates by post ID and by shared URLs across all sources
6. Converts BlueSky rich text annotations into clickable Telegram HTML
7. Auto-categorizes each post based on keyword matching
8. Sends new posts to Telegram with images, albums, video thumbnails, and inline buttons
9. Saves state back to the repository (which posts were sent, which links were seen)
10. Responds to any pending /start or /sources commands

If a run fails, the next run doubles its lookback window to catch up automatically.

No servers to pay for, no computer to leave on. Total cost: zero.

---

## License

MIT — do whatever you want with it.
