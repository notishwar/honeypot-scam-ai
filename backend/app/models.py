from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    persona: str | None = None


class ExtractedIntel(BaseModel):
    upi_ids: list[str] = Field(default_factory=list)
    bank_accounts: list[str] = Field(default_factory=list)
    phishing_links: list[str] = Field(default_factory=list)


class MessageResponse(BaseModel):
    session_id: str
    scam_detected: bool
    agent_active: bool
    extracted_intel: ExtractedIntel
    agent_reply: str
    risk_score: int | None = None
    persona: str | None = None
    persona_profile: dict | None = None
    asked_fields: list[str] | None = None
    scam_intent: str | None = None
    scam_reasons: list[str] | None = None
    scam_score: int | None = None
