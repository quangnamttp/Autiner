// src/actions/testNow.js
import { sendMessage } from '../telegram/bot.js';
import { getConfig } from '../storage/configRepo.js';
import { batchHeader, signalMessage } from '../telegram/format.js';
import { makeFiveOnusSignals } from '../signals/fiveMaker.js';

const CHAT_ID = process.env.ALLOWED_TELEGRAM_USER_ID;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export async function runTestNow() {
  if (!CHAT_ID) return;

  const cfg = await getConfig();
  const ex = (cfg.active_exchange || 'ONUS').toUpperCase();

  await sendMessage(CHAT_ID, batchHeader('NOW', ex));

  if (ex !== 'ONUS') {
    // Giữ nguyên nguyên tắc: không lấy chéo sàn, không báo lỗi — chỉ im lặng
    await sendMessage(CHAT_ID, `⚠️ Sàn ${ex} chưa cấu hình nguồn dữ liệu thật. Đang chờ bạn bật dữ liệu sàn này.`);
    return;
  }

  const sigs = await makeFiveOnusSignals();
  // luôn cố gắng đủ 5; nếu <5 (lần khởi động đầu tiên) vẫn gửi những gì có, không báo lỗi
  for (const s of sigs) {
    await sendMessage(CHAT_ID, signalMessage(s));
    await sleep(180);
  }
}
