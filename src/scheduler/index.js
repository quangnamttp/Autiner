// src/scheduler/index.js
import cron from 'node-cron';
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { makeFiveOnusSignals } from '../signals/fiveMaker.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const TZ = process.env.TZ || 'Asia/Ho_Chi_Minh';

let isBatchRunning = false;

function nextSlotString(date = new Date()) {
  const d = new Date(date);
  const m = d.getMinutes();
  const add = m < 15 ? (15 - m) : m < 45 ? (45 - m) : (60 - m);
  d.setMinutes(m + add, 0, 0);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

export function startSchedulers() {
  // 06:00 — chào sáng
  cron.schedule('0 6 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(
      CHAT_ID,
      'Chào buổi sáng nhé bạn ☀️\n• Top 5 tăng: (sẽ gắn dữ liệu sàn)\n• Funding/Volume/Xu hướng: ...\n• Xu hướng hôm nay: <b>TĂNG/GIẢM/TRUNG LẬP</b>  🟩 Tăng X%  |  🟥 Giảm Y% (theo sàn, khung 4h)\n(1 USD ≈ X <b>VND</b> • 06:00)'
    );
  }, { timezone: TZ });

  // 07:00 — lịch vĩ mô (placeholder)
  cron.schedule('0 7 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '📅 07:00 Lịch vĩ mô (sẽ lấy từ ForexFactory, lọc High Impact).');
  }, { timezone: TZ });

  // 06:15 → 21:45 — mỗi 30'
  cron.schedule('15,45 6-21 * * *', async () => {
    if (!CHAT_ID) return;
    if (isBatchRunning) return;
    isBatchRunning = true;

    try {
      const cfg = await getConfig();
      const ex = (cfg.active_exchange || 'ONUS').toUpperCase();
      const nextTime = nextSlotString();
      await sendMessage(CHAT_ID, batchHeader(nextTime, ex));

      if (ex !== 'ONUS') {
        await sendMessage(CHAT_ID, `⚠️ Sàn ${ex} chưa cấu hình nguồn dữ liệu thật. Bỏ batch để tránh sai giá.`);
        return;
      }

      const sigs = await makeFiveOnusSignals();
      for (const s of sigs) {
        await sendMessage(CHAT_ID, signalMessage(s));
        await new Promise(r => setTimeout(r, 180));
      }
    } finally {
      isBatchRunning = false;
    }
  }, { timezone: TZ });

  // 22:00 — tổng kết (placeholder)
  cron.schedule('0 22 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '🌙 Tổng kết hôm nay\n• TP: x | SL: y | Thoát: z\n• BUY: a — SELL: b\nNgủ ngon nha!');
  }, { timezone: TZ });
}
