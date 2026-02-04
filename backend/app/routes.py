from fastapi import APIRouter, HTTPException, Request

import re

from .agent import HoneyPotAgent, get_llm_client, get_profile
from .intel_extractor import extract_and_merge
from .logger import get_logger, log_event
from .models import MessageRequest, MessageResponse, ExtractedIntel
from .scam_detector import detect_scam, detect_scam_details
from .session_store import get_rate_limiter, get_session_store, new_session
from .config import API_KEY, PERSONA_DEFAULT

router = APIRouter()
logger = get_logger()
store = get_session_store()
rate_limiter = get_rate_limiter()
agent = HoneyPotAgent(get_llm_client())


def _validate_api_key(api_key: str) -> None:
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/message", response_model=MessageResponse)
async def handle_message(payload: MessageRequest, request: Request) -> MessageResponse:
    _validate_api_key(payload.api_key)

    if not rate_limiter.allow(payload.session_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    session = store.get_session(payload.session_id) or new_session()
    session.setdefault("history", [])
    session.setdefault("intel", {"upi_ids": [], "bank_accounts": [], "phishing_links": []})
    session.setdefault("scam_detected", False)
    session.setdefault("agent_active", False)
    session.setdefault("persona", PERSONA_DEFAULT)
    session.setdefault("persona_profile", {})
    session.setdefault("asked_fields", [])

    session["history"].append({"role": "user", "content": payload.message})

    details = detect_scam_details(payload.message)
    # Determine persona early so UI always reflects selection
    persona = (payload.persona or session.get("persona") or PERSONA_DEFAULT).lower()
    session["persona"] = persona
    session["persona_profile"] = get_profile(persona, session.get("persona_profile") or {})

    scam_detected = session.get("scam_detected", False) or bool(details.get("scam_detected"))
    session["scam_detected"] = scam_detected
    # Activate agent if strong signals or moderate score with unknown intent
    score = int(details.get("score") or 0) if details else 0
    intent = str(details.get("intent") or "unknown") if details else "unknown"
    if scam_detected or (score >= 25 and intent == "unknown"):
        session["agent_active"] = True

    agent_active = session.get("agent_active", False)
    agent_reply = ""
    if agent_active:
        profile = session.get("persona_profile") or get_profile(persona, {})

        intel_seed = extract_and_merge(payload.message, session.get("intel", {}))
        asked = session.get("asked_fields", [])
        agent_reply = agent.reply(session["history"], persona, intel_seed, asked, profile)
        session["history"].append({"role": "assistant", "content": agent_reply})
    else:
        # Normal conversation reply when not a scam
        agent_reply = agent.normal_reply(persona, payload.message)
        session["history"].append({"role": "assistant", "content": agent_reply})

    intel = session.get("intel", {"upi_ids": [], "bank_accounts": [], "phishing_links": []})
    intel = extract_and_merge(payload.message, intel)
    if agent_reply:
        intel = extract_and_merge(agent_reply, intel)
    session["intel"] = intel

    # Update asked fields based on reply content
    asked_fields = set(session.get("asked_fields", []))
    reply_text = (agent_reply or "").lower()
    if "upi" in reply_text:
        asked_fields.add("upi")
    if "account" in reply_text or "ifsc" in reply_text:
        asked_fields.add("bank_ifsc")
    if "link" in reply_text or "url" in reply_text:
        asked_fields.add("link")
    if "wallet" in reply_text or "crypto" in reply_text or "bitcoin" in reply_text:
        asked_fields.add("crypto_wallet")
    session["asked_fields"] = sorted(asked_fields)

    # Risk score based on signals (0-95)
    combined = (payload.message + " " + agent_reply).strip()
    email_re = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    phone_re = re.compile(r"\+?\d[\d\s().-]{7,}\d")
    crypto_re = re.compile(r"\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b", re.IGNORECASE)
    has_email = bool(email_re.search(combined))
    has_phone = bool(phone_re.search(combined))
    has_crypto = bool(crypto_re.search(combined))

    risk_score = 0
    if scam_detected:
        risk_score += 40
    if intel.get("phishing_links"):
        risk_score += 25
    if intel.get("upi_ids") or intel.get("bank_accounts"):
        risk_score += 20
    if has_phone:
        risk_score += 5
    if has_email:
        risk_score += 5
    if has_crypto:
        risk_score += 10
    risk_score = min(risk_score, 95)

    store.save_session(payload.session_id, session)

    log_event(
        logger,
        "message_handled",
        session_id=payload.session_id,
        scam_detected=scam_detected,
        agent_active=agent_active,
        client=request.client.host if request.client else "unknown",
    )

    return MessageResponse(
        session_id=payload.session_id,
        scam_detected=scam_detected,
        agent_active=agent_active,
        extracted_intel=ExtractedIntel(**intel),
        agent_reply=agent_reply,
        risk_score=risk_score,
        persona=session.get("persona"),
        persona_profile=session.get("persona_profile"),
        asked_fields=session.get("asked_fields"),
        scam_intent=str(details.get("intent")) if details else None,
        scam_reasons=list(details.get("reasons")) if details else None,
        scam_score=int(details.get("score")) if details and details.get("score") is not None else None,
    )
