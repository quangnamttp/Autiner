// src/actions/testNow.js
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { pickTop5SignalsFromOnus } from '../signals/generator.js';
import { getOnusSnapshotCached } from '../sources/onus/cache.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export async function runTestNow() {
  if (!CHAT_ID) return;

  const cfg = await getConfig();
  const ex = cfg.active_exchange || 'ONUS';

  await sendMessage(CHAT_ID, batchHeader('NOW', ex));

  if (ex === 'ONUS') {
    try {
      const snap = await getOnusSnapshotCached({ maxAgeSec: 120, quickRetries: 3 });
      const sigs = pickTop5SignalsFromOnus(snap);
      if (!sigs.length) {
        await sendMessage(CHAT_ID, '⚠️ Không có tín hiệu phù hợp từ ONUS lúc này.');
        return;
      }
      for (const s of sigs) {
        await sendMessage(CHAT_ID, signalMessage(s));
        await sleep(250);
      }
      return;
    } catch (e) {
      await sendMessage(CHAT_ID, `⚠️ Onus dữ liệu không đạt chuẩn (${e.message}). Batch NOW dừng.`);
      return;
    }
  }

  // Mock cho MEXC/NAMI nếu cần
  await sendMessage(CHAT_ID, '⚠️ Chế độ mock dữ liệu cho sàn khác.');
}
