# Saweria CV Unlock 🔓

Website CV dengan unlock otomatis setelah donasi Saweria QRIS.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set username Saweria
Edit `main.py`, ganti:
```python
SAWERIA_USERNAME = "iwanni"   # ← username Saweria kamu
DONATION_AMOUNT  = 1000       # ← nominal donasi
```

### 3. Jalankan backend
```bash
python main.py
```
Backend berjalan di `http://localhost:8000`

### 4. Buka website
Buka browser → `http://localhost:8000`

---

## Setup Webhook Saweria (untuk production)

1. Login ke saweria.co
2. Buka **Integrations → Webhook**
3. Masukkan URL backend: `https://yourdomain.com/api/webhook`
4. Aktifkan toggle **Nyalakan**
5. Klik **Simpan**

> ⚠️ Untuk testing lokal, webhook tidak bisa diterima dari Saweria karena localhost tidak bisa diakses dari internet.
> Gunakan [ngrok](https://ngrok.com) untuk expose localhost ke public URL:
> ```bash
> ngrok http 8000
> ```
> Lalu set webhook URL ke `https://xxxx.ngrok.io/api/webhook`

---

## Flow

```
User buka website
→ Frontend request GET /api/qr
→ Backend generate QRIS unik via saweriaqris → dapat qr_string + transaction_id
→ Frontend render QR pakai qrcode.js

User scan QR → transfer

Saweria POST /api/webhook → backend tandai transaction_id = PAID

Frontend polling GET /api/status/:id setiap 3 detik
→ Kalau paid = true → gambar unlock otomatis 🎉
```

---

## Stack
- Backend: Python + FastAPI
- QRIS Generator: `saweriaqris` (pip)
- QR Render: `qrcode.js` (CDN)
- Frontend: HTML/CSS/JS static
