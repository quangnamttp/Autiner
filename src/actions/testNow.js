// src/actions/testNow.js
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { makeExactlyFiveOnusSignals } from '../signals/fiveMaker.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export async function runTestNow() {
  if (!CHAT_ID) return;

  const cfg = await getConfig();
  const ex = (cfg.active_exchange || 'ONUS').toUpperCase();

  // Chỉ gửi khi CHẮC có 5 lệnh → tránh spam tiêu đề rỗng
  if (ex === 'ONUS') {
    const sigs = await makeExactlyFiveOnusSignals();
    if (!sigs) return; // im lặng nếu chưa đủ 5
    await sendMessage(CHAT_ID, batchHeader('NOW', ex));
    for (const s of sigs) {
      await sendMessage(CHAT_ID, signalMessage(s));
      await sleep(160);
    }
    return;
  }

  // Các sàn khác chưa bật dữ liệu thật → im lặng (không lấy chéo)
}
