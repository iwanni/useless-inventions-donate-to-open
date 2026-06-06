from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from saweriaqris import create_payment_qr, paid_status
from datetime import datetime, timedelta
from upstash_redis import Redis
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Upstash Redis ────────────────────────────────────────────────
r = Redis(
    url=os.environ["KV_REST_API_URL"],
    token=os.environ["KV_REST_API_TOKEN"]
)

SESSION_TTL_MIN  = 15
PAID_TTL_HOURS   = 24
SAWERIA_USERNAME = "iwanni"
DONATION_AMOUNT  = 10000

# ─── Helper ───────────────────────────────────────────────────────
def get_session(transaction_id: str):
    raw = r.get(f"session:{transaction_id}")
    if not raw:
        return None
    return json.loads(raw) if isinstance(raw, str) else raw

def set_session(transaction_id: str, data: dict, ttl_seconds: int):
    r.setex(f"session:{transaction_id}", ttl_seconds, json.dumps(data))

# ─── Konten rahasia ───────────────────────────────────────────────
SECRET_HTML1 = """
<div class="blur-row">
  <div class="blur-icon">🙏</div>
  <div class="blur-text">
    <strong>Tolong pak, bu, bang, kak — terima saya</strong>
    <span>Saya sudah ngelamar ke mana-mana. Ini bukan lebay.</span>
  </div>
</div>
<div class="blur-row">
  <div class="blur-icon">☕</div>
  <div class="blur-text">
    <strong>Tahan banting, anti drama, pro kopi</strong>
    <span>Lembur sampai subuh? Fine. Asal ada colokan & wifi.</span>
  </div>
</div>
<div class="blur-row">
  <div class="blur-icon">📈</div>
  <div class="blur-text">
    <strong>Growth mindset sejati</strong>
    <span>Tiap kali error saya bilang "ini learning experience." Tulus.</span>
  </div>
</div>
"""

SECRET_HTML2 = """
<div class="blur-row">
  <div class="blur-icon">💰</div>
  <div class="blur-text">
    <strong>Ada angkanya di sini — unlock dulu ya Pak/Bu 🥺</strong>
    <span>Bisa nego. Sangat bisa nego. Saya fleksibel sekali.</span>
  </div>
</div>
"""

SECRET_HTML3 = """
<div class="blur-row">
  <div class="blur-icon">📱</div>
  <div class="blur-text">
    <strong>Nomor HP tersembunyi di sini</strong>
    <span>WA dibalas cepat. Lebih cepat dari deploy production.</span>
  </div>
</div>
<div class="blur-row">
  <div class="blur-icon">📧</div>
  <div class="blur-text">
    <strong>Email juga ada — tenang aja</strong>
    <span>Reply dalam 5 menit. Kecuali lagi sholat atau makan siang.</span>
  </div>
</div>
<div class="blur-row">
  <div class="blur-icon">📍</div>
  <div class="blur-text">
    <strong>Lokasi: Jakarta — siap WFO, WFH, WFA</strong>
    <span>Yang penting jangan suruh ngantor jam 6 pagi.</span>
  </div>
</div>
"""

# ─── Endpoints ────────────────────────────────────────────────────

@app.get("/debug")
async def debug():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://saweria.co/iwanni")

    return {
        "status": r.status_code,
        "body": r.text[:1000]
    }

@app.get("/api/qr")
async def generate_qr():
    try:
        result = create_payment_qr(
            SAWERIA_USERNAME,
            DONATION_AMOUNT,
            "Donatur",
            "dummy@example.com",
            "unlock"
        )
        qr_string      = result[0]
        transaction_id = result[1]

        set_session(transaction_id, {"paid": False}, ttl_seconds=SESSION_TTL_MIN * 60)

        return {
            "transactionId": transaction_id,
            "qrString": qr_string,
            "amount": DONATION_AMOUNT
        }
    except Exception as e:
        return {"error": str(e)}, 500


@app.post("/api/webhook")
async def receive_webhook(request: Request):
    try:
        body = await request.json()
        transaction_id = body.get("id")

        if transaction_id:
            session = get_session(transaction_id)
            if session:
                set_session(transaction_id, {"paid": True}, ttl_seconds=int(PAID_TTL_HOURS * 3600))
                print(f"✅ Paid: {transaction_id} | amount: {body.get('amount_raw')}")
            else:
                print(f"⚠️  Webhook masuk tapi session tidak ditemukan: {transaction_id}")

        return {"ok": True}
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/status/{transaction_id}")
async def check_status(transaction_id: str):
    session = get_session(transaction_id)
    if not session:
        return {"paid": False, "expired": True}
    return {"paid": session["paid"], "expired": False}


@app.get("/api/content/{transaction_id}")
async def get_content(transaction_id: str):
    session = get_session(transaction_id)
    if not session or not session["paid"]:
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    return {"html1": SECRET_HTML1, "html2": SECRET_HTML2, "html3": SECRET_HTML3}


# ─── Serve static files ───────────────────────────────────────────
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
