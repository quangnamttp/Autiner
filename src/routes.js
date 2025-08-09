import express from 'express';
import { setWebhook, handleUpdate, sendMessage } from './telegram/bot.js';
import { buildMainMenu } from './telegram/menu.js';
import { getConfig } from './storage/configRepo.js';

const router = express.Router();
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET;
const BASE_URL = process.env.BASE_URL;

// Webhook bí mật: Telegram sẽ POST vào đây
router.post(`/webhook/${WEBHOOK_SECRET}`, async (req, res) => {
  try {
    await handleUpdate(req.body);
    res.sendStatus(200);
  } catch (_e) {
    // tránh Telegram retry bão
    res.sendStatus(200);
  }
});

// Tiện set webhook (hỗ trợ GET/POST)
router.all('/setup-webhook', async (req, res) => {
  const token = (req.query.token || '').toString();
  if (!token || token !== WEBHOOK_SECRET) {
    return res.status(401).json({ error: 'unauthorized' });
  }
  const url = `${BASE_URL}/webhook/${WEBHOOK_SECRET}`;
  const resp = await setWebhook(url);
  res.json(resp);
});

// /status nhanh (text)
router.get('/status', async (_req, res) => {
  const cfg = await getConfig();
  res.json({
    ok: true,
    active_exchange: cfg.active_exchange,
    schedule: '06:15–21:45, mỗi 30 phút; 06:00 chào sáng; 07:00 lịch vĩ mô; 22:00 tổng kết',
    frequency: '30 phút (cố định)',
    sources: {
      onus: 'Batch 2/3',
      mexc: 'Batch 2/3',
      nami: 'Batch 2/3'
    }
  });
});

// Gửi menu test (tiện debug trên web, không bắt buộc)
router.get('/send-menu', async (req, res) => {
  const chatId = req.query.chatId;
  if (!chatId) return res.status(400).send('need ?chatId=');
  const menu = await buildMainMenu();
  await sendMessage(chatId, 'Menu điều khiển', { reply_markup: menu });
  res.send('sent');
});

export { router };
