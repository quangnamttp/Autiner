// src/telegram/format.js
import { fmtVN } from '../utils/time.js';
import { formatUSD, formatVND } from '../utils/number.js';

// Escape an toàn cho HTML (phòng trường hợp lý do/chuỗi có ký tự đặc biệt)
function escapeHtml(s = '') {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function batchHeader(nextTimeHHmm, exchange) {
  return `📢 Tín hiệu 30p tiếp theo (<b>${escapeHtml(nextTimeHHmm)}</b>) — theo sàn <b>${escapeHtml(exchange)}</b>`;
}

/**
 * Tạo nội dung 1 tín hiệu (HTML mode)
 * @param {{
 *  symbol:string, side:'LONG'|'SHORT',
 *  strategyType:string, orderType:string,
 *  entry:number, tp:number, sl:number,
 *  strength:number, strengthLabel:string,
 *  reason:string, currency:'VND'|'USD'
 * }} p
 */
export function signalMessage(p) {
  const sideIcon = p.side === 'LONG' ? '🟩' : '🟥';
  const fmt = p.currency === 'VND'
    ? (n) => `${formatVND(n)} <b>VND</b>`   // VND: không thập phân
    : (n) => `${formatUSD(n)} <b>USD</b>`;  // USD: giữ thập phân

  const lines = [
    `📈 <b>${escapeHtml(p.symbol)}</b> — ${sideIcon} <b>${escapeHtml(p.side)}</b>`,
    ``,
    `🟢 Loại lệnh: <b>${escapeHtml(p.strategyType)}</b>`,
    `🔹 Kiểu vào lệnh: <b>${escapeHtml(p.orderType)}</b>`,
    `💰 Entry: ${fmt(p.entry)}`,
    `🎯 TP: ${fmt(p.tp)}`,
    `🛡️ SL: ${fmt(p.sl)}`,
    `📊 Độ mạnh: <b>${Number(p.strength) || 0}%</b> (${escapeHtml(p.strengthLabel)})`,
    `📌 Lý do: ${escapeHtml(p.reason)}`,
    `🕒 Thời gian: ${fmtVN()}`
  ];

  return lines.join('\n');
}
