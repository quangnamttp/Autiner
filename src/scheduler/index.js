// src/scheduler/index.js
import cron from 'node-cron';
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';

// ONUS data (Batch 3)
import { getOnusSnapshot } from '../sources/onus/scrape.js';
import { pickTop5SignalsFromOnus } from '../signals/generator.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const TZ = process.env.TZ || 'Asia/Ho_Chi_Minh';

// chống trùng chạy khi tick trùng (Render có thể “giật” container)
let isBatchRunning = false;
// chống spam cảnh báo khi ONUS lỗi (10 phút 1 lần)
let lastOnusAlertAt = 0;

// Tính mốc HH:mm kế tiếp theo khung 15/45 phút (theo giờ VN)
function nextSlotString(date = new Date()) {
  const d = new Date(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: TZ,
      hour12: false,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    }).format(date).replace(
      /(\d{2})\/(\d{2})\/(\d{4}), (\d{2}):(\d{2}):(\d{2})/,
      (_m, dd, MM, yyyy, HH, mm, ss) => `${yyyy}-${MM}-${dd}T${HH}:${mm}:${ss}`
    )
  );

  const m = d.getMinutes();
  const add = m < 15 ? (15 - m) : m < 45 ? (45 - m) : (60 - m);
  d.setMinutes(m + add, 0, 0);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

export function startSchedulers() {
  if (!CHAT_ID) {
    console.warn('[scheduler] ALLOWED_TELEGRAM_USER_ID chưa được cấu hình.');
  }

  // 06:00 — Chào buổi sáng
  cron.schedule('0 6 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(
      CHAT_ID,
      'Chào buổi sáng nhé bạn ☀️\n• Top 5 tăng: (sẽ gắn dữ liệu sàn)\n• Funding/Volume/Xu hướng: ...\n• Xu hướng hôm nay: <b>TĂNG/GIẢM/TRUNG LẬP</b>  🟩 Tăng X%  |  🟥 Giảm Y% (theo sàn, khung 4h)\n(1 USD ≈ X <b>VND</b> • 06:00)'
    );
  }, { timezone: TZ });

  // 07:00 — Lịch vĩ mô (ForexFactory)
  cron.schedule('0 7 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '📅 07:00 Lịch vĩ mô (sẽ lấy từ ForexFactory, lọc high impact).');
  }, { timezone: TZ });

  // 06:15 → 21:45 — Mỗi 30 phút
  cron.schedule('15,45 6-21 * * *', async () => {
    if (!CHAT_ID) return;

    // khóa chống trùng
    if (isBatchRunning) return;
    isBatchRunning = true;

    try {
      const cfg = await getConfig();
      const ex = cfg.active_exchange || 'ONUS';
      const nextTime = nextSlotString();

      // Tiêu đề nhóm trước
      await sendMessage(CHAT_ID, batchHeader(nextTime, ex));

      if (ex === 'ONUS') {
        // ONUS: lấy dữ liệu thật, nếu lỗi -> cảnh báo & dừng batch này
        try {
          const snapshot = await getOnusSnapshot();                 // [{symbol,last,change,funding,vol5m}]
          const signals = pickTop5SignalsFromOnus(snapshot);        // 5 tín hiệu chắc
          if (!signals.length) throw new Error('Không có tín hiệu phù hợp.');

          // Gửi 5 tín hiệu RIÊNG LẺ
          for (const s of signals) {
            await sendMessage(CHAT_ID, signalMessage(s));
            await new Promise(r => setTimeout(r, 300)); // đệm nhẹ, tránh gộp
          }
        } catch (err) {
          const now = Date.now();
          if (now - lastOnusAlertAt > 10 * 60 * 1000) {
            lastOnusAlertAt = now;
            await sendMessage(
              CHAT_ID,
              `⚠️ Onus dữ liệu không đạt chuẩn (${err.message}).\nBatch ${nextTime} tạm dừng để giữ độ chính xác.\nGõ /status để xem chi tiết.`
            );
          }
          return; // dừng batch (không gửi mock/fallback)
        }
      } else {
        // MEXC/NAMI: hiện tại giữ mock (đúng format) để bạn thấy nhịp
        const currency = ex === 'MEXC' ? 'USD' : 'VND';
        const examples = ex === 'MEXC'
          ? [
              { symbol: '1000CATUSDT', entry: 0.009538, tp: 0.009624, sl: 0.009481, side: 'LONG' },
              { symbol: 'BTCUSDT',     entry: 58000.5,  tp: 58200.0,  sl: 57700.0,  side: 'LONG' },
              { symbol: 'ETHUSDT',     entry: 2500.2,   tp: 2520.0,   sl: 2488.0,   side: 'LONG' },
              { symbol: 'DOGEUSDT',    entry: 0.126,    tp: 0.128,    sl: 0.124,    side: 'SHORT' },
              { symbol: 'PEPEUSDT',    entry: 0.0000123,tp: 0.0000126,sl: 0.0000120,side: 'LONG' }
            ]
          : [
              { symbol: 'BTCVND', entry: 1230000, tp: 1250000, sl: 1210000, side: 'LONG' },
              { symbol: 'ETHVND', entry:   78500, tp:   79300, sl:   77800, side: 'SHORT' },
              { symbol: 'SOLVND', entry:   32800, tp:   33200, sl:   32400, side: 'LONG' },
              { symbol: 'BNBVND', entry:  142000, tp:  143400, sl:  140600, side: 'LONG' },
              { symbol: 'ARBVND', entry:   18900, tp:   19200, sl:   18600, side: 'SHORT' }
            ];

        const metas = [
          { strategyType: 'Scalping', orderType: 'Market', strength: 72, strengthLabel: 'Mạnh', reason: 'Funding=0.0003, Vol5m=x1.12, RSI=65.4, EMA9=..., EMA21=...' },
          { strategyType: 'Scalping', orderType: 'Limit',  strength: 68, strengthLabel: 'Tiêu chuẩn — biên dưới', reason: 'Funding=0.0001, Vol5m=x0.92, RSI=54.1, EMA9=..., EMA21=...' },
          { strategyType: 'Scalping', orderType: 'Market', strength: 75, strengthLabel: 'Mạnh', reason: 'Funding=0.0005, Vol5m=x1.35, RSI=61.0, EMA9=..., EMA21=...' },
          { strategyType: 'Swing',    orderType: 'Limit',  strength: 70, strengthLabel: 'Mạnh', reason: 'Funding=0.0002, Vol5m=x1.05, RSI=57.3, EMA9=..., EMA21=...' },
          { strategyType: 'Swing',    orderType: 'Market', strength: 66, strengthLabel: 'Tiêu chuẩn — biên dưới', reason: 'Funding=-0.0001, Vol5m=x0.88, RSI=49.9, EMA9=..., EMA21=...' }
        ];

        for (let i = 0; i < 5; i++) {
          const s = examples[i], m = metas[i];
          const msg = signalMessage({
            symbol: s.symbol, side: s.side,
            strategyType: m.strategyType, orderType: m.orderType,
            entry: s.entry, tp: s.tp, sl: s.sl,
            strength: m.strength, strengthLabel: m.strengthLabel,
            reason: m.reason, currency
          });
          await sendMessage(CHAT_ID, msg);
          await new Promise(r => setTimeout(r, 300));
        }
      }
    } finally {
      isBatchRunning = false;
    }
  }, { timezone: TZ });

  // 22:00 — Tổng kết
  cron.schedule('0 22 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '🌙 Tổng kết hôm nay\n• TP: x | SL: y | Thoát: z\n• BUY: a — SELL: b\nNgủ ngon nha!');
  }, { timezone: TZ });
}
