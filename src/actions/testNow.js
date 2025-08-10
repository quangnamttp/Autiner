// src/actions/testNow.js
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { makeFiveOnusSignalsLive } from '../signals/fiveMaker.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export async function runTestNow() {
  if (!CHAT_ID) return;

  const cfg = await getConfig();
  const ex = (cfg.active_exchange || 'ONUS').toUpperCase();
  if (ex !== 'ONUS') return; // chỉ ONUS

  // Quét live nhiều vòng → đủ 5 là gửi ngay
  const sigs = await makeFiveOnusSignalsLive();
  if (!sigs.length) return; // trường hợp cực hiếm: không gửi

  await sendMessage(CHAT_ID, batchHeader('NOW', ex));
  for (const s of sigs) {
    await sendMessage(CHAT_ID, signalMessage(s));
    await sleep(140);
  }
}
