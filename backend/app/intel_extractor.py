import re
from typing import Dict, List

UPI_RE = re.compile(r"\b[a-zA-Z0-9._-]{2,256}@[a-zA-Z]{2,64}\b")
BANK_RE = re.compile(r"\b\d{9,18}\b")
IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"]+\b", re.IGNORECASE)


def _normalize_url(url: str) -> str:
    if url.lower().startswith("www."):
        return "http://" + url
    return url


def _looks_like_phone(number: str, text: str) -> bool:
    if len(number) == 10 and number[0] in {"6", "7", "8", "9"}:
        if not any(k in text.lower() for k in ("account", "bank", "a/c", "acc", "ifsc")):
            return True
    return False


def _has_bank_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 24) : min(len(text), end + 24)].lower()
    return any(k in window for k in ("account", "bank", "a/c", "acc", "ifsc", "ifsc code"))


def _normalize_account(num: str) -> str:
    return re.sub(r"[\s-]", "", num)


def extract_intel(text: str) -> Dict[str, List[str]]:
    if not text:
        return {"upi_ids": [], "bank_accounts": [], "phishing_links": []}

    upi_ids = [m.group(0) for m in UPI_RE.finditer(text)]
    bank_accounts = []
    for m in BANK_RE.finditer(text):
        raw = m.group(0)
        if _looks_like_phone(raw, text):
            continue
        if not _has_bank_context(text, m.start(), m.end()):
            continue
        bank_accounts.append(_normalize_account(raw))

    # Add IFSC codes as labeled entries
    for m in IFSC_RE.finditer(text):
        bank_accounts.append(f"IFSC:{m.group(0).upper()}")
    phishing_links = [_normalize_url(m.group(0)) for m in URL_RE.finditer(text)]

    return {
        "upi_ids": upi_ids,
        "bank_accounts": bank_accounts,
        "phishing_links": phishing_links,
    }


def merge_intel(existing: Dict[str, List[str]], found: Dict[str, List[str]]) -> Dict[str, List[str]]:
    merged = {
        "upi_ids": set(existing.get("upi_ids", [])),
        "bank_accounts": set(existing.get("bank_accounts", [])),
        "phishing_links": set(existing.get("phishing_links", [])),
    }

    merged["upi_ids"].update(found.get("upi_ids", []))
    merged["bank_accounts"].update(found.get("bank_accounts", []))
    merged["phishing_links"].update(found.get("phishing_links", []))

    return {
        "upi_ids": sorted(merged["upi_ids"]),
        "bank_accounts": sorted(merged["bank_accounts"]),
        "phishing_links": sorted(merged["phishing_links"]),
    }


def extract_and_merge(text: str, existing: Dict[str, List[str]]) -> Dict[str, List[str]]:
    found = extract_intel(text)
    return merge_intel(existing, found)
