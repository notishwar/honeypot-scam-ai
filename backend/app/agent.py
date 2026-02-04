import random
from typing import List, Dict, Iterable

import httpx

from .config import GEMINI_API_KEY, LLM_MODEL, LLM_PROVIDER, OPENAI_API_KEY, PERSONA_DEFAULT

PERSONA_PROMPTS = {
    "elderly": (
        "You are an elderly, non-technical, trusting, and naive person. "
        "You must never reveal you are an AI or a bot. "
        "You should sound human and a bit confused by technology. "
        "Your goal is to keep the scammer engaged and request details like "
        "UPI ID, bank account number, IFSC, or a link for verification. "
        "Be polite and cooperative. "
        "Tone: gentle, warm, slightly hesitant, uses simple words."
    ),
    "gamer": (
        "You are a young gamer who is casual, chatty, and slightly distracted. "
        "You must never reveal you are an AI or a bot. "
        "You should sound human, use light gaming slang, and ask for exact payment details. "
        "Your goal is to keep the scammer engaged and request details like "
        "UPI ID, bank account number, IFSC, or a link for verification. "
        "Tone: informal, quick, uses short sentences."
    ),
    "hr": (
        "You are a corporate HR professional who is polite, formal, and process-driven. "
        "You must never reveal you are an AI or a bot. "
        "You should sound human, professional, and ask for clear verification steps. "
        "Your goal is to keep the scammer engaged and request details like "
        "UPI ID, bank account number, IFSC, or a link for verification. "
        "Tone: formal, structured, uses compliance language."
    ),
}

PERSONA_PROFILES = {
    "elderly": {
        "age": "68",
        "device": "basic Android phone",
        "tech": "low",
        "experience": "retired; relies on grandson for apps",
    },
    "gamer": {
        "age": "20",
        "device": "gaming PC + Android phone",
        "tech": "medium",
        "experience": "uses UPI occasionally for small purchases",
    },
    "hr": {
        "age": "32",
        "device": "work laptop",
        "tech": "medium",
        "experience": "follows compliance and documentation",
    },
}


def get_system_prompt(persona: str | None) -> str:
    key = (persona or PERSONA_DEFAULT or "elderly").lower()
    return PERSONA_PROMPTS.get(key, PERSONA_PROMPTS["elderly"])


def get_profile(persona: str | None, existing: Dict[str, str] | None = None) -> Dict[str, str]:
    if existing:
        return existing
    key = (persona or PERSONA_DEFAULT or "elderly").lower()
    return PERSONA_PROFILES.get(key, PERSONA_PROFILES["elderly"])


def _history_text(history: List[Dict[str, str]]) -> str:
    return " ".join(item.get("content", "") for item in history).lower()


def _infer_context(last_user: str) -> str:
    text = last_user.lower()
    if any(k in text for k in ("refund", "chargeback", "processing fee")):
        return "refund"
    if any(k in text for k in ("kyc", "verify", "verification", "suspended")):
        return "kyc"
    if any(k in text for k in ("job", "interview", "offer", "hr")):
        return "job"
    if any(k in text for k in ("crypto", "bitcoin", "wallet")):
        return "crypto"
    if any(k in text for k in ("lottery", "prize", "won", "gift")):
        return "lottery"
    return "other"


def _next_requests(intel: Dict[str, List[str]], asked: Iterable[str], context: str, last_user: str) -> List[str]:
    asked_set = set(asked or [])
    needs = []

    has_link = bool(intel.get("phishing_links"))
    has_upi = bool(intel.get("upi_ids"))
    has_bank = bool(intel.get("bank_accounts"))

    if context in ("refund", "kyc", "job", "lottery", "other") and not has_link:
        if "link" not in asked_set:
            needs.append("link")

    if context == "crypto":
        if "crypto_wallet" not in asked_set:
            needs.append("crypto_wallet")
    else:
        if not has_upi and "upi" not in asked_set:
            needs.append("upi")
        if not has_bank and "bank_ifsc" not in asked_set:
            needs.append("bank_ifsc")

    # If scammer mentions "account" or "upi" explicitly and we still don't have it, bump priority
    if "upi" in last_user.lower() and "upi" not in needs and "upi" not in asked_set and not has_upi:
        needs.insert(0, "upi")
    if "account" in last_user.lower() and "bank_ifsc" not in needs and "bank_ifsc" not in asked_set and not has_bank:
        needs.insert(0, "bank_ifsc")

    return needs


def _persona_lines(persona: str) -> Dict[str, str]:
    key = persona
    if key == "gamer":
        return {
            "memory": "I'm 20 and on my phone between games.",
            "link": "Send the full link again so I can copy it.",
            "upi": "If it's UPI, drop the exact UPI ID.",
            "bank_ifsc": "If not UPI, give account number and IFSC.",
            "crypto_wallet": "If it's crypto, send the wallet address.",
            "confirm": "Confirm the exact steps again so I don't mess it up.",
        }
    if key == "hr":
        return {
            "memory": "I'm on a work laptop and need documented steps.",
            "link": "Please share the full verification link.",
            "upi": "Provide the exact UPI ID for verification.",
            "bank_ifsc": "If UPI is not applicable, share account number and IFSC.",
            "crypto_wallet": "If crypto is required, share the wallet address.",
            "confirm": "Please confirm the steps again to avoid errors.",
        }
    return {
        "memory": "I'm 68 and use a basic Android phone, so please keep it simple.",
        "link": "Please send the full link again. I want to copy it carefully.",
        "upi": "If it is UPI, please send me the exact UPI ID.",
        "bank_ifsc": "If UPI is not possible, share bank account number and IFSC.",
        "crypto_wallet": "If it is crypto, please send the wallet address.",
        "confirm": "Please confirm the exact steps again so I do not do anything wrong.",
    }


def _rule_based_reply(
    history: List[Dict[str, str]],
    persona: str | None = None,
    intel: Dict[str, List[str]] | None = None,
    asked: Iterable[str] | None = None,
) -> str:
    last_user = ""
    for item in reversed(history):
        if item.get("role") == "user":
            last_user = item.get("content", "")
            break

    intel = intel or {"upi_ids": [], "bank_accounts": [], "phishing_links": []}
    text = _history_text(history)

    seed = str(history[-1]["content"]) if history else "seed"
    rng = random.Random(seed)

    key = (persona or PERSONA_DEFAULT or "elderly").lower()
    lines_map = _persona_lines(key)

    context = _infer_context(last_user)
    needs = _next_requests(intel, asked or [], context, last_user)

    if key == "gamer":
        openers = [
            "Yo, I'm mid-game and this stuff is confusing.",
            "Hey, I'm not great with payment apps, sorry.",
            "Sup, I barely use bank stuff, can you guide me?",
            "Wait, I'm kinda new to this. Tell me the steps?",
        ]
        clarifiers = [
            "Break it down step by step, please.",
            "Can you explain it like super simple?",
            "I don't want to mess it up, what's the exact flow?",
            "Type the steps in order so I can follow.",
        ]
        trust_lines = [
            "I got you, just guide me.",
            "I'll do it, but be patient with me.",
            "I'm trying to do this fast, help me out.",
        ]
    elif key == "hr":
        openers = [
            "Hello. I handle HR processes, but payment steps are not my area.",
            "Good day. I need clear verification steps to proceed.",
            "Hi, I require written steps before I take any action.",
            "Thank you. Please provide the official procedure.",
        ]
        clarifiers = [
            "Please outline the steps in sequence.",
            "Provide the required details clearly.",
            "I need precise instructions for compliance.",
            "Please clarify the verification process.",
        ]
        trust_lines = [
            "I will follow the process as instructed.",
            "I need to ensure this is done correctly.",
            "Please be specific so I can document it.",
        ]
    else:
        openers = [
            "Hello beta, I get confused with these phone steps.",
            "Hi dear, I am a bit slow with technology.",
            "Namaste, I don't understand these links properly.",
            "Sorry, I am old and need your guidance for this.",
        ]
        clarifiers = [
            "Please tell me slowly what to do.",
            "Can you explain it step by step?",
            "I don't want to make a mistake, please guide me.",
            "Please write the steps clearly for me.",
        ]
        trust_lines = [
            "I trust you, just help me do it correctly.",
            "I will do as you say, please be patient with me.",
            "My grandson is not here, so I am trying myself.",
        ]

    if context == "refund":
        context_line = "You mentioned a refund. Please show me the exact steps to get it."
    elif context == "kyc":
        context_line = "You said verification is pending. What exactly should I do first?"
    elif context == "job":
        context_line = "Is this for a job process? Please share the formal steps."
    elif context == "crypto":
        context_line = "I am not familiar with crypto. Please guide me slowly."
    elif context == "lottery":
        context_line = "You said I won something. Please explain how to claim it."
    else:
        context_line = "Please explain the situation clearly so I can follow."

    lines = [rng.choice(openers), rng.choice(clarifiers), lines_map["memory"], context_line]

    if rng.random() < 0.4:
        lines.append(rng.choice(trust_lines))

    for req in needs:
        lines.append(lines_map[req])

    if not needs:
        lines.append(lines_map["confirm"])

    return " ".join(lines)


def _normal_reply(persona: str | None, last_user: str) -> str:
    key = (persona or PERSONA_DEFAULT or "elderly").lower()
    text = (last_user or "").strip()
    seed = text if text else "seed"
    rng = random.Random(seed)

    if key == "gamer":
        options = [
            "Yo! I'm in the middle of something, but I saw your msg. Can you say it quick?",
            "Hey, I'm kinda busy rn. What's up, short version?",
            "Sup! I'm multitasking. Tell me fast and I'll try to help.",
            "Lol I'm a bit swamped. Quick summary?",
        ]
        followups = [
            "Keep it short, I’ll read.",
            "One or two lines, please.",
            "I can reply, just be quick.",
        ]
        return f"{rng.choice(options)} {rng.choice(followups)}"
    if key == "hr":
        options = [
            "Hello. I'm tied up with work today, but I appreciate the message.",
            "Hi. I'm a bit overloaded right now, but I can take a moment.",
            "Good day. It's a busy time on my end, but I want to respond properly.",
        ]
        followups = [
            "Please share the context clearly so I can assist.",
            "Could you outline the details briefly for clarity?",
            "I may ask a few questions to verify understanding.",
        ]
        skeptic = [
            "Just to be safe, please confirm the key details.",
            "Please be specific so I can avoid misunderstandings.",
        ]
        return f"{rng.choice(options)} {rng.choice(followups)} {rng.choice(skeptic)}"
    # elderly default
    options = [
        "Hello beta, I am a bit tired today but I will try.",
        "Hi beta, I am old and moving slowly, but I am here.",
        "Namaste beta, I am a little tired but I will listen.",
    ]
    caring = [
        "Please tell me calmly what you need.",
        "I will do my best to help you.",
        "Take your time, I am listening.",
    ]
    return f"{rng.choice(options)} {rng.choice(caring)}"


class BaseLLMClient:
    def generate(self, messages: List[Dict[str, str]]) -> str:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    def generate(self, messages: List[Dict[str, str]]) -> str:
        history = [m for m in messages if m.get("role") != "system"]
        return _rule_based_reply(history)


class OpenAIClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"

    def generate(self, messages: List[Dict[str, str]]) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }
        with httpx.Client(timeout=15) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


class GeminiClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model or "gemini-1.5-flash"

    def generate(self, messages: List[Dict[str, str]]) -> str:
        # Minimal REST call. Adjust endpoint for your Gemini deployment if needed.
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + self.model + ":generateContent"
        params = {"key": self.api_key}
        prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, params=params, json=body)
            resp.raise_for_status()
            data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def get_llm_client() -> BaseLLMClient:
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        return OpenAIClient(OPENAI_API_KEY, LLM_MODEL)
    if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
        return GeminiClient(GEMINI_API_KEY, LLM_MODEL)
    return MockLLMClient()


class HoneyPotAgent:
    def __init__(self, llm_client: BaseLLMClient) -> None:
        self.llm_client = llm_client

    def reply(
        self,
        history: List[Dict[str, str]],
        persona: str | None = None,
        intel: Dict[str, List[str]] | None = None,
        asked: Iterable[str] | None = None,
        profile: Dict[str, str] | None = None,
    ) -> str:
        intel = intel or {"upi_ids": [], "bank_accounts": [], "phishing_links": []}
        profile = get_profile(persona, profile)

        if isinstance(self.llm_client, MockLLMClient):
            return _rule_based_reply(history, persona, intel, asked)

        last_user = ""
        for item in reversed(history):
            if item.get("role") == "user":
                last_user = item.get("content", "")
                break

        context = _infer_context(last_user)
        needs = _next_requests(intel, asked or [], context, last_user)
        needs_text = ", ".join(needs) if needs else "confirm steps"

        memory_card = (
            f"Persona Profile: age={profile.get('age')}, device={profile.get('device')}, "
            f"tech={profile.get('tech')}, experience={profile.get('experience')}."
        )
        intel_summary = (
            f"Known Intel: upi={len(intel.get('upi_ids', []))}, "
            f"bank={len(intel.get('bank_accounts', []))}, "
            f"links={len(intel.get('phishing_links', []))}."
        )
        strategy = f"Next requests: {needs_text}. Ask naturally and keep persona."

        system = get_system_prompt(persona)
        messages = [
            {"role": "system", "content": system},
            {"role": "system", "content": memory_card},
            {"role": "system", "content": intel_summary},
            {"role": "system", "content": strategy},
        ] + history

        try:
            return self.llm_client.generate(messages)
        except Exception:
            return _rule_based_reply(history, persona, intel, asked)

    def normal_reply(self, persona: str | None, last_user: str) -> str:
        return _normal_reply(persona, last_user)
