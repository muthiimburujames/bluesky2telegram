# 🏎 F1 BlueSky → Telegram Bot

A free, automated bot that monitors Formula 1 accounts on BlueSky and posts their content to your Telegram channel. Runs entirely on GitHub Actions — no server, no always-on computer, no costs.

## What it does

- Checks 11 F1 BlueSky accounts every 5 minutes and posts new content to your Telegram channel
- Renders rich text with clickable links and @mentions (not flat text)
- Sends full-quality images, multi-image albums, and video thumbnails
- Auto-categorizes posts as Breaking, Technical, Transfer, Race, Regulation, or News
- Detects self-reply threads so corrections and follow-ups aren't missed
- Skips reposts/boosts to avoid duplicates
- Detects when multiple accounts share the same article and only posts it once
- Adds inline buttons (View on BlueSky / Share) to every post
- Highlights popular posts with high engagement
- Truncates long posts at sentence boundaries instead of cutting mid-word
- Recovers automatically from errors by extending the lookback window on the next run
- Responds to /start and /sources commands when users message the bot directly
- Runs 100% free on GitHub Actions with a public repository (unlimited minutes)
- Remembers what it already sent — no duplicates across runs

## Pre-built F1 accounts monitored

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

> **Note:** Some handles above may not exist yet on BlueSky — the bot will simply skip accounts it can't find and continue with the rest. You can edit the list in `bot.py` or add more via GitHub settings (see Step 5).

## How posts look in your channel

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
│ [View on BlueSky] [Share]            │
└──────────────────────────────────────┘
```

Links and @mentions in the post text are clickable. Posts with videos show a thumbnail with a "watch on BlueSky" link. Multi-image posts display as swipeable Telegram albums.

## Post categories

The bot automatically tags posts based on content:

| Tag | Triggers on |
|-----|-------------|
| **[Breaking]** | "breaking", "confirmed", "just in", "announced" |
| **[Technical]** | "aero", "downforce", "floor", "sidepod", "upgrade", "diffuser", etc. |
| **[Transfer]** | "rumour", "reportedly", "set to join", "driver market", "contract extension" |
| **[Race]** | "wins grand prix", "podium", "race result", "chequered flag" |
| **[Regulation]** | "FIA", "regulation", "penalty", "stewards", "cost cap" |

General news posts have no tag. Posts with 50+ likes also get a **[Popular]** label.

---

## Setup guide (no coding needed!)

### Step 1: Create your Telegram Bot

1. Open **Telegram** and search for **@BotFather** (look for the blue checkmark)
2. Send `/start`, then send `/newbot`
3. Choose a display name (e.g., `F1 BlueSky News`)
4. Choose a username ending in `bot` (e.g., `F1BlueSkyNews_bot`)
5. BotFather replies with a **token** like `123456789:ABCdef...` — **copy and save it!**
6. Optionally, while in BotFather: send `/mybots` → select your bot → **Edit Bot** → **Edit Botpic** → send an F1-themed image for the bot's profile picture

### Step 2: Add the bot to your Telegram Channel

**Do this from Telegram Desktop or web.telegram.org** (mobile can be unreliable for this step):

1. Open your Telegram channel
2. Tap the channel name → **Administrators** → **Add Administrator**
3. Search for your bot's **username** (the `@something_bot` name, not the display name)
4. **Tap on the bot** when it appears in search results
5. Grant it **"Post Messages"** permission → **Save**
6. Go back to the Administrators list and confirm your bot is listed there

> **Important:** Simply searching for the bot is not enough — you must tap it, grant permission, and save.

### Step 3: Find your Channel ID

- **Public channel:** Your ID is `@YourChannelName` (e.g., `@MyF1News`)
- **Private channel:** Forward any message from your channel to **@MyChatInfoBot** in Telegram — it replies with the numeric ID (starts with `-100...`)

### Step 4: Set up the GitHub repository

1. **Create a GitHub account** at [github.com](https://github.com) if you don't have one (free)
2. Click the green **"New"** button to create a new repository
3. Name it whatever you like (e.g., `f1-bluesky-telegram-bot`)
4. Set it to **Public** (required for unlimited free GitHub Actions minutes)
5. Check **"Add a README file"** and click **Create repository**
6. **Create each file directly on GitHub** (easiest method):
   - Click **"Add file"** → **"Create new file"**
   - Type the filename in the box (for nested folders, type the path with slashes, e.g., `.github/workflows/bluesky_monitor.yml` — GitHub creates the folders automatically)
   - Paste the file contents → click **"Commit changes"**
   - Repeat for all files

   The folder structure should look like this:
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

> **Tip:** Files starting with `.` (like `.github`) are hidden on your computer. Creating them directly on GitHub avoids this issue entirely.

### Step 5: Add your secrets

Your Telegram credentials need to be stored securely as GitHub Secrets:

1. Go to your repository on GitHub
2. Click **Settings** (tab at the top)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **"New repository secret"** and add these two secrets:

   | Name | Value |
   |------|-------|
   | `TELEGRAM_BOT_TOKEN` | Your bot token from Step 1 (e.g., `123456789:ABCdef...`) |
   | `TELEGRAM_CHANNEL_ID` | Your channel ID from Step 3 (e.g., `@MyF1News` or `-1001234567890`) |

5. (Optional) Click the **"Variables"** tab and add any of these to customize:

   | Name | Default | What it does |
   |------|---------|-------------|
   | `LOOKBACK_HOURS` | `2` | How many hours back to check for posts |
   | `MAX_POSTS_PER_RUN` | `10` | Max posts sent per 5-minute cycle |
   | `POPULAR_THRESHOLD` | `50` | Minimum likes for a post to get the [Popular] tag |
   | `EXTRA_BSKY_ACCOUNTS` | *(empty)* | Extra BlueSky handles, comma-separated |

> **Security note:** GitHub Secrets are encrypted and never visible in logs, code, or to anyone viewing the repo — even on a public repository. This is how thousands of open-source bots operate safely.

### Step 6: Verify the bot is connected

Before enabling automation, test the connection. Open this URL in your browser (replace the placeholders):

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage?chat_id=<YOUR_CHANNEL_ID>&text=Test
```

If you see `"ok": true` and "Test" appears in your channel, everything is connected.

### Step 7: Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. You should see the **"F1 BlueSky to Telegram"** workflow
3. If GitHub asks you to enable workflows, click the green button
4. To test immediately: click the workflow name → **"Run workflow"** → **"Run workflow"**
5. Watch the run — click on it to see live logs

### 🎉 That's it!

The bot will now automatically run every 5 minutes, check all configured BlueSky accounts, and post new F1 content to your Telegram channel.

---

## Customizing the bot

### Adding or removing BlueSky accounts

**Easy way (no file editing):** Go to Settings → Secrets and variables → Actions → Variables tab. Add or edit `EXTRA_BSKY_ACCOUNTS` with comma-separated handles:
```
user1.bsky.social,user2.bsky.social
```

**Direct way:** Edit `bot.py` on GitHub — click the file → pencil icon → edit the `F1_ACCOUNTS` list → commit.

### Changing the refresh rate

Edit `.github/workflows/bluesky_monitor.yml` on GitHub. Find the `cron` line and change it:

- Every 5 minutes: `'*/5 * * * *'` (default — requires public repo)
- Every 10 minutes: `'*/10 * * * *'`
- Every 30 minutes: `'*/30 * * * *'` (works fine on private repos)

> **Free tier note:** Public repos get unlimited GitHub Actions minutes. Private repos get 2,000 minutes/month. At 5-minute intervals on a private repo, you would exceed the limit — keep it public or use a longer interval.

### Adjusting the Popular post threshold

By default, posts with 50+ likes get a **[Popular]** label. Change this by adding `POPULAR_THRESHOLD` as a variable in Settings → Secrets and variables → Actions → Variables with your preferred number.

### Bot commands

When users message your bot directly, it responds to two commands:

- `/start` — Shows a welcome message explaining how the bot works and what the categories mean
- `/sources` — Lists all monitored BlueSky accounts with links to their profiles

These commands are set up automatically by the bot. The bot's description and short bio in Telegram are also configured automatically on each run.

---

## Troubleshooting

### The bot didn't post anything

1. Check the **Actions** tab → click the latest run → expand **"Run the bot"** → read the logs
2. Verify your secrets are set correctly (Settings → Secrets — note you can't view them after saving, only replace)
3. Make sure the bot is an **administrator** in your Telegram channel with "Post Messages" permission
4. Run the browser test from Step 6 to verify the connection

### "Forbidden: bot is not a member of the channel chat"

The bot isn't properly added as an admin. Re-do Step 2 from **Telegram Desktop or web.telegram.org** — mobile sometimes doesn't save permissions properly. After adding, verify the bot appears in the Administrators list.

### "Could not resolve handle"

That BlueSky account doesn't exist or changed its handle. The bot skips it and continues with the others. Edit the account list to fix or remove it.

### The scheduled workflow isn't triggering automatically

This is a known GitHub Actions issue. Push any small commit to the repo (even editing the README) to resync the schedule. If it persists, manually trigger one run from the Actions tab — this usually kickstarts automatic scheduling.

> **Note:** GitHub Actions does not guarantee exact cron timing. Runs scheduled every 5 minutes may occasionally be delayed by 5-15 minutes during high-load periods. This is normal and doesn't cause missed posts — the lookback window covers the gap.

### Duplicate posts appearing

The bot has three layers of deduplication (post URI tracking, repost/boost skipping, and duplicate link detection). If duplicates still appear, delete `state/sent_posts.json` on GitHub — it will be recreated fresh on the next run.

### I want to stop the bot

Go to the **Actions** tab → click the workflow → click the **"..."** menu → **"Disable workflow"**. Re-enable anytime.

---

## How it works

Every 5 minutes, GitHub's servers run your bot for free. The bot:

1. Reads each BlueSky account's recent posts using BlueSky's free public API (no authentication needed)
2. Filters for posts from the last 2 hours
3. Skips reposts/boosts and detects when multiple accounts share the same article
4. Converts BlueSky's rich text annotations into clickable Telegram HTML (links and @mentions)
5. Auto-categorizes each post based on keyword matching
6. Checks which posts it already sent (tracked in `state/sent_posts.json`)
7. Sends new posts to Telegram with images, albums, video thumbnails, and inline buttons
8. Saves the updated state back to the repository
9. Responds to any pending /start or /sources commands from users

If a run fails due to a network error or API timeout, the next run automatically extends its lookback window to catch up on anything that was missed.

No servers to pay for, no computer to leave on, no accounts to manage beyond GitHub and Telegram.

---

## License

MIT — do whatever you want with it.
