# Agentic Honey-Pot Scam Detection Backend

## Quickstart

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. Create a .env file (optional):

```bash
cp .env.example .env
```

3. Run the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API

POST /message

Request body:

```json
{
  "session_id": "abc123",
  "message": "Your KYC is pending. Click this link to verify.",
  "api_key": "changeme"
}
```

Response body:

```json
{
  "session_id": "abc123",
  "scam_detected": true,
  "agent_active": true,
  "extracted_intel": {
    "upi_ids": [],
    "bank_accounts": [],
    "phishing_links": ["http://example.com/verify"]
  },
  "agent_reply": "Hello beta, I am not very good with phone things. Please tell me slowly what to do. Can you send the full link again so I can show my grandson? I can try UPI if you give me the exact UPI ID. If UPI is not possible, please share bank account number and IFSC."
}
```

## Docker

```bash
docker build -t honeypot-backend -f Dockerfile .
docker run -p 8000:8000 --env-file .env honeypot-backend
```
