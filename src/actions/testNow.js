// src/actions/testNow.js
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { pickSignals } from '../signals/generator.js';
import {
  getOnusSnapshotCached,
  getOnusLastGood,
  getOnusMeta
} from '../sources/onus/cache.js';
import { logSourceError } from '../storage/errorRepo.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export async function runTestNow() {
  if (!CHAT_ID) return;

  const cfg = await getConfig();
  const ex = (cfg.active_exchange || 'ONUS').toUpperCase();

  // Tiêu đề batch
  await sendMessage(CHAT_ID, batchHeader('NOW', ex));

  // Chỉ chạy thật cho ONUS (đúng yêu cầu “đúng sàn – không chéo”)
  if (ex !== 'ONUS') {
    await sendMessage(CHAT_ID, `⚠️ Sàn ${ex} chưa được cấu hình nguồn dữ liệu thật. Bỏ batch để tránh sai giá.`);
    return;
  }

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

    // Ưu tiên đủ 5 kèo
    let signals = pickSignals(freshRows, 5, 'VND');

    // Bù từ last-good (≤60’) nếu thiếu – vẫn là ONUS
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

    // Nếu đủ 5 thì gửi 5; nếu không đủ thì tối thiểu 3
    if (signals.length >= 3) {
      for (const s of signals) {
        await sendMessage(CHAT_ID, signalMessage(s));
        await sleep(200);
      }
      if (staleNote) await sendMessage(CHAT_ID, staleNote);
      return;
    }

    throw new Error(`Không đủ tín hiệu (có ${signals.length}/5, yêu cầu tối thiểu 3)`);
  } catch (err) {
    const msg = String(err?.message || err);
    await logSourceError('ONUS', msg);
    await sendMessage(CHAT_ID, `⚠️ ONUS không đủ dữ liệu để tạo 3 tín hiệu tối thiểu (${msg}).`);
  }
}
