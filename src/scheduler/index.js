import express from 'express';
import dotenv from 'dotenv';
import bodyParser from 'body-parser';
import { startSchedulers } from './src/scheduler/index.js';
import { handleUpdate } from './src/telegram/bot.js';

dotenv.config();

const app = express();
app.use(bodyParser.json());

// webhook từ Telegram (bạn đã set ở Render)
app.post(`/webhook/${process.env.WEBHOOK_SECRET}`, async (req, res) => {
  try {
    await handleUpdate(req.body); // hiện tại chưa làm gì, để sẵn
    res.sendStatus(200);
  } catch (e) {
    console.error('[WEBHOOK]', e);
    res.sendStatus(500);
  }
});

// tiện set webhook nhanh
app.get('/setup-webhook', async (req, res) => {
  if (req.query.token !== process.env.WEBHOOK_SECRET) {
    return res.status(403).json({ ok: false, error: 'Invalid token' });
  }
  const url = `${process.env.PUBLIC_URL}/webhook/${process.env.WEBHOOK_SECRET}`;
  const api = `https://api.telegram.org/bot${process.env.BOT_TOKEN}/setWebhook?url=${encodeURIComponent(url)}`;
  try {
    const r = await fetch(api);
    const j = await r.json();
    res.json(j);
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e) });
  }
});

app.get('/', (_req, res) => res.send('Autiner minimal bot is running'));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log('Server listening on', PORT);
  startSchedulers(); // chỉ 06:00 & 07:00
});
