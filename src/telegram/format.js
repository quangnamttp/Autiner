import { fmtVN } from '../utils/time.js';
import { formatUSD, formatVND } from '../utils/number.js';

export function batchHeader(nextTimeHHmm, exchange) {
  return `📢 Tín hiệu 30p tiếp theo (${nextTimeHHmm}) — theo sàn ${exchange}`;
}

export function signalMessage({ symbol, side, strategyType, orderType, entry, tp, sl, strength, strengthLabel, reason, currency }) {
  const sideIcon = side === 'LONG' ? '🟩' : '🟥';
  const fmt = currency === 'VND' ? (n) => `${formatVND(n)} **VND**` : (n) => `${formatUSD(n)} **USD**`;
  return [
    `📈 ${symbol} — ${sideIcon} ${side}`,
    '',
    `🟢 Loại lệnh: ${strategyType}`,
    `🔹 Kiểu vào lệnh: ${orderType}`,
    `💰 Entry: ${fmt(entry)}`,
    `🎯 TP: ${fmt(tp)}`,
    `🛡️ SL: ${fmt(sl)}`,
    `📊 Độ mạnh: ${strength}% (${strengthLabel})`,
    `📌 Lý do: ${reason}`,
    `🕒 Thời gian: ${fmtVN()}`
  ].join('\n');
}
