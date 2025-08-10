// src/scheduler/index.js
import cron from 'node-cron';
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { getOnusTop5GainersForMorning } from '../signals/fiveMaker.js';
import { getOnusSnapshot } from '../sources/onus/scrape.js';
import { saveOnusSnapshot } from '../storage/onusRepo.js';
import { getOnusMeta } from '../sources/onus/cache.js';
import { prepareNextBatch, getPreparedBatch } from '../batch/builder.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const TZ = process.env.TZ || 'Asia/Ho_Chi_Minh';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function nextSlot(date = new Date()) {
  const d = new Date(date);
  const m = d.getMinutes();
  const add = m < 15 ? (15 - m) : m < 45 ? (45 - m) : (60 - m);
  d.setMinutes(m + add, 0, 0);
  return d;
}
function nextSlotString(d) {
  return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

async function preWarmOnce() {
  try { const rows = await getOnusSnapshot(); await saveOnusSnapshot(rows, Date.now()); } catch {}
}

export function startSchedulers() {
  // Watchdog 2’ → cache >120s thì ép scrape
  cron.schedule('*/2 * * * *', async () => {
    const meta = getOnusMeta();
    if (!meta.ageSec || meta.ageSec <= 120) return;
    await preWarmOnce();
  }, { timezone: TZ });

  // Pre‑warm + chuẩn bị batch trước 5 phút (10 & 40)
  cron.schedule('10,40 * * * *', async () => {
    await preWarmOnce();
    await prepareNextBatch(); // tạo sẵn 5 kèo cho slot 15/45
  }, { timezone: TZ });

  // 06:00 — chào sáng
  cron.schedule('0 6 * * *', async () => {
    if (!CHAT_ID) return;
    const top5 = await getOnusTop5GainersForMorning();
    const topLine = top5.length ? `• Top 5 tăng: ${top5.join(', ')}` : '• Top 5 tăng: (đang tổng hợp)';
    await sendMessage(CHAT_ID,
      `Chào buổi sáng nhé bạn ☀️\n${topLine}\n• Funding/Volume/Xu hướng: …\n• Xu hướng hôm nay: <b>TĂNG/GIẢM/TRUNG LẬP</b>  🟩 Tăng X%  |  🟥 Giảm Y% (theo sàn, khung 4h)\n(1 USD ≈ X <b>VND</b> • 06:00)`
    );
  }, { timezone: TZ });

  // 07:00 — lịch vĩ mô (để sau nối FF)
  cron.schedule('0 7 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '📅 07:00 Lịch vĩ mô (đang kết nối ForexFactory).');
  }, { timezone: TZ });

  // 06:15 → 21:45 — gửi batch đã chuẩn bị (5 lệnh)
  cron.schedule('15,45 6-21 * * *', async () => {
    if (!CHAT_ID) return;

    const cfg = await getConfig();
    const ex = (cfg.active_exchange || 'ONUS').toUpperCase();
    if (ex !== 'ONUS') return;

    const slot = nextSlot(); // slot hiện tại
    // nếu chưa ready, đợi tối đa 30s vừa ép scrape vừa prepare
    let ready = await getPreparedBatch(slot);
    for (let i = 0; !ready && i < 6; i++) {
      await preWarmOnce();
      await prepareNextBatch();
      await sleep(5000);
      ready = await getPreparedBatch(slot);
    }
    if (!ready || ready.length < 5) return; // im lặng nếu chưa đủ 5

    await sendMessage(CHAT_ID, batchHeader(nextSlotString(slot), ex));
    for (const s of ready) {
      await sendMessage(CHAT_ID, signalMessage(s));
      await sleep(140);
    }
  }, { timezone: TZ });

  // 22:00 — tổng kết (placeholder)
  cron.schedule('0 22 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '🌙 Tổng kết hôm nay\n• TP: x | SL: y | Thoát: z\n• BUY: a — SELL: b\nNgủ ngon nha!');
  }, { timezone: TZ });
}
