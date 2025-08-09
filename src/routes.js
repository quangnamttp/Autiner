import express from 'express';
import { setWebhook, handleUpdate, sendMessage } from './telegram/bot.js';
import { buildMainMenu } from './telegram/menu.js';
import { getConfig } from './storage/configRepo.js';

const router = express.Router();
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET;
const BASE_URL = process.env.BASE_URL;

router.post(`/webhook/${WEBHOOK_SECRET}`, async (req, res) => {
  try { await handleUpdate(req.body); } catch {}
  res.sendStatus(200);
});

router.all('/setup-webhook', async (req, res) => {
  const token = (req.query.token || '').toString();
  if (!token || token !== WEBHOOK_SECRET) return res.status(401).json({ error: 'unauthorized' });
  const resp = await setWebhook(`${BASE_URL}/webhook/${WEBHOOK_SECRET}`);
  res.json(resp);
});

router.get('/status', async (_req, res) => {
  const cfg = await getConfig();
  res.json({
    ok: true,
    active_exchange: cfg.active_exchange,
    schedule: '06:15–21:45 (30p); 06:00; 07:00; 22:00',
    frequency: '30 phút (cố định)'
  });
});

router.get('/send-menu', async (req, res) => {
  const chatId = req.query.chatId;
  if (!chatId) return res.status(400).send('need ?chatId=');
  const menu = await buildMainMenu();
  await sendMessage(chatId, 'Menu điều khiển', { reply_markup: menu });
  res.send('sent');
});

export { router };
