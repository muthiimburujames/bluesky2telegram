# 🏎 F1 BlueSky → Telegram Bot

A free, zero-code bot that automatically monitors Formula 1 accounts on BlueSky and posts their content to your Telegram channel. Runs entirely on GitHub Actions — no server, no always-on computer, no costs.

## What it does

- Checks 10+ F1 BlueSky accounts every 30 minutes
- Sends new posts to your Telegram channel with images and links
- Remembers what it already sent (no duplicates)
- Runs 100% free on GitHub Actions (you get 2,000 free minutes/month)
- Optional: searches BlueSky for F1 keywords too

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

> **Note:** Some handles above may not exist yet on BlueSky — the bot will simply skip accounts it can't find and continue with the rest. You can freely edit the list in `bot.py` or add more via GitHub settings (see Step 5).

---

## Setup guide (no coding needed!)

### Step 1: Create your Telegram Bot

You need a Telegram bot to post messages to your channel.

1. Open **Telegram** and search for **@BotFather**
2. Send `/start`, then send `/newbot`
3. Choose a display name (e.g., `F1 BlueSky News`)
4. Choose a username ending in `bot` (e.g., `F1BlueSkyNews_bot`)
5. BotFather replies with a **token** like `123456789:ABCdef...` — **copy and save it!**

### Step 2: Add the bot to your Telegram Channel

1. Open your Telegram channel
2. Tap the channel name → **Administrators** → **Add Administrator**
3. Search for your bot's username (e.g., `@F1BlueSkyNews_bot`)
4. Grant it **"Post Messages"** permission → Save

### Step 3: Find your Channel ID

- **Public channel:** Your ID is `@YourChannelName` (e.g., `@MyF1News`)
- **Private channel:** Forward any message from your channel to **@MyChatInfoBot** in Telegram — it replies with the numeric ID (starts with `-100...`)

### Step 4: Set up the GitHub repository

1. **Create a GitHub account** at [github.com](https://github.com) if you don't have one (free)
2. Click the green **"New"** button to create a new repository
3. Name it `f1-bluesky-telegram-bot` (or anything you like)
4. Set it to **Private** (recommended, since it will contain bot activity logs)
5. Check **"Add a README file"** and click **Create repository**
6. **Upload the bot files:**
   - On your new repo page, click **"Add file"** → **"Upload files"**
   - Drag and drop ALL the files and folders from this project (make sure the `.github` folder and `state` folder are included)
   - Click **"Commit changes"**
   
   > **Important:** Make sure the folder structure looks like this in your repo:
   > ```
   > your-repo/
   > ├── .github/
   > │   └── workflows/
   > │       └── bluesky_monitor.yml
   > ├── state/
   > │   └── sent_posts.json
   > ├── bot.py
   > ├── requirements.txt
   > ├── .gitignore
   > └── README.md
   > ```

### Step 5: Add your secrets (the important part!)

Your Telegram bot token and channel ID need to be stored securely as GitHub Secrets:

1. Go to your repository on GitHub
2. Click **Settings** (tab at the top)
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **"New repository secret"** and add these two secrets:

   | Name | Value |
   |------|-------|
   | `TELEGRAM_BOT_TOKEN` | Your bot token from Step 1 (e.g., `123456789:ABCdef...`) |
   | `TELEGRAM_CHANNEL_ID` | Your channel ID from Step 3 (e.g., `@MyF1News` or `-1001234567890`) |

5. (Optional) Click the **"Variables"** tab and add these to customize behavior:

   | Name | Default | What it does |
   |------|---------|-------------|
   | `LOOKBACK_HOURS` | `2` | How many hours back to check for posts |
   | `MAX_POSTS_PER_RUN` | `10` | Max posts sent per 30-minute cycle |
   | `ENABLE_KEYWORD_SEARCH` | `false` | Set to `true` to also search BlueSky for F1 keywords |
   | `EXTRA_BSKY_ACCOUNTS` | *(empty)* | Extra BlueSky handles, comma-separated |

### Step 6: Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. You should see the **"F1 BlueSky to Telegram"** workflow listed
3. If GitHub asks you to enable workflows, click the green button to enable them
4. To test it right now: click on the workflow name → **"Run workflow"** → **"Run workflow"** (green button)
5. Watch the run — click on it to see live logs!

### 🎉 That's it!

The bot will now automatically run every 30 minutes, check all the F1 BlueSky accounts, and post new content to your Telegram channel. You don't need to do anything else — it's fully automated.

---

## Customizing the bot

### Adding or removing BlueSky accounts

**Easy way (no file editing):** Go to your repo's **Settings** → **Secrets and variables** → **Actions** → **Variables** tab. Add or edit `EXTRA_BSKY_ACCOUNTS` with comma-separated handles:
```
user1.bsky.social,user2.bsky.social,user3.bsky.social
```

**Direct way:** Edit `bot.py` on GitHub — click the file → pencil icon → edit the `F1_ACCOUNTS` list → commit.

### Changing the schedule

Edit `.github/workflows/bluesky_monitor.yml` on GitHub. Find the `cron` line and change it:

- Every 30 minutes: `'*/30 * * * *'` (default)
- Every hour: `'0 * * * *'`
- Every 15 minutes: `'*/15 * * * *'` (uses more free minutes)

> **Free tier math:** 2,000 free minutes/month ÷ ~0.5 minutes per run = ~4,000 runs possible. Running every 30 min = ~1,440 runs/month. You have plenty of headroom.

### Enabling keyword search

Set the `ENABLE_KEYWORD_SEARCH` variable to `true` in **Settings** → **Secrets and variables** → **Actions** → **Variables**. This makes the bot also search BlueSky for general F1 keywords, which finds posts from accounts not in your follow list.

---

## Troubleshooting

### The bot didn't post anything

1. Check the **Actions** tab → click the latest run → read the logs
2. Verify your secrets are set correctly (Settings → Secrets)
3. Make sure the bot is an **administrator** in your Telegram channel
4. Check that the BlueSky accounts actually have recent posts

### I see "Could not resolve handle"

That BlueSky account doesn't exist or changed its handle. The bot will skip it and continue with others. Edit the account list to fix or remove it.

### I'm getting duplicate posts

This shouldn't happen, but if it does: delete the `state/sent_posts.json` file on GitHub (it will be recreated). Some duplicates may appear on the very first run.

### The Actions workflow isn't running

Go to **Actions** tab and make sure workflows are enabled. GitHub may disable scheduled workflows on repos with no recent activity — just visit the repo or trigger a manual run to re-enable.

### I want to stop the bot

Go to **Actions** tab → click the workflow → click the **"..."** menu → **"Disable workflow"**. You can re-enable it anytime.

---

## How it works (the simple version)

Every 30 minutes, GitHub's servers wake up your bot for free. The bot:

1. Reads each BlueSky account's recent posts using BlueSky's free public API
2. Filters for posts from the last 2 hours
3. Checks which ones it already sent (tracked in `state/sent_posts.json`)
4. Sends new posts to your Telegram channel with images and links
5. Saves the updated list of sent posts back to the repository

No servers to pay for, no computer to leave on, no accounts to manage beyond GitHub and Telegram.

---

## License

MIT — do whatever you want with it.
