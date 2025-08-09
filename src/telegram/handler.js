import { sendMessage, answerCallbackQuery } from './bot.js';
import { buildMainMenu, handleMenuAction } from './menu.js';
import { isOwner } from '../utils/time.js';

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
        '• Nguồn dữ liệu: Onus (Batch 3 sẽ bật dữ liệu thật)'
      ].join('\n');
      return sendMessage(chatId, status);
    }

    if (text === '/test_all') {
      return sendMessage(chatId, '[TEST] Scheduler đang chạy (mock). Batch 3 sẽ ghép dữ liệu Onus thật.');
    }

    return sendMessage(chatId, 'Gõ /menu để mở điều khiển hoặc /status để xem tình trạng.');
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
