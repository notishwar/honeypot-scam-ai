const apiUrlInput = document.getElementById("apiUrl");
const apiKeyInput = document.getElementById("apiKey");
const sessionInput = document.getElementById("sessionId");
const personaInput = document.getElementById("persona");
const messageInput = document.getElementById("message");
const sendBtn = document.getElementById("sendBtn");
const pingBtn = document.getElementById("pingBtn");
const clearBtn = document.getElementById("clearBtn");
const chat = document.getElementById("chat");
const raw = document.getElementById("raw");
const statusEl = document.getElementById("status");
const upiList = null;
const bankList = null;
const linkList = null;
const riskBadge = document.getElementById("riskBadge");
const phoneValue = document.getElementById("phoneValue");
const cryptoValue = document.getElementById("cryptoValue");
const emailValue = document.getElementById("emailValue");
const bankUpiValue = document.getElementById("bankUpiValue");
const linkValue = document.getElementById("linkValue");
const originValue = document.getElementById("originValue");
const allUpiValue = document.getElementById("allUpiValue");
const allBankValue = document.getElementById("allBankValue");
const allLinksValue = document.getElementById("allLinksValue");
const personaName = document.getElementById("personaName");
const personaAge = document.getElementById("personaAge");
const personaDevice = document.getElementById("personaDevice");
const personaTech = document.getElementById("personaTech");
const personaExp = document.getElementById("personaExp");
const askedFields = document.getElementById("askedFields");
const scamIntent = document.getElementById("scamIntent");
const scamScore = document.getElementById("scamScore");
const scamReasons = document.getElementById("scamReasons");

const threatState = {
  phones: new Set(),
  emails: new Set(),
  cryptos: new Set(),
  origins: new Set(),
};

function setStatus(ok, text) {
  statusEl.textContent = text;
  statusEl.classList.toggle("ok", ok);
}

function appendBubble(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `bubble ${role}`;
  wrap.textContent = text;
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
}

function renderList(el, items) {
  if (!el) return;
  el.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "—";
    el.appendChild(li);
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  });
}

function findFirstMatch(text, regex) {
  const match = text.match(regex);
  return match ? match[0] : "";
}

function updateThreatCard(data, lastText) {
  const combined = `${lastText || ""} ${data.agent_reply || ""}`;

  const phone = findFirstMatch(combined, /\+?\d[\d\s().-]{7,}\d/);
  const email = findFirstMatch(combined, /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
  const crypto = findFirstMatch(
    combined,
    /\b(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b/i
  );
  const origin = findFirstMatch(combined, /\b[A-Z][a-z]+,\s*[A-Z][a-z]+/);

  const upi = (data.extracted_intel && data.extracted_intel.upi_ids) || [];
  const banks = (data.extracted_intel && data.extracted_intel.bank_accounts) || [];
  const links = (data.extracted_intel && data.extracted_intel.phishing_links) || [];

  const computedRisk =
    (data.scam_detected ? 40 : 0) +
    (links.length ? 25 : 0) +
    (upi.length || banks.length ? 20 : 0) +
    (phone ? 10 : 0) +
    (email ? 5 : 0);
  const risk = Number.isFinite(data.risk_score) ? data.risk_score : Math.min(computedRisk, 95);

  riskBadge.textContent = `RISK: ${risk}%`;
  if (phone) threatState.phones.add(phone);
  if (email) threatState.emails.add(email);
  if (crypto) threatState.cryptos.add(crypto);
  if (origin) threatState.origins.add(origin);

  const firstPhone = threatState.phones.values().next().value;
  const firstEmail = threatState.emails.values().next().value;
  const firstCrypto = threatState.cryptos.values().next().value;
  const firstOrigin = threatState.origins.values().next().value;

  phoneValue.textContent = firstPhone || "NOT DETECTED";
  cryptoValue.textContent = firstCrypto || "NOT DETECTED";
  emailValue.textContent = firstEmail || "NOT DETECTED";
  bankUpiValue.textContent = upi[0] || banks[0] || "NOT DETECTED";
  linkValue.textContent = links[0] || "NOT DETECTED";
  originValue.textContent = firstOrigin || "UNKNOWN";

  const fallbackPersona = personaInput ? personaInput.value : "elderly";
  if (personaName) personaName.textContent = data.persona || fallbackPersona;
  if (personaAge) personaAge.textContent = data.persona_profile?.age || "—";
  if (personaDevice) personaDevice.textContent = data.persona_profile?.device || "—";
  if (personaTech) personaTech.textContent = data.persona_profile?.tech || "—";
  if (personaExp) personaExp.textContent = data.persona_profile?.experience || "—";
  if (askedFields) {
    const asked = data.asked_fields || [];
    askedFields.textContent = asked.length ? asked.join(", ") : "—";
  }
  if (scamIntent) scamIntent.textContent = data.scam_intent || "UNKNOWN";
  if (scamScore) scamScore.textContent = Number.isFinite(data.scam_score) ? String(data.scam_score) : "0";
  if (scamReasons) {
    const reasons = data.scam_reasons || [];
    scamReasons.textContent = reasons.length ? reasons.join(", ") : "—";
  }

  if (allUpiValue) {
    allUpiValue.textContent = upi.length ? upi.join(" | ") : "—";
    allUpiValue.classList.toggle("multi", upi.length > 1);
  }
  if (allBankValue) {
    allBankValue.textContent = banks.length ? banks.join(" | ") : "—";
    allBankValue.classList.toggle("multi", banks.length > 1);
  }
  if (allLinksValue) {
    allLinksValue.textContent = links.length ? links.join(" | ") : "—";
    allLinksValue.classList.toggle("multi", links.length > 1);
  }
}

async function sendMessage() {
  const payload = {
    session_id: sessionInput.value.trim() || "demo-session",
    message: messageInput.value.trim(),
    api_key: apiKeyInput.value.trim(),
    persona: personaInput ? personaInput.value : undefined,
  };

  if (!payload.message) {
    alert("Please enter a message.");
    return;
  }
  if (!payload.api_key) {
    alert("Please enter your API key.");
    return;
  }

  appendBubble("user", payload.message);
  messageInput.value = "";

  try {
    const res = await fetch(apiUrlInput.value.trim(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      const detail = data && data.detail ? String(data.detail) : "Unknown error";
      const hint =
        detail.toLowerCase().includes("api key") ?
          "Invalid API key. Check backend/.env API_KEY and restart the server." :
          "Request failed. Check the API URL and backend logs.";
      setStatus(false, "Error");
      raw.textContent = JSON.stringify(
        { error: detail, hint, status: res.status },
        null,
        2
      );
      return;
    }

    setStatus(true, data.scam_detected ? "Scam Detected" : "Benign");
    appendBubble("agent", data.agent_reply || "(no reply)");
    renderList(upiList, data.extracted_intel?.upi_ids);
    renderList(bankList, data.extracted_intel?.bank_accounts);
    renderList(linkList, data.extracted_intel?.phishing_links);
    updateThreatCard(data, payload.message);
    raw.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    setStatus(false, "Disconnected");
    raw.textContent = String(err);
  }
}

async function pingServer() {
  try {
    const baseUrl = apiUrlInput.value.trim().replace(/\/message\/?$/, "");
    const res = await fetch(`${baseUrl}/health`, { method: "GET" });
    setStatus(res.ok, "Connected");
  } catch (err) {
    setStatus(false, "Disconnected");
  }
}

function clearAll() {
  chat.innerHTML = "";
  raw.textContent = "";
  renderList(upiList, []);
  renderList(bankList, []);
  renderList(linkList, []);
  riskBadge.textContent = "RISK: 0%";
  phoneValue.textContent = "NOT DETECTED";
  cryptoValue.textContent = "NOT DETECTED";
  emailValue.textContent = "NOT DETECTED";
  bankUpiValue.textContent = "NOT DETECTED";
  linkValue.textContent = "NOT DETECTED";
  originValue.textContent = "UNKNOWN";
  if (personaName) personaName.textContent = "Elderly";
  if (personaAge) personaAge.textContent = "—";
  if (personaDevice) personaDevice.textContent = "—";
  if (personaTech) personaTech.textContent = "—";
  if (personaExp) personaExp.textContent = "—";
  if (askedFields) askedFields.textContent = "—";
  if (scamIntent) scamIntent.textContent = "UNKNOWN";
  if (scamScore) scamScore.textContent = "0";
  if (scamReasons) scamReasons.textContent = "—";
  threatState.phones.clear();
  threatState.emails.clear();
  threatState.cryptos.clear();
  threatState.origins.clear();
  if (allUpiValue) allUpiValue.textContent = "—";
  if (allBankValue) allBankValue.textContent = "—";
  if (allLinksValue) allLinksValue.textContent = "—";
  setStatus(false, "Disconnected");
}

sendBtn.addEventListener("click", sendMessage);
clearBtn.addEventListener("click", clearAll);
pingBtn.addEventListener("click", pingServer);
if (personaInput) {
  personaInput.addEventListener("change", () => updateThreatCard({}, ""));
}

renderList(upiList, []);
renderList(bankList, []);
renderList(linkList, []);
updateThreatCard(
  { scam_detected: false, extracted_intel: { upi_ids: [], bank_accounts: [], phishing_links: [] } },
  ""
);
