// src/scheduler/index.js
import cron from 'node-cron';
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { makeExactlyFiveOnusSignals, getOnusTop5GainersForMorning } from '../signals/fiveMaker.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const TZ = process.env.TZ || 'Asia/Ho_Chi_Minh';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function nextSlotString(date = new Date()) {
  const d = new Date(date);
  const m = d.getMinutes();
  const add = m < 15 ? (15 - m) : m < 45 ? (45 - m) : (60 - m);
  d.setMinutes(m + add, 0, 0);
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

export function startSchedulers() {
  // 06:00 — chào sáng (Top 5 tăng thật từ ONUS nếu có)
  cron.schedule('0 6 * * *', async () => {
    if (!CHAT_ID) return;
    const top5 = await getOnusTop5GainersForMorning();
    const topLine = top5.length ? `• Top 5 tăng: ${top5.join(', ')}` : '• Top 5 tăng: (đang tổng hợp)';
    await sendMessage(
      CHAT_ID,
      `Chào buổi sáng nhé bạn ☀️\n${topLine}\n• Funding/Volume/Xu hướng: …\n• Xu hướng hôm nay: <b>TĂNG/GIẢM/TRUNG LẬP</b>  🟩 Tăng X%  |  🟥 Giảm Y% (theo sàn, khung 4h)\n(1 USD ≈ X <b>VND</b> • 06:00)`
    );
  }, { timezone: TZ });

  // 07:00 — lịch vĩ mô (placeholder gọn, sẽ nối ForexFactory sau)
  cron.schedule('0 7 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '📅 07:00 Lịch vĩ mô (đang kết nối ForexFactory – bản tiếp theo).');
  }, { timezone: TZ });

  // 06:15 → 21:45 — mỗi 30'
  cron.schedule('15,45 6-21 * * *', async () => {
    if (!CHAT_ID) return;

    const cfg = await getConfig();
    const ex = (cfg.active_exchange || 'ONUS').toUpperCase();
    if (ex !== 'ONUS') return; // chưa bật sàn khác

    // CHỈ gửi khi chắc chắn có 5 lệnh
    const sigs = await makeExactlyFiveOnusSignals();
    if (!sigs) return;

    const nextTime = nextSlotString();
    await sendMessage(CHAT_ID, batchHeader(nextTime, ex));
    for (const s of sigs) {
      await sendMessage(CHAT_ID, signalMessage(s));
      await sleep(160);
    }
  }, { timezone: TZ });

  // 22:00 — tổng kết (giữ placeholder)
  cron.schedule('0 22 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '🌙 Tổng kết hôm nay\n• TP: x | SL: y | Thoát: z\n• BUY: a — SELL: b\nNgủ ngon nha!');
  }, { timezone: TZ });
}
