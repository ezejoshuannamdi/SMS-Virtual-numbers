from datetime import datetime, timezone
import hashlib
import hmac
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sms_hub.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class InboundMessage(Base):
    __tablename__ = "inbound_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_message_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    to_number: Mapped[str] = mapped_column(String(32), index=True)
    from_number: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(engine)

app = FastAPI(title="CodeSpace SMS Hub", version="0.1.0")

COUNTRIES = [
    {"code": "US", "name": "United States", "dial_code": "+1"},
    {"code": "GB", "name": "United Kingdom", "dial_code": "+44"},
    {"code": "CA", "name": "Canada", "dial_code": "+1"},
    {"code": "IT", "name": "Italy", "dial_code": "+39"},
]


class ProvisionRequest(BaseModel):
    country: str = Field(pattern="^(US|GB|CA|IT)$")
    use_case: str = Field(min_length=10, max_length=500)


class InboundPayload(BaseModel):
    message_id: str = Field(min_length=1, max_length=160)
    to: str = Field(min_length=5, max_length=32)
    from_: str = Field(alias="from", min_length=5, max_length=32)
    body: str = Field(min_length=1, max_length=5000)


@app.get("/health")
def health():
    return {"status": "ok", "service": "codespace-sms-hub", "mode": os.getenv("SMS_PROVIDER", "mock")}


@app.get("/api/countries")
def countries():
    return {"countries": COUNTRIES}


@app.get("/api/numbers")
def numbers():
    # Live inventory is intentionally unavailable until an approved provider is configured.
    return {"mode": "mock", "numbers": [], "message": "Connect an approved SMS provider to view purchasable inventory."}


@app.post("/api/numbers/provision")
def provision_number(payload: ProvisionRequest):
    # Never pretend a number was purchased. A real adapter must enforce provider and legal checks.
    if payload.country not in {c["code"] for c in COUNTRIES}:
        raise HTTPException(status_code=400, detail="Unsupported country")
    return {
        "status": "not_configured",
        "country": payload.country,
        "message": "Number provisioning is not active. Configure an approved provider and complete its compliance review first.",
    }


@app.post("/webhooks/sms/inbound")
async def inbound_sms(request: Request, x_hub_signature: Optional[str] = Header(default=None)):
    raw = await request.body()
    secret = os.getenv("WEBHOOK_SECRET")
    if os.getenv("APP_ENV", "development") == "production":
        if not secret:
            raise HTTPException(status_code=503, detail="Webhook secret is not configured")
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        supplied = (x_hub_signature or "").removeprefix("sha256=")
        if not hmac.compare_digest(expected, supplied):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = InboundPayload.model_validate_json(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid inbound SMS payload")

    with SessionLocal() as db:
        existing = db.scalar(select(InboundMessage).where(InboundMessage.provider_message_id == payload.message_id))
        if existing:
            return {"status": "duplicate_ignored"}
        db.add(InboundMessage(
            provider_message_id=payload.message_id,
            to_number=payload.to,
            from_number=payload.from_,
            body=payload.body,
        ))
        db.commit()
    return {"status": "accepted"}


@app.get("/api/messages")
def list_messages(limit: int = 50):
    limit = max(1, min(limit, 100))
    with SessionLocal() as db:
        rows = db.scalars(select(InboundMessage).order_by(InboundMessage.id.desc()).limit(limit)).all()
        return {"messages": [
            {"id": row.id, "to": row.to_number, "from": row.from_number,
             "body": row.body, "received_at": row.received_at.isoformat()}
            for row in rows
        ]}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CodeSpace SMS Hub</title><style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#0b1020;color:#eef2ff}
body{margin:0;padding:32px}.wrap{max-width:1050px;margin:auto}.top{display:flex;justify-content:space-between;align-items:center;gap:16px}
.tag{border:1px solid #334155;border-radius:99px;padding:7px 12px;color:#a5f3fc;font-size:12px}
h1{font-size:34px;margin:26px 0 8px}.muted{color:#94a3b8}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:28px 0}
.card{background:#141c31;border:1px solid #26334d;border-radius:16px;padding:20px}.card strong{display:block;font-size:20px;margin:8px 0}
button{background:#67e8f9;color:#082f49;border:0;border-radius:10px;padding:11px 16px;font-weight:700;cursor:pointer}
table{width:100%;border-collapse:collapse;margin-top:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #26334d;font-size:14px}
.notice{padding:14px;border-radius:12px;background:#172554;color:#bfdbfe;line-height:1.5}
</style></head><body><main class="wrap">
<div class="top"><b>◈ CodeSpace SMS Hub</b><span class="tag">DEVELOPMENT · MOCK MODE</span></div>
<h1>Inbound SMS workspace</h1><p class="muted">A compliant messaging workspace for numbers your business is authorized to manage.</p>
<div class="grid">
<div class="card"><span class="muted">Supported markets</span><strong>US · UK · CA · IT</strong><span class="muted">Country catalogue ready</span></div>
<div class="card"><span class="muted">Provisioned numbers</span><strong id="numberCount">0</strong><span class="muted">Provider connection pending</span></div>
<div class="card"><span class="muted">Inbound messages</span><strong id="messageCount">0</strong><span class="muted">Webhook endpoint available</span></div>
</div>
<div class="notice">Number purchasing is disabled until an approved telecom provider is connected and the intended business use case is approved. This service is not designed to bypass third-party platform verification.</div>
<section class="card" style="margin-top:20px"><div class="top"><h2>Recent inbound messages</h2><button onclick="loadMessages()">Refresh</button></div>
<table><thead><tr><th>To</th><th>From</th><th>Message</th><th>Received</th></tr></thead><tbody id="messages"><tr><td colspan="4" class="muted">No messages received yet.</td></tr></tbody></table></section>
<p class="muted" style="margin-top:24px">CodeSpace SMS Hub · API documentation at <a href="/docs" style="color:#67e8f9">/docs</a></p>
</main><script>
async function loadMessages(){try{const r=await fetch('/api/messages');const d=await r.json();document.getElementById('messageCount').textContent=d.messages.length;document.getElementById('messages').innerHTML=d.messages.length?d.messages.map(m=>'<tr><td>'+esc(m.to)+'</td><td>'+esc(m.from)+'</td><td>'+esc(m.body)+'</td><td>'+new Date(m.received_at).toLocaleString()+'</td></tr>').join(''):'<tr><td colspan="4" class="muted">No messages received yet.</td></tr>'}catch(e){console.error(e)}}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
loadMessages();setInterval(loadMessages,15000);
</script></body></html>""")
