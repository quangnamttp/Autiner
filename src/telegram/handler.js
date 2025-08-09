import { sendMessage, answerCallbackQuery } from './bot.js';
import { buildMainMenu, handleMenuAction } from './menu.js';
import { isOwner } from '../utils/time.js';

export async function handleMessageOrCallback(update) {
  if (update.message) {
    const m = update.message;
    const chatId = m.chat.id;

    if (!isOwner(chatId)) {
      return sendMessage(chatId, 'Xin lỗi, bot dùng riêng.');
    }

    const text = (m.text || '').trim();

    if (text === '/start') {
      const menu = await buildMainMenu();
      return sendMessage(chatId, 'autiner đã sẵn sàng\\. Chọn thao tác bên dưới\\.', { reply_markup: menu });
    }

    if (text === '/menu') {
      const menu = await buildMainMenu();
      return sendMessage(chatId, 'Menu điều khiển', { reply_markup: menu });
    }

    if (text === '/status') {
      // Batch 1: trạng thái cơ bản
      const status = [
        '*Trạng thái bot*',
        '• Sàn đang dùng: sẽ hiển thị trong menu',
        '• Khung giờ: 06:15–21:45; 06:00; 07:00; 22:00',
        '• Tần suất: 30 phút',
        '• Nguồn dữ liệu: sẽ thêm ở Batch 2/3'
      ].join('\n');
      return sendMessage(chatId, status);
    }

    if (text === '/test_all') {
      return sendMessage(chatId, '[TEST] Batch 1 đang chỉ có menu/webhook\\. Các test khác sẽ có ở Batch 2\\.');
    }

    return sendMessage(chatId, 'Gõ /menu để mở điều khiển hoặc /status để xem tình trạng\\.');
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
