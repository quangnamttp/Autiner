import { sendMessage, answerCallbackQuery } from './bot.js';
import { buildMainMenu, handleMenuAction } from './menu.js';
import { isOwner, fmtVN } from '../utils/time.js';
import { getConfig } from '../storage/configRepo.js';
import { getOnusMeta } from '../sources/onus/cache.js';

export async function handleMessageOrCallback(update) {
  if (update.message) {
    const m = update.message;
    const chatId = m.chat.id;
    if (!isOwner(chatId)) return sendMessage(chatId, 'Xin lỗi, bot dùng riêng.');

    const text = (m.text || '').trim();

    if (text === '/start' || text === '/menu') {
      const menu = await buildMainMenu();
      return sendMessage(chatId, 'autiner sẵn sàng. Chọn thao tác bên dưới.', { reply_markup: menu });
    }

    if (text === '/status') {
      const status = [
        '<b>Trạng thái bot</b>',
        '• Khung giờ: 06:15–21:45 (30p); 06:00; 07:00; 22:00',
        '• Tần suất: 30 phút',
        '• Nguồn dữ liệu: ONUS (scrape + cache)'
      ].join('\n');
      return sendMessage(chatId, status);
    }

    if (text === '/source') {
      const cfg = await getConfig();
      const ex = cfg.active_exchange || 'ONUS';

      if (ex === 'ONUS') {
        const meta = getOnusMeta();
        const timeStr = meta.fetchedAt ? fmtVN(new Date(meta.fetchedAt)) : 'chưa có';
        const age = meta.ageSec != null ? `${meta.ageSec}s` : 'N/A';
        const lines = [
          '📡 <b>Nguồn dữ liệu hiện tại</b>',
          `• Sàn đang chọn: <b>${ex}</b>`,
          `• Lần lấy gần nhất: <b>${timeStr}</b>`,
          `• Tuổi dữ liệu: <b>${age}</b>`,
          `• Có dữ liệu: <b>${meta.hasData ? 'Có' : 'Không'}</b>`
        ];
        return sendMessage(chatId, lines.join('\n'));
      }

      // MEXC/NAMI (chưa bật nguồn thật)
      const lines = [
        '📡 <b>Nguồn dữ liệu hiện tại</b>',
        `• Sàn đang chọn: <b>${ex}</b>`,
        '• Trạng thái: <i>đang ở chế độ mock dữ liệu</i>'
      ];
      return sendMessage(chatId, lines.join('\n'));
    }

    if (text === '/test_all') {
      const { runTestNow } = await import('../actions/testNow.js');
      await sendMessage(chatId, '🔧 Đang chạy 1 batch thử ngay bây giờ…');
      await runTestNow();
      return;
    }

    return sendMessage(chatId, 'Gõ /menu để mở điều khiển, hoặc /status, /source để xem tình trạng.');
  }

  if (update.callback_query) {
    const cb = update.callback_query;
    const chatId = cb.message.chat.id;
    if (!isOwner(chatId)) {
      await answerCallbackQuery(cb.id);
      return sendMessage(chatId, 'Xin lỗi, bot dùng riêng.');
    }
    await handleMenuAction(cb);
    await answerCallbackQuery(cb.id);
  }
}
