import cron from 'node-cron';
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;

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
  cron.schedule('0 6 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID,
      'Chào buổi sáng nhé bạn ☀️\n• Top 5 tăng: (Batch 3 sẽ gắn dữ liệu sàn)\n• Funding/Volume/Xu hướng: ...\n• Xu hướng hôm nay: **TĂNG/GIẢM/TRUNG LẬP**  🟩 Tăng X%  |  🟥 Giảm Y% (theo sàn, khung 4h)\n(1 USD ≈ X **VND** • 06:00)'
    );
  });

  cron.schedule('0 7 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '📅 07:00 Lịch vĩ mô (Batch 3 sẽ lấy từ ForexFactory, lọc high impact).');
  });

  cron.schedule('15,45 6-21 * * *', async () => {
    if (!CHAT_ID) return;
    const cfg = await getConfig();
    const ex = cfg.active_exchange || 'ONUS';
    const nextTime = nextSlotString();

    await sendMessage(CHAT_ID, batchHeader(nextTime, ex));

    const currency = ex === 'MEXC' ? 'USD' : 'VND';
    const examples = ex === 'MEXC'
      ? [
          { symbol: '1000CATUSDT', entry: 0.009538, tp: 0.009624, sl: 0.009481, side: 'LONG' },
          { symbol: 'BTCUSDT',     entry: 58000.5, tp: 58200.0, sl: 57700.0, side: 'LONG' },
          { symbol: 'ETHUSDT',     entry: 2500.2,  tp: 2520.0,  sl: 2488.0,  side: 'LONG' },
          { symbol: 'DOGEUSDT',    entry: 0.126,   tp: 0.128,   sl: 0.124,   side: 'SHORT' },
          { symbol: 'PEPEUSDT',    entry: 0.0000123, tp: 0.0000126, sl: 0.0000120, side: 'LONG' }
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
      await new Promise(r => setTimeout(r, 400));
    }
  });

  cron.schedule('0 22 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '🌙 Tổng kết hôm nay\n• TP: x | SL: y | Thoát: z\n• BUY: a — SELL: b\nNgủ ngon nha!');
  });
}
