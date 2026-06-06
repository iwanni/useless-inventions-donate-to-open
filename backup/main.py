from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from upstash_redis import Redis
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

# ─── Config ───────────────────────────────────────────────────────
PAID_TTL_SECONDS = 5 * 60  # 5 menit setelah webhook → CV tutup lagi
GLOBAL_KEY       = "cv_unlocked"

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

@app.post("/api/webhook")
async def receive_webhook(request: Request):
    """Terima notifikasi dari Saweria → set global unlock selama 5 menit."""
    try:
        body = await request.json()
        amount = body.get("amount_raw", 0)
        donator = body.get("donator_name", "someone")

        # Set global key dengan TTL 5 menit
        r.setex(GLOBAL_KEY, PAID_TTL_SECONDS, "1")
        print(f"✅ Webhook dari {donator} | amount: {amount} → CV unlocked 5 menit")

        return {"ok": True}
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/status")
async def check_status():
    """Frontend polling: cek apakah CV sedang unlocked."""
    unlocked = r.get(GLOBAL_KEY)
    # Ambil sisa TTL untuk countdown di frontend
    ttl = r.ttl(GLOBAL_KEY)
    return {
        "unlocked": bool(unlocked),
        "ttl": ttl if ttl and ttl > 0 else 0
    }


@app.get("/api/content")
async def get_content():
    """Kirim konten rahasia — HANYA kalau global key ada (masih dalam 5 menit)."""
    unlocked = r.get(GLOBAL_KEY)
    if not unlocked:
        return JSONResponse(status_code=403, content={"error": "Forbidden"})
    return {"html1": SECRET_HTML1, "html2": SECRET_HTML2, "html3": SECRET_HTML3}


# ─── Serve static files ───────────────────────────────────────────
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
