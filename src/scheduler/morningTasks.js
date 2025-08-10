// src/scheduler/morningTasks.js
import cron from 'node-cron';
import { sendToOwner } from '../telegram/bot.js';

const TZ = process.env.TZ || 'Asia/Ho_Chi_Minh';

export function startMorningTasks() {
  // 06:00 — Chào buổi sáng
  cron.schedule('0 6 * * *', async () => {
    await sendToOwner(
      'Chào buổi sáng nhé bạn ☀️\n• Top 5 tăng: (đang cập nhật)\n• Funding/Volume/Xu hướng: …\n• Xu hướng hôm nay: <b>TĂNG/GIẢM/TRUNG LẬP</b>\n(1 USD ≈ X <b>VND</b> • 06:00)'
    );
  }, { timezone: TZ });

  // 07:00 — Lịch vĩ mô
  cron.schedule('0 7 * * *', async () => {
    await sendToOwner('📅 07:00 Lịch vĩ mô (đang cập nhật).');
  }, { timezone: TZ });
}
