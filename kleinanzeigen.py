#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable, List, Sequence, Set, Optional

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.kleinanzeigen.de/s-"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
TIMEOUT = 10

# Titles that usually indicate "full PC / setup / bundle", not a single item
DEFAULT_TITLE_BLACKLIST = [
    "gaming pc",
    "pc ",
    " setup",
    "bundle",
    "komplett",
    "rechner",
    "fertig",
    "wasserkühlung",
    "wasserkuehlung",
]


@dataclass
class Listing:
    title: str
    price: float
    location: str
    url: str
    term: str


@dataclass
class SearchTermConfig:
    term: str
    min_price: float | None = None
    max_price: float | None = None


def is_blacklisted_title(
    title: str,
    search_term: str,
    extra_blacklist: Optional[Sequence[str]] = None,
) -> bool:
    t = title.lower()
    term_lower = search_term.lower()
    # Obvious gaming PC / setup phrases, unless the user is explicitly
    # searching for those words.
    if "gaming" in t and ("pc" in t or "setup" in t):
        if "gaming" not in term_lower and "pc" not in term_lower and "setup" not in term_lower:
            return True

    # Default blacklist substrings, but don't blacklist substrings that
    # are part of the search term.
    for bad in DEFAULT_TITLE_BLACKLIST:
        if bad in term_lower:
            continue
        if bad in t:
            return True

    # Extra user-provided blacklist entries behave similarly.
    if extra_blacklist:
        for bad in extra_blacklist:
            bad_l = str(bad).lower()
            if bad_l in term_lower:
                continue
            if bad_l in t:
                return True
    return False


def parse_price(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    if "zu verschenken" in text.lower() or "tausch" in text.lower():
        return None
    m = re.search(r"(\d+(?:[\.,]\d{1,2})?)", text.replace("\xa0", " "))
    if not m:
        return None
    val = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def fetch_listings_for_term(
    term: str,
    extra_blacklist: Optional[Sequence[str]] = None,
) -> List[Listing]:
    slug = term.lower().replace(" ", "-")
    url = f"{BASE_URL}{slug}/k0"
    headers = {"User-Agent": USER_AGENT}

    print(f"[INFO] Fetching: {url}")
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    listings: List[Listing] = []

    for ad in soup.select("article.aditem, article.aditem-container, article"):
        title_el = None
        title_text = ""

        # Prefer anchors that actually look like ad titles:
        for a in ad.find_all("a", href=True):
            href_candidate = a.get("href") or ""
            if "/s-anzeige/" not in href_candidate:
                continue
            txt = a.get_text(strip=True)
            if not txt:
                continue
            # Skip numeric-only anchors like image counters
            if not re.search(r"[A-Za-zÄÖÜäöü]", txt):
                continue
            title_el = a
            title_text = txt
            break

        if not title_el:
            continue
        title = title_text

        # Drop obvious PC/bundle listings
        if is_blacklisted_title(title, search_term=term, extra_blacklist=extra_blacklist):
            continue

        href = title_el.get("href") or ""
        if not href.startswith("http"):
            href = "https://www.kleinanzeigen.de" + href

        price_el = ad.select_one(
            ".aditem-main--middle--price-shipping, .aditem-main--middle--price"
        )
        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        price = parse_price(price_text)

        loc_el = ad.select_one(".aditem-main--top--left, .aditem-main--top")
        location = loc_el.get_text(" ", strip=True) if loc_el else ""

        if price is None:
            continue
        listings.append(
            Listing(title=title, price=price, location=location, url=href, term=term)
        )

    return listings


def find_matching_listings(
    search_terms: Iterable[SearchTermConfig | str],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    extra_blacklist: Optional[Sequence[str]] = None,
) -> list[Listing]:
    all_hits: list[Listing] = []
    configs: list[SearchTermConfig] = []

    for term in search_terms:
        if isinstance(term, SearchTermConfig):
            configs.append(term)
        else:
            configs.append(SearchTermConfig(term=str(term)))

    for cfg in configs:
        try:
            listings = fetch_listings_for_term(cfg.term, extra_blacklist=extra_blacklist)
        except Exception as e:
            print(f"[ERROR] Failed for term '{cfg.term}': {e}")
            continue

        effective_min = cfg.min_price if cfg.min_price is not None else min_price
        effective_max = cfg.max_price if cfg.max_price is not None else max_price

        for listing in listings:
            if effective_min is not None and listing.price < effective_min:
                continue
            if effective_max is not None and listing.price > effective_max:
                continue
            all_hits.append(listing)

        time.sleep(2)

    # Deduplicate listings by URL across all terms to avoid duplicates when
    # multiple variants match the same ad.
    seen_urls: set[str] = set()
    unique_hits: list[Listing] = []
    for listing in all_hits:
        if listing.url in seen_urls:
            continue
        seen_urls.add(listing.url)
        unique_hits.append(listing)

    return sorted(unique_hits, key=lambda x: x.price)


STATE_PATH = Path.home() / ".cache" / "kleinanzeigen_seen.json"


def load_seen_urls() -> Set[str]:
    try:
        raw = STATE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except Exception as e:
        print(f"[WARN] Failed to read state file '{STATE_PATH}': {e}")
        return set()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[WARN] Failed to parse state file '{STATE_PATH}': {e}")
        return set()

    if not isinstance(data, list):
        print(f"[WARN] State file '{STATE_PATH}' has unexpected format; ignoring.")
        return set()

    return {str(item) for item in data}


def save_seen_urls(urls: Set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        STATE_PATH.write_text(json.dumps(sorted(urls)), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] Failed to write state file '{STATE_PATH}': {e}")


def filter_new_listings(listings: Sequence[Listing]) -> list[Listing]:
    seen = load_seen_urls()
    new_listings = [listing for listing in listings if listing.url not in seen]
    if not new_listings:
        return []

    seen.update(listing.url for listing in new_listings)
    save_seen_urls(seen)
    return new_listings


def format_listing(listing: Listing) -> str:
    return (
        f"[{listing.term}] {listing.price:.0f} € | {listing.title}\n"
        f"{listing.location}\n"
        f"{listing.url}"
    )


def notify_email(listings: Sequence[Listing]) -> None:
    if not listings:
        return

    sender = os.getenv("DEAL_NOTIFIER_EMAIL_FROM")
    recipient = os.getenv("DEAL_NOTIFIER_EMAIL_TO")

    if not sender or not recipient:
        print(
            "[WARN] DEAL_NOTIFIER_EMAIL_FROM/DEAL_NOTIFIER_EMAIL_TO not set; "
            "skipping email notification."
        )
        return

    host = os.getenv("DEAL_NOTIFIER_SMTP_HOST", "localhost")
    port_raw = os.getenv("DEAL_NOTIFIER_SMTP_PORT", "25")
    try:
        port = int(port_raw)
    except ValueError:
        print(f"[WARN] Invalid DEAL_NOTIFIER_SMTP_PORT '{port_raw}', falling back to 25.")
        port = 25

    user = os.getenv("DEAL_NOTIFIER_SMTP_USER")
    password = os.getenv("DEAL_NOTIFIER_SMTP_PASSWORD")
    use_starttls = os.getenv("DEAL_NOTIFIER_SMTP_STARTTLS", "0") == "1"

    msg = EmailMessage()
    msg["Subject"] = f"[Kleinanzeigen] {len(listings)} new listing(s)"
    msg["From"] = sender
    msg["To"] = recipient
    body = "\n\n".join(format_listing(l) for l in listings)
    msg.set_content(body)

    try:
        import smtplib

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_starttls:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        print(f"[INFO] Sent email notification for {len(listings)} listing(s).")
    except Exception as e:
        print(f"[ERROR] Failed to send email notification: {e}")


def notify_ntfy(listings: Sequence[Listing]) -> None:
    if not listings:
        return

    url = os.getenv("DEAL_NOTIFIER_NTFY_URL")
    topic = os.getenv("DEAL_NOTIFIER_NTFY_TOPIC")

    if not url:
        if not topic:
            print(
                "[WARN] DEAL_NOTIFIER_NTFY_URL/DEAL_NOTIFIER_NTFY_TOPIC not set; "
                "skipping ntfy notification."
            )
            return
        url = f"https://ntfy.sh/{topic}"

    def sanitize_header(value: str) -> str:
        # HTTP headers must be ISO-8859-1 / ASCII; ntfy only cares about
        # human readability, so we can safely replace non-encodable chars.
        return value.encode("ascii", "replace").decode("ascii")

    sent = 0
    for listing in listings:
        title = f"{listing.price:.0f} € {listing.title}"
        if len(title) > 80:
            title = title[:77] + "..."
        title = sanitize_header(title)
        body = listing.url

        try:
            resp = requests.post(
                url,
                data=body.encode("utf-8"),
                headers={"Title": title},
                timeout=5,
            )
            resp.raise_for_status()
            sent += 1
        except Exception as e:
            print(
                f"[ERROR] Failed to send ntfy notification for '{listing.url}': {e}"
            )

    if sent:
        print(f"[INFO] Sent ntfy notification for {sent} listing(s).")


def print_listings(
    listings: Sequence[Listing],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> None:
    if not listings:
        if min_price is not None and max_price is not None:
            print(
                f"[INFO] No listings between {min_price} € and {max_price} € found."
            )
        elif min_price is not None:
            print(f"[INFO] No listings with price >= {min_price} € found.")
        elif max_price is not None:
            print(f"[INFO] No listings with price <= {max_price} € found.")
        else:
            print("[INFO] No listings found.")
        return

    if min_price is not None or max_price is not None:
        if min_price is not None and max_price is not None:
            header = f"({min_price}–{max_price} €)"
        elif min_price is not None:
            header = f"(>= {min_price} €)"
        else:
            header = f"(<= {max_price} €)"
        print(f"\n=== MATCHING LISTINGS {header} ===")
    else:
        print("\n=== MATCHING LISTINGS (any price) ===")
    for listing in listings:
        print(f"[{listing.term}] {listing.price:.0f} € | {listing.title}")
        print(f"  {listing.location}")
        print(f"  {listing.url}\n")


def parse_search_term_arg(arg: str) -> list[SearchTermConfig]:
    """
    Parse a positional search term argument.

    Supported forms:
      - "term"
      - "term1|term2|term3"
      - "term:MIN"
      - "term:MIN-MAX"
      - "term1|term2:MIN-MAX"
    """
    term_part, sep, price_part = arg.partition(":")
    term_raw = term_part.strip()
    if not term_raw:
        raise ValueError(f"Invalid search term '{arg}': empty term.")

    term_variants = [t.strip() for t in term_raw.split("|") if t.strip()]
    if not term_variants:
        raise ValueError(f"Invalid search term '{arg}': empty term.")

    if not sep:
        return [SearchTermConfig(term=t) for t in term_variants]

    price_str = price_part.strip()
    if not price_str:
        raise ValueError(f"Invalid search term '{arg}': missing price after ':'.")

    local_min: float | None = None
    local_max: float | None = None

    if "-" in price_str:
        low_str, high_str = [s.strip() for s in price_str.split("-", 1)]
        if not low_str or not high_str:
            raise ValueError(
                f"Invalid price range '{price_str}' in search term '{arg}'."
            )
        try:
            local_min = float(low_str.replace(",", "."))
            local_max = float(high_str.replace(",", "."))
        except ValueError:
            raise ValueError(
                f"Invalid price range '{price_str}' in search term '{arg}'."
            )
        if local_max < local_min:
            raise ValueError(
                f"Invalid price range '{price_str}' in search term '{arg}': "
                "max < min."
            )
    else:
        try:
            local_min = float(price_str.replace(",", "."))
        except ValueError:
            raise ValueError(
                f"Invalid price '{price_str}' in search term '{arg}'."
            )
        local_max = None

    return [
        SearchTermConfig(term=t, min_price=local_min, max_price=local_max)
        for t in term_variants
    ]


def run_once(
    notify: bool,
    enable_email: bool,
    enable_ntfy: bool,
    search_terms: Iterable[SearchTermConfig | str],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    extra_blacklist: Optional[Sequence[str]] = None,
) -> None:
    all_hits = find_matching_listings(
        search_terms=search_terms,
        min_price=min_price,
        max_price=max_price,
        extra_blacklist=extra_blacklist,
    )

    if not notify:
        print_listings(all_hits, min_price=min_price, max_price=max_price)
        return

    new_hits = filter_new_listings(all_hits)
    if not new_hits:
        print("[INFO] No new listings to notify.")
        return

    if enable_email:
        notify_email(new_hits)
    if enable_ntfy:
        notify_ntfy(new_hits)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Search Kleinanzeigen for deals matching search terms and "
            "optionally send notifications."
        )
    )
    parser.add_argument(
        "search_terms",
        nargs="*",
        help=(
            "Kleinanzeigen search terms. Each term can optionally include a "
            "per-term price range as 'TERM:MIN' or 'TERM:MIN-MAX'."
        ),
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notifications for new listings instead of just printing.",
    )
    parser.add_argument(
        "--min-price",
        type=float,
        help="Minimum price in EUR (optional).",
    )
    parser.add_argument(
        "--max-price",
        type=float,
        help="Maximum price in EUR (optional).",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Disable email notifications (when --notify is set).",
    )
    parser.add_argument(
        "--no-ntfy",
        action="store_true",
        help="Disable ntfy notifications (when --notify is set).",
    )
    parser.add_argument(
        "--blacklist",
        action="append",
        help=(
            "Additional case-insensitive substrings to blacklist in titles. "
            "Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--clear-seen",
        action="store_true",
        help="Clear the cache of already-seen listings before running.",
    )

    args = parser.parse_args()

    if not args.search_terms:
        parser.error("at least one search term is required")

    search_terms_cfg: list[SearchTermConfig] = []
    try:
        for arg in args.search_terms:
            search_terms_cfg.extend(parse_search_term_arg(arg))
    except ValueError as e:
        parser.error(str(e))

    min_price: Optional[float] = float(args.min_price) if args.min_price is not None else None
    max_price: Optional[float] = float(args.max_price) if args.max_price is not None else None
    extra_blacklist: Optional[Sequence[str]] = args.blacklist

    if args.clear_seen:
        try:
            if STATE_PATH.exists():
                STATE_PATH.unlink()
                print(f"[INFO] Cleared seen-cache at '{STATE_PATH}'.")
        except Exception as e:
            print(f"[WARN] Failed to clear seen-cache '{STATE_PATH}': {e}")

    run_once(
        notify=args.notify,
        enable_email=not args.no_email,
        enable_ntfy=not args.no_ntfy,
        search_terms=search_terms_cfg,
        min_price=min_price,
        max_price=max_price,
        extra_blacklist=extra_blacklist,
    )


if __name__ == "__main__":
    main()
