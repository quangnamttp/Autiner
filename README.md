# autiner (Batch 1)

## Chạy local
1) `cp .env.example .env` và điền BOT_TOKEN, WEBHOOK_SECRET (tạm), DATABASE_URL (nếu có Postgres local).
2) `npm i`
3) `npm start`
4) Gọi `POST http://localhost:3000/setup-webhook?token=WEBHOOK_SECRET`

## Deploy Render (tóm tắt)
- Build: `npm ci`
- Start: `npm start`
- Env: BOT_TOKEN, ALLOWED_TELEGRAM_USER_ID, WEBHOOK_SECRET, BASE_URL, DATABASE_URL, TZ
- Sau khi “Live”: mở `https://autiner.onrender.com/setup-webhook?token=WEBHOOK_SECRET`
