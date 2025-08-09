// src/scheduler/index.js
import cron from 'node-cron';
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { pickSignals } from '../signals/generator.js';
import {
  startOnusPoller,
  getOnusSnapshotCached,
  getOnusLastGood,
  getOnusMeta
} from '../sources/onus/cache.js';
import { logSourceError } from '../storage/errorRepo.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const TZ = process.env.TZ || 'Asia/Ho_Chi_Minh';

let isBatchRunning = false;
let lastAlertAt = 0;

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
  // Khởi động poll ONUS (sàn đã có dữ liệu thật)
  startOnusPoller({ intervalMs: 20000 });

  // 06:00 — chào sáng
  cron.schedule('0 6 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(
      CHAT_ID,
      'Chào buổi sáng nhé bạn ☀️\n• Top 5 tăng: (sẽ gắn dữ liệu sàn)\n• Funding/Volume/Xu hướng: ...\n• Xu hướng hôm nay: <b>TĂNG/GIẢM/TRUNG LẬP</b>  🟩 Tăng X%  |  🟥 Giảm Y% (theo sàn, khung 4h)\n(1 USD ≈ X <b>VND</b> • 06:00)'
    );
  }, { timezone: TZ });

  // 07:00 — lịch vĩ mô
  cron.schedule('0 7 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '📅 07:00 Lịch vĩ mô (sẽ lấy từ ForexFactory, lọc high impact).');
  }, { timezone: TZ });

  // 06:15 → 21:45 — mỗi 30'
  cron.schedule('15,45 6-21 * * *', async () => {
    if (!CHAT_ID) return;
    if (isBatchRunning) return;
    isBatchRunning = true;

    try {
      const cfg = await getConfig();
      const ex = (cfg.active_exchange || 'ONUS').toUpperCase(); // ONUS/MEXC/NAMI
      const nextTime = nextSlotString();
      await sendMessage(CHAT_ID, batchHeader(nextTime, ex));

      if (ex === 'ONUS') {
        let staleNote = '';
        try {
          const metaBefore = getOnusMeta();
          const freshRows = await getOnusSnapshotCached({ maxAgeSec: 120, quickRetries: 3 });
          const metaAfter = getOnusMeta();
          if (metaAfter.ageSec && metaAfter.ageSec > 120) {
            staleNote = `\n(ℹ️ Dùng snapshot ONUS cũ ~${metaAfter.ageSec}s)`;
          } else if (metaBefore.fetchedAt && metaAfter.fetchedAt === metaBefore.fetchedAt && metaAfter.ageSec > 120) {
            staleNote = `\n(ℹ️ Dùng snapshot ONUS cũ ~${metaAfter.ageSec}s)`;
          }

          // ƯU TIÊN đủ 5 kèo
          let signals = pickSignals(freshRows, 5, 'VND');

          // BƯỚC BÙ từ last-good (≤60’) – vẫn là ONUS, không lấy chéo
          if (signals.length < 5) {
            const last = getOnusLastGood();
            if (last && (Date.now() - last.fetchedAt) / 1000 <= 3600) {
              const used = new Set(signals.map(s => s.symbol));
              const extraRows = (last.rows || []).filter(r => !used.has(r.symbol));
              if (extraRows.length) {
                const extra = pickSignals(extraRows, 5 - signals.length, 'VND');
                for (const e of extra) e.reason = (e.reason ? e.reason + ' ' : '') + '• nguồn: snapshot cũ';
                signals = signals.concat(extra);
              }
            }
          }

          // Nếu vẫn không đủ 5 nhưng có ≥3 → vẫn gửi
          if (signals.length >= 3) {
            for (const s of signals) {
              await sendMessage(CHAT_ID, signalMessage(s));
              await new Promise(r => setTimeout(r, 200));
            }
            if (staleNote) await sendMessage(CHAT_ID, staleNote);
            return;
          }

          // <3 kèo → cảnh báo & bỏ batch (an toàn)
          throw new Error(`Không đủ tín hiệu (có ${signals.length}/5, yêu cầu tối thiểu 3)`);
        } catch (err) {
          const msg = String(err?.message || err);
          await logSourceError('ONUS', msg);

          const now = Date.now();
          if (now - lastAlertAt > 10 * 60 * 1000) {
            lastAlertAt = now;
            await sendMessage(
              CHAT_ID,
              `⚠️ ONUS không đủ dữ liệu để tạo 3 tín hiệu tối thiểu (${msg}).\nGõ /source để kiểm tra tuổi dữ liệu.`
            );
          }
          return;
        }
      }

      // Các sàn khác (MEXC/NAMI) — KHÔNG lấy chéo. Nếu chưa cấu hình dữ liệu thật, báo rõ & bỏ batch.
      if (ex === 'MEXC' || ex === 'NAMI') {
        await sendMessage(
          CHAT_ID,
          `⚠️ Sàn ${ex} chưa được cấu hình nguồn dữ liệu thật. Bỏ batch để tránh sai giá.`
        );
        return;
      }
    } finally {
      isBatchRunning = false;
    }
  }, { timezone: TZ });

  // 22:00 — tổng kết
  cron.schedule('0 22 * * *', async () => {
    if (!CHAT_ID) return;
    await sendMessage(CHAT_ID, '🌙 Tổng kết hôm nay\n• TP: x | SL: y | Thoát: z\n• BUY: a — SELL: b\nNgủ ngon nha!');
  }, { timezone: TZ });
}
