import { getConfig, setActiveExchange } from '../storage/configRepo.js';
import { sendMessage } from './bot.js';

const EXCHANGES = ['ONUS', 'MEXC', 'NAMI'];

export async function buildMainMenu() {
  const cfg = await getConfig();

  const rows = [];

  // Hàng chọn sàn
  const exButtons = EXCHANGES.map(ex => ({
    text: ex === cfg.active_exchange ? `✅ ${ex}` : ex,
    callback_data: `EXCHANGE:${ex}`
  }));
  rows.push(exButtons);

  // Lịch vĩ mô (placeholder – Batch 3 sẽ đổ dữ liệu)
  rows.push([
    { text: '📅 Lịch hôm nay', callback_data: 'CAL:today' },
    { text: '📅 Ngày mai', callback_data: 'CAL:tomorrow' },
    { text: '📅 Cả tuần', callback_data: 'CAL:week' }
  ]);

  // Trạng thái nhanh
  rows.push([
    { text: '🔎 Trạng thái bot', callback_data: 'STATUS:show' }
  ]);

  // Test all (placeholder)
  rows.push([
    { text: '🧪 Test toàn bộ', callback_data: 'TEST:all' }
  ]);

  return { inline_keyboard: rows };
}

export async function handleMenuAction(cb) {
  const chatId = cb.message.chat.id;
  const data = cb.data || '';

  if (data.startsWith('EXCHANGE:')) {
    const ex = data.split(':')[1];
    if (!EXCHANGES.includes(ex)) {
      return sendMessage(chatId, 'Sàn không hợp lệ.');
    }
    await setActiveExchange(ex);
    const menu = await buildMainMenu();
    return sendMessage(chatId, `Đã chuyển sang *${ex}*\\. Tất cả tín hiệu sẽ theo sàn này\\.`, { reply_markup: menu });
  }

  if (data === 'CAL:today' || data === 'CAL:tomorrow' || data === 'CAL:week') {
    return sendMessage(chatId, '📅 Lịch vĩ mô sẽ được bật ở *Batch 3* — mình sẽ lấy từ ForexFactory, lọc high impact và dịch chuẩn VN\\.');
  }

  if (data === 'STATUS:show') {
    const cfg = await getConfig();
    const text = [
      '*Trạng thái bot*',
      `• Sàn đang dùng: *${cfg.active_exchange}*`,
      '• Khung giờ: 06:15–21:45 (30p/batch), 06:00 chào sáng, 07:00 lịch vĩ mô, 22:00 tổng kết',
      '• Tần suất: 30 phút (cố định)',
      '• Nguồn dữ liệu: sẽ bật ở Batch 2/3'
    ].join('\n');
    return sendMessage(chatId, text);
  }

  if (data === 'TEST:all') {
    return sendMessage(chatId, '[TEST] Batch 1 chỉ có webhook/menu/status\\. Test đầy đủ sẽ có ở Batch 2\\.');
  }

  return sendMessage(chatId, 'Không hiểu thao tác\\. Hãy mở /menu lại nhé\\.');
}
