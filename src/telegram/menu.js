// src/telegram/menu.js
import { sendMessage } from './bot.js';
import { getConfig } from '../storage/configRepo.js';

function mark(active, name) {
  return active === name ? `✅ ${name}` : name;
}

export async function buildMainMenu() {
  const cfg = await getConfig();
  const ex = (cfg.active_exchange || 'ONUS').toUpperCase();

  const rows = [];
  // hàng chọn sàn
  rows.push([
    { text: mark(ex, 'ONUS'), callback_data: 'EX:ONUS' },
    { text: mark(ex, 'MEXC'), callback_data: 'EX:MEXC' },
    { text: mark(ex, 'NAMI'), callback_data: 'EX:NAMI' }
  ]);
  // lịch vĩ mô
  rows.push([
    { text: '📅 Lịch hôm nay', callback_data: 'CAL:today' },
    { text: '📅 Ngày mai',     callback_data: 'CAL:tomorrow' },
    { text: '📅 Cả tuần',      callback_data: 'CAL:week' }
  ]);
  // trạng thái + test
  rows.push([{ text: '🔎 Trạng thái bot',    callback_data: 'STATUS:show' }]);
  rows.push([{ text: '🧪 Test toàn bộ (NOW)', callback_data: 'TEST:all' }]);

  return { inline_keyboard: rows };
}

export async function handleMenuAction(cb) {
  const chatId = cb.message.chat.id;
  const data = cb.data || '';

  if (data.startsWith('EX:')) {
    const ex = data.split(':')[1];
    const { switchExchange } = await import('../actions/switchExchange.js');
    await switchExchange(ex);
    const menu = await buildMainMenu();
    await sendMessage(chatId, `Đã chuyển sang <b>${ex}</b>. Tất cả tín hiệu sẽ theo sàn này.`, { reply_markup: menu });
    return;
  }

  if (data.startsWith('CAL:')) {
    // Batch vĩ mô 07:00 sẽ gửi tự động; nút này để xem nhanh placeholder
    const kind = data.split(':')[1];
    const text =
      kind === 'today'    ? '📅 Tin vĩ mô hôm nay (sẽ lấy từ ForexFactory, lọc High Impact)':
      kind === 'tomorrow' ? '📅 Tin vĩ mô ngày mai (sẽ lấy từ ForexFactory)':
                            '📅 Lịch cả tuần (sẽ lấy từ ForexFactory)';
    return sendMessage(chatId, text);
  }

  if (data === 'STATUS:show') {
    const cfg = await getConfig();
    const ex = (cfg.active_exchange || 'ONUS').toUpperCase();
    const msg = [
      '<b>Trạng thái bot</b>',
      `• Sàn đang dùng: <b>${ex}</b> (không lấy chéo sàn)`,
      '• Khung giờ: 06:15–21:45 (30p), 06:00 chào sáng, 07:00 lịch vĩ mô, 22:00 tổng kết',
      '• Tín hiệu: ưu tiên 5/5; thiếu thì ≥3/5'
    ].join('\n');
    return sendMessage(chatId, msg);
  }

  if (data === 'TEST:all') {
    const { runTestNow } = await import('../actions/testNow.js');
    await sendMessage(chatId, '🔧 Đang chạy 1 batch thử ngay bây giờ…');
    await runTestNow();
    return;
  }

  return sendMessage(chatId, 'Không hiểu thao tác. Hãy mở /menu lại nhé.');
}
