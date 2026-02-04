import re
from typing import Dict, List, Tuple

SCAM_KEYWORDS = {
    "upi",
    "otp",
    "bank",
    "account",
    "refund",
    "lottery",
    "prize",
    "kyc",
    "verification",
    "verify",
    "click",
    "link",
    "payment",
    "deposit",
    "transfer",
    "wire",
    "password",
    "login",
    "customer care",
    "support",
    "suspend",
    "blocked",
    "urgent",
    "penalty",
    "fine",
    "limited time",
    "gift card",
    "bitcoin",
    "crypto",
    "wallet",
    "zelle",
    "processing fee",
    "fee",
}

URGENCY = {
    "urgent",
    "immediately",
    "within",
    "expire",
    "suspend",
    "limited time",
    "last chance",
    "final notice",
    "action required",
}

FAMILY_HINTS = {
    "mom",
    "dad",
    "mother",
    "father",
    "bro",
    "brother",
    "sis",
    "sister",
    "aunt",
    "uncle",
    "son",
    "daughter",
    "cousin",
    "grandma",
    "grandpa",
    "grandmother",
    "grandfather",
    "family",
}

NORMAL_HINTS = {
    "hello",
    "hi",
    "how are you",
    "good morning",
    "good afternoon",
    "good evening",
    "thanks",
    "thank you",
    "ok",
    "okay",
    "see you",
    "meet",
    "call me",
}

URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"]+\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _score(message: str) -> Tuple[int, List[str]]:
    reasons: List[str] = []
    if not message:
        return 0, reasons

    text = message.lower()
    score = 0

    keyword_hits = [kw for kw in SCAM_KEYWORDS if kw in text]
    if keyword_hits:
        score += min(30, 5 * len(keyword_hits))
        reasons.append(f"keywords:{','.join(keyword_hits[:5])}")

    if any(u in text for u in URGENCY):
        score += 15
        reasons.append("urgency")

    if URL_RE.search(text):
        score += 20
        reasons.append("url")

    if "otp" in text or "password" in text or "login" in text:
        score += 20
        reasons.append("credential_request")

    if "kyc" in text or "verify" in text or "verification" in text:
        score += 15
        reasons.append("verification")

    if "refund" in text or "prize" in text or "lottery" in text:
        score += 15
        reasons.append("too_good")

    if "bitcoin" in text or "crypto" in text or "wallet" in text:
        score += 20
        reasons.append("crypto")

    if "processing fee" in text or ("fee" in text and "refund" in text):
        score += 15
        reasons.append("fee_request")

    if PHONE_RE.search(text) or EMAIL_RE.search(text):
        score += 5
        reasons.append("contact_info")

    return score, reasons


def _classify_intent(text: str) -> str:
    if any(k in text for k in FAMILY_HINTS):
        return "family"
    if any(k in text for k in NORMAL_HINTS):
        return "normal"
    return "unknown"


def detect_scam_details(message: str) -> Dict[str, object]:
    text = (message or "").lower()
    score, reasons = _score(message or "")
    intent = _classify_intent(text)
    # Fast-path triggers
    strong_triggers = any(k in text for k in ("upi", "otp", "ifsc", "bank account", "bitcoin", "crypto", "wallet"))
    url_trigger = bool(URL_RE.search(text)) and any(k in text for k in ("verify", "login", "update", "kyc"))
    refund_fee_trigger = ("refund" in text) and ("fee" in text or "processing fee" in text)

    scam_detected = (
        score >= 35
        or ("url" in reasons and "verification" in reasons)
        or strong_triggers
        or url_trigger
        or refund_fee_trigger
    )

    # Reduce false positives for casual/family chat with no scam signals
    if intent in {"family", "normal"} and score < 25:
        scam_detected = False

    return {
        "scam_detected": scam_detected,
        "score": min(score, 95),
        "intent": intent,
        "reasons": reasons,
    }


def detect_scam(message: str) -> bool:
    return bool(detect_scam_details(message).get("scam_detected"))
