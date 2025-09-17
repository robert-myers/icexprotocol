import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

URL = "https://tracreports.org/immigration/quickfacts/"
OUTPUT_PATH = Path("data/detentions.json")
HISTORY_LIMIT = 365
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ICE x Protocol scraper/1.0; +https://icexprotocol.com/)"
}

DIGITS_ONLY_RE = re.compile(r"^\d[\d,]*$")
NUMBER_WITH_COMMAS_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
LARGE_NUMBER_RE = re.compile(r"\b\d{4,}\b")
DATE_RE = re.compile(r"[A-Za-z]+\s+\d{1,2},\s+\d{4}")
MONTH_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)",
    re.IGNORECASE,
)


class ScraperError(RuntimeError):
    """Raised when the TRAC facts page cannot be parsed."""


def fetch_soup(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def find_fact_card(soup: BeautifulSoup, fragment: str) -> Optional[Tag]:
    anchor = soup.find(
        "a",
        href=lambda value: isinstance(value, str) and value.strip() == f"#{fragment}",
    )
    if not anchor:
        return None

    for ancestor in anchor.parents:
        if getattr(ancestor, "name", None) != "div":
            continue
        if not ancestor.find("a", href=f"#{fragment}"):
            continue
        if ancestor.find(string=lambda s: isinstance(s, str) and "data current as of" in s.lower()):
            return ancestor
    return None


def extract_primary_integer(card: Optional[Tag]) -> Optional[int]:
    if card is None:
        return None

    for node in card.find_all(string=True):
        text = node.strip()
        if not text or "%" in text or any(ch.isalpha() for ch in text):
            continue
        if DIGITS_ONLY_RE.fullmatch(text):
            return int(text.replace(",", ""))

    text = card.get_text(" ", strip=True)

    comma_match = NUMBER_WITH_COMMAS_RE.search(text)
    if comma_match:
        return int(comma_match.group(0).replace(",", ""))

    for match in LARGE_NUMBER_RE.finditer(text):
        candidate = match.group(0)
        if _is_likely_year(text, match.start()):
            continue
        return int(candidate)

    return None


def extract_ratio_numerator(card: Optional[Tag]) -> Optional[int]:
    if card is None:
        return None
    text = card.get_text(" ", strip=True)
    match = re.search(r"([0-9][0-9,]*)\s+out of", text, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    return extract_primary_integer(card)


def extract_date(card: Optional[Tag]) -> Optional[str]:
    if card is None:
        return None
    text = card.get_text(" ", strip=True)
    match = DATE_RE.search(text)
    if not match:
        return None
    date_text = match.group(0).replace(" ,", ",")
    return date_text.strip().rstrip(".")


def _is_likely_year(text: str, index: int) -> bool:
    start = max(0, index - 25)
    context = text[start:index].lower()
    return bool(MONTH_RE.search(context))


def load_existing_history() -> List[Dict[str, object]]:
    if not OUTPUT_PATH.exists():
        return []

    try:
        existing = json.loads(OUTPUT_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    history = existing.get("history", [])
    if not isinstance(history, list):
        return []

    cleaned: List[Dict[str, object]] = []
    for entry in history:
        if isinstance(entry, dict) and "detention_total" in entry:
            cleaned.append(entry)
    return cleaned


def snapshots_match(a: Dict[str, object], b: Dict[str, object]) -> bool:
    keys = (
        "detention_total",
        "detention_total_date",
        "no_criminal_conviction",
        "no_criminal_conviction_date",
        "atd_monitored",
        "atd_monitored_date",
    )
    return all(a.get(key) == b.get(key) for key in keys)


def append_snapshot(history: List[Dict[str, object]], snapshot: Dict[str, object]) -> List[Dict[str, object]]:
    if history and snapshots_match(history[-1], snapshot):
        history[-1]["captured_at"] = snapshot["captured_at"]
        return history

    history.append(snapshot)
    if len(history) > HISTORY_LIMIT:
        history = history[-HISTORY_LIMIT:]
    return history


def main() -> None:
    soup = fetch_soup(URL)

    total_card = find_fact_card(soup, "detention_held")
    nocrim_card = find_fact_card(soup, "detention_nocrim")
    atd_card = find_fact_card(soup, "detention_numatd")

    if not total_card or not nocrim_card or not atd_card:
        raise ScraperError("Could not locate one or more fact cards on the TRAC page")

    output = {
        "detention_total": extract_primary_integer(total_card),
        "detention_total_date": extract_date(total_card),
        "no_criminal_conviction": extract_ratio_numerator(nocrim_card),
        "no_criminal_conviction_date": extract_date(nocrim_card),
        "atd_monitored": extract_primary_integer(atd_card),
        "atd_monitored_date": extract_date(atd_card),
    }

    missing = [key for key, value in output.items() if value is None]
    if missing:
        raise ScraperError(f"Missing values for: {', '.join(missing)}")

    history = load_existing_history()
    snapshot = {
        **output,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    history = append_snapshot(history, snapshot)

    output_with_history = {**output, "history": history}

    json_payload = json.dumps(output_with_history, indent=2)
    OUTPUT_PATH.write_text(json_payload + "\n")
    print(json_payload)


if __name__ == "__main__":
    main()
