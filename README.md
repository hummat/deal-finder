# deal-finder

Minimal deal finder / notifier for Kleinanzeigen search results.

The code is structured so that `deal_finder/kleinanzeigen.py` acts as a plugin for one source (Kleinanzeigen). Additional sources (e.g. Amazon, eBay, etc.) can be added later as separate modules.

## Current capabilities

- Scrapes Kleinanzeigen search results for one or more search terms.
- Filters by a configurable price range and a simple title blacklist to avoid obvious full-PC bundles.
- Keeps a cache of already-notified listing URLs in `~/.cache/kleinanzeigen_seen.json`.
- Sends notifications for *new* listings via:
  - email (through SMTP), and/or
  - ntfy (HTTP push, one short notification per listing).

Run `kleinanzeigen.py` directly from the repo, or use the installed console script `check-kleinanzeigen-cpus`.

## Usage

From the project root, you must provide at least one search term. This prints all matching listings once and exits:

```bash
python3 kleinanzeigen.py "ryzen 9 5900x"
```

To enable notifications (email + ntfy, depending on environment variables), just add `--notify`:

```bash
python3 kleinanzeigen.py "ryzen 9 5900x" --notify
```

You can disable individual channels:

```bash
python3 kleinanzeigen.py --notify --no-email   # ntfy only
python3 kleinanzeigen.py --notify --no-ntfy    # email only
```

If installed as a package, you can also use the console script:

```bash
check-kleinanzeigen-cpus --notify
```

### Custom search terms, price filters, blacklist, and cache control

Search terms are positional arguments; price limits, blacklist tweaks, and cache control are optional flags:

- `<search-term> ...` – one or more search term strings (required). Each term can optionally include:
  - per-term price range as `TERM:MIN` or `TERM:MIN-MAX`, and/or
  - multiple variants separated by `|` (e.g. `term-en|term-de|1234:MIN-MAX`).
- `--min-price` – minimum price in EUR (optional)
- `--max-price` – maximum price in EUR (optional)
- `--blacklist` – additional case-insensitive substrings to blacklist in titles (can be repeated)
- `--clear-seen` – clear the cache of already-notified listings before this run

Examples:

```bash
# Single search term, no price filter
python3 kleinanzeigen.py "ryzen 9 5900x"

# Multiple terms and a narrower price range
python3 kleinanzeigen.py \
  "ryzen 7 5800x3d" "ryzen 9 5900x" \
  --min-price 180 --max-price 260 \
  --notify --no-email

# Per-term price ranges (overriding global min/max for that term)
python3 kleinanzeigen.py \
  "ryzen 7 5800x3d:180-260" \
  "ryzen 9 5900x:200-320" \
  --notify

# Multiple variants for one logical search (e.g. LEGO set title in English/German and set number)
python3 kleinanzeigen.py \
  "lego hogwarts castle|lego schloss hogwarts|75954:40-80" \
  --notify

# Add extra blacklist hints (on top of built-in heuristics)
python3 kleinanzeigen.py \
  "ryzen 7 5800x3d" \
  --min-price 150 --max-price 300 \
  --blacklist "komplettsystem" --blacklist "fertig pc"

# Rerun notifications from scratch (clear seen-cache first)
python3 kleinanzeigen.py \
  "ryzen 7 5800x3d" \
  --min-price 150 --max-price 300 \
  --clear-seen --notify
```

## Environment configuration

### Email (SMTP)

The following environment variables control email notifications:

- `DEAL_NOTIFIER_EMAIL_FROM` – sender address (required for email).
- `DEAL_NOTIFIER_EMAIL_TO` – recipient address (required).
- `DEAL_NOTIFIER_SMTP_HOST` – SMTP host (default: `localhost`).
- `DEAL_NOTIFIER_SMTP_PORT` – SMTP port (default: `25`).
- `DEAL_NOTIFIER_SMTP_USER` – username (optional).
- `DEAL_NOTIFIER_SMTP_PASSWORD` – password (optional).
- `DEAL_NOTIFIER_SMTP_STARTTLS` – set to `1` to use STARTTLS (default: no TLS).

If `FROM` or `TO` is missing, email is skipped with a warning.

### ntfy

Use either:

- `DEAL_NOTIFIER_NTFY_URL` – full ntfy URL (e.g. `https://ntfy.sh/your-topic`), or
- `DEAL_NOTIFIER_NTFY_TOPIC` – topic name; the code will use `https://ntfy.sh/<topic>`.

If neither is set, ntfy notifications are skipped with a warning.

Each matching listing results in a short ntfy push:

- Title: `"<price> € <truncated title>"` (80 chars max)
- Body: the Kleinanzeigen listing URL

## Scheduling

### Cron (simple)

For frequent checks with minimal latency, an example cron entry:

```cron
*/5 * * * * /usr/bin/env python3 /path/to/kleinanzeigen.py \
  "ryzen 7 5700x3d" "ryzen 7 5800x3d" \
  --min-price 150 --max-price 300 \
  --notify >> /var/log/kleinanzeigen_cpus.log 2>&1
```

Adjust the interval, path, search terms, and flags as needed.

### systemd user timer (recommended)

You can run deal-finder as a user-level systemd service and timer so it survives logouts and has per-unit logs.

1. Create an env file (e.g. `~/.config/deal-finder.env`) with your notification settings:

```bash
export DEAL_NOTIFIER_EMAIL_FROM="you@mailbox.org"
export DEAL_NOTIFIER_EMAIL_TO="you@mailbox.org"
export DEAL_NOTIFIER_SMTP_HOST="smtp.mailbox.org"
export DEAL_NOTIFIER_SMTP_PORT="587"
export DEAL_NOTIFIER_SMTP_USER="you@mailbox.org"
export DEAL_NOTIFIER_SMTP_PASSWORD="your-mailbox-password-or-app-pw"
export DEAL_NOTIFIER_SMTP_STARTTLS="1"

export DEAL_NOTIFIER_NTFY_TOPIC="kleinanzeigen-12345-67890"
```

2. User service unit (example, in `~/.config/systemd/user/deal-finder.service`).
   Do **not** enable this unit directly; the timer will start it.

```ini
[Unit]
Description=Kleinanzeigen deal finder notifier

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash -lc '\
  if [ -f "$HOME/.config/deal-finder.env" ]; then \
    source "$HOME/.config/deal-finder.env"; \
  fi; \
  cd "$HOME" && \
  python deal_finder/kleinanzeigen.py \
    "ryzen 7 5700x3d" "ryzen 7 5800x3d" \
    --min-price 150 --max-price 300 \
    --notify \
'
```

3. User timer unit (example, in `~/.config/systemd/user/deal-finder.timer`):

```ini
[Unit]
Description=Run Kleinanzeigen deal finder periodically

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=default.target
```

4. Reload systemd, enable the timer (not the service), and start it immediately:

```bash
systemctl --user daemon-reload
systemctl --user enable --now deal-finder.timer
```

Whenever you change the `deal-finder.service` or `deal-finder.timer` unit file, reload and restart so systemd picks up the new definition:

```bash
systemctl --user daemon-reload
systemctl --user restart deal-finder.timer      # for schedule/unit changes
systemctl --user start deal-finder.service      # optional: run a search immediately
```

If you only change the env file (e.g. `~/.config/deal-finder.env`), you do **not** need `daemon-reload`; just restart the service or wait for the next timer run:

```bash
systemctl --user restart deal-finder.service
```

Check timer status and upcoming runs:

```bash
systemctl --user status deal-finder.timer
systemctl --user list-timers --all | grep deal-finder
```

The service is triggered by the timer. Manual status/logs:

```bash
systemctl --user status deal-finder.service
journalctl --user -u deal-finder.service -n 50
```

To keep it running while logged out, enable lingering for your user:

```bash
loginctl enable-linger "$USER"
```

### Termux (Android)

You can run deal-finder on your Android phone using [Termux](https://f-droid.org/packages/com.termux/).

1. Install Termux from F-Droid (not Play Store – the Play Store version is outdated).

2. Install dependencies:

```bash
pkg update && pkg upgrade
pkg install python git
pip install requests beautifulsoup4
```

3. Clone the repository:

```bash
mkdir -p ~/git && cd ~/git
git clone https://github.com/YOUR_USERNAME/deal-finder.git
cd deal-finder
```

4. Add environment variables to `~/.bashrc`:

```bash
# deal-finder notifications
export DEAL_NOTIFIER_EMAIL_FROM="you@example.com"
export DEAL_NOTIFIER_EMAIL_TO="you@example.com"
export DEAL_NOTIFIER_SMTP_HOST="smtp.example.com"
export DEAL_NOTIFIER_SMTP_PORT="587"
export DEAL_NOTIFIER_SMTP_USER="you@example.com"
export DEAL_NOTIFIER_SMTP_PASSWORD="your-password"
export DEAL_NOTIFIER_SMTP_STARTTLS="1"

export DEAL_NOTIFIER_NTFY_TOPIC="your-ntfy-topic"

# Start crond if not running
pgrep -x crond > /dev/null || crond
```

5. Install cronie and reload your shell:

```bash
pkg install cronie
source ~/.bashrc
```

6. Create a crontab entry (runs every hour):

```bash
crontab -e
```

Add:

```cron
0 * * * * . $HOME/.bashrc && cd $HOME/git/deal-finder && python3 kleinanzeigen.py "your search term:MIN-MAX" --notify >> $HOME/.cache/deal-finder.log 2>&1
```

7. Useful commands:

```bash
# View/edit crontab
crontab -l
crontab -e

# Check logs
tail -f ~/.cache/deal-finder.log

# Test manually
cd ~/git/deal-finder && python3 kleinanzeigen.py "test" --notify

# Check if crond is running
pgrep -x crond
```

**Note:** Termux must remain running in the background for cron jobs to execute. Consider disabling battery optimization for Termux in Android settings. For persistence across device reboots, install the [Termux:Boot](https://f-droid.org/packages/com.termux.boot/) app.

## Future extensions

Planned / obvious next steps:

- Add more sources:
  - `deal_finder/amazon.py`
  - `deal_finder/ebay.py`
  - `deal_finder/kickstarter.py`
- Generalize the model:
  - Introduce a site-agnostic `Deal` type with fields like `site`, `id`, `title`, `price`, `url`, `location`, `tags`.
- Shared orchestration:
  - Central scheduler that runs multiple source plugins and aggregates new deals.
  - Unified deduplication across sources.
- More flexible filters:
  - Configurable include/exclude keyword lists per source.
  - Configurable price ranges and simple heuristics per category.

For now, the Kleinanzeigen plugin is intentionally small and opinionated, optimized for running frequently with fast, minimal notifications.
