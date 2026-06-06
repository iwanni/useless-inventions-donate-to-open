from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from saweriaqris import create_payment_qr, paid_status
from datetime import datetime, timedelta
import asyncio
import threading

app = FastAPI()

# CORS — izinkan frontend akses backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory store ──────────────────────────────────────────────
# Format: { transaction_id: { "paid": bool, "created_at": datetime } }
sessions = {}
sessions_lock = threading.Lock()

# ─── Config ───────────────────────────────────────────────────────
SAWERIA_USERNAME  = "iwanni"   # ← ganti dengan username Saweria kamu
DONATION_AMOUNT   = 10000      # ← minimum Rp 10.000 (limit dari Saweria)
SESSION_TTL_MIN   = 15         # sesi belum bayar kadaluarsa setelah 15 menit
PAID_TTL_HOURS    = 24         # sesi sudah bayar bertahan 24 jam (persist refresh)

# ─── Konten rahasia — hanya dikirim setelah paid ──────────────────
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

# ─── Cleanup expired sessions ─────────────────────────────────────
def cleanup_sessions():
    now = datetime.now()
    with sessions_lock:
        expired = [
            tid for tid, data in sessions.items()
            if (
                # Belum bayar: expired setelah 15 menit
                (not data["paid"] and now - data["created_at"] > timedelta(minutes=SESSION_TTL_MIN))
                or
                # Sudah bayar: expired setelah 24 jam
                (data["paid"] and now - data["created_at"] > timedelta(hours=PAID_TTL_HOURS))
            )
        ]
        for tid in expired:
            del sessions[tid]

# ─── Endpoints ────────────────────────────────────────────────────

@app.get("/api/qr")
async def generate_qr():
    """Generate QRIS unik per sesi user."""
    cleanup_sessions()
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

        with sessions_lock:
            sessions[transaction_id] = {
                "paid": False,
                "created_at": datetime.now()
            }

        return {
            "transactionId": transaction_id,
            "qrString": qr_string,
            "amount": DONATION_AMOUNT
        }
    except Exception as e:
        return {"error": str(e)}, 500


@app.post("/api/webhook")
async def receive_webhook(request: Request):
    """Terima notifikasi dari Saweria saat donasi berhasil."""
    try:
        body = await request.json()
        transaction_id = body.get("id")

        if transaction_id:
            with sessions_lock:
                if transaction_id in sessions:
                    sessions[transaction_id]["paid"] = True
                    print(f"✅ Paid: {transaction_id} | amount: {body.get('amount_raw')}")
                else:
                    print(f"⚠️  Webhook masuk tapi session tidak ditemukan: {transaction_id}")

        return {"ok": True}
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/status/{transaction_id}")
async def check_status(transaction_id: str):
    """Frontend polling: cek apakah transaksi sudah dibayar."""
    with sessions_lock:
        session = sessions.get(transaction_id)

    if not session:
        return {"paid": False, "expired": True}

    # Belum bayar dan sudah 15 menit → expired
    if not session["paid"] and datetime.now() - session["created_at"] > timedelta(minutes=SESSION_TTL_MIN):
        return {"paid": False, "expired": True}

    return {"paid": session["paid"], "expired": False}


@app.get("/api/content/{transaction_id}")
async def get_content(transaction_id: str):
    """Kirim konten rahasia — HANYA kalau transaction_id sudah paid."""
    with sessions_lock:
        session = sessions.get(transaction_id)

    if not session or not session["paid"]:
        return JSONResponse(status_code=403, content={"error": "Forbidden"})

    return {"html1": SECRET_HTML1, "html2": SECRET_HTML2, "html3": SECRET_HTML3}


# ─── Serve static files (index.html) ──────────────────────────────
app.mount("/", StaticFiles(directory=".", html=True), name="static")


# ─── Run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

