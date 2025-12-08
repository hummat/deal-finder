# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

deal-finder is a minimal deal finder/notifier for Kleinanzeigen (German classifieds). The code is structured as a plugin architecture where `kleinanzeigen.py` is one source module; additional sources (Amazon, eBay, etc.) can be added as separate modules.

## Commands

### Installation
```bash
pip install -e .
```

### Running
```bash
# Basic search (prints matching listings)
python3 kleinanzeigen.py "search term"

# With notifications
python3 kleinanzeigen.py "search term" --notify

# Multiple terms with price filter
python3 kleinanzeigen.py "term1" "term2" --min-price 100 --max-price 300 --notify

# Per-term price ranges
python3 kleinanzeigen.py "term1:100-200" "term2:150-250" --notify

# Variants (multiple search strings for same item)
python3 kleinanzeigen.py "english name|german name|item-number:100-200" --notify

# Disable specific notification channels
python3 kleinanzeigen.py --notify --no-email   # ntfy only
python3 kleinanzeigen.py --notify --no-ntfy    # email only

# Clear seen cache
python3 kleinanzeigen.py "term" --clear-seen --notify
```

### Console Script (after install)
```bash
check-kleinanzeigen-cpus --notify
```

**Note:** No test suite exists in this repository.

## Architecture

Single-file module `kleinanzeigen.py` (~576 lines). Python 3.10+ required (uses `float | None` union syntax).

### Key Data Structures
- `Listing` dataclass: title, price, location, url, term
- `SearchTermConfig` dataclass: term with optional per-term min/max price

### Core Flow
1. `parse_search_term_arg()` - Parses CLI args supporting `term:MIN-MAX` and `term1|term2` syntax
2. `fetch_listings_for_term()` - Scrapes Kleinanzeigen search results using requests + BeautifulSoup
3. `find_matching_listings()` - Aggregates listings, applies price filters, deduplicates by URL
4. `filter_new_listings()` - Filters against seen cache at `~/.cache/kleinanzeigen_seen.json`
5. `notify_email()` / `notify_ntfy()` - Send notifications via SMTP or ntfy HTTP push

### Title Filtering
`is_blacklisted_title()` filters out PC bundles/full systems using `DEFAULT_TITLE_BLACKLIST`. The blacklist is skipped for terms that contain the blacklisted word (e.g., searching for "gaming pc" won't filter "gaming pc" titles).

## Environment Variables

Email (SMTP): `DEAL_NOTIFIER_EMAIL_FROM`, `DEAL_NOTIFIER_EMAIL_TO`, `DEAL_NOTIFIER_SMTP_HOST`, `DEAL_NOTIFIER_SMTP_PORT`, `DEAL_NOTIFIER_SMTP_USER`, `DEAL_NOTIFIER_SMTP_PASSWORD`, `DEAL_NOTIFIER_SMTP_STARTTLS`

ntfy: `DEAL_NOTIFIER_NTFY_URL` or `DEAL_NOTIFIER_NTFY_TOPIC`
