// src/signals/generator.js
// Bộ chấm điểm & chọn kèo chung cho 1 snapshot của 1 sàn
// LƯU Ý: Không đụng tới nguồn dữ liệu — file này chỉ chọn/tính Entry/TP/SL.

function scoreRow(r) {
  // Cho điểm: funding | vol5m | biên độ 24h
  const f = Math.abs(Number(r.funding) || 0);
  const v = Number(r.vol5m) || 0;
  const c = Number(r.change) || 0;
  return (f * 1000) + (Math.log10(v + 1) * 10) + (Math.abs(c) * 0.5);
}

function decideSide(change) {
  // change dương → ưu tiên LONG; âm → SHORT
  return (Number(change) || 0) >= 0 ? 'LONG' : 'SHORT';
}

function makeLevelsVND(price, side, mode) {
  const p = Math.round(price);
  const tpK = mode === 'Scalping' ? 0.004 : 0.008;
  const slK = mode === 'Scalping' ? 0.006 : 0.012;
  const entry = p;
  const tp = Math.round(side === 'LONG' ? p * (1 + tpK) : p * (1 - tpK));
  const sl = Math.round(side === 'LONG' ? p * (1 - slK) : p * (1 + slK));
  return { entry, tp, sl, orderType: 'Market' };
}

/**
 * Chọn N kèo từ 1 snapshot cùng sàn.
 * @param {Array} snapshot - [{symbol,last,change,funding,vol5m}]
 * @param {number} desired - số kèo mong muốn (mặc định 5)
 * @param {'VND'|'USD'} currency
 * @returns {Array} signals
 */
export function pickSignals(snapshot, desired = 5, currency = 'VND') {
  if (!Array.isArray(snapshot) || snapshot.length === 0) return [];

  const scored = snapshot
    .map(r => ({ ...r, _score: scoreRow(r) }))
    .sort((a, b) => b._score - a._score);

  const out = [];
  const used = new Set();

  function pushByMode(mode) {
    for (const r of scored) {
      if (used.has(r.symbol)) continue;
      const side = decideSide(r.change);
      const levels = currency === 'VND'
        ? makeLevelsVND(r.last, side, mode)
        : makeLevelsVND(r.last, side, mode); // nếu sau này có USD thì đổi hàm tính riêng
      const strength = Math.min(95, Math.round(r._score));
      const strengthLabel = strength >= 70 ? 'Mạnh' : (strength >= 50 ? 'Tiêu chuẩn' : 'Tham khảo');
      const reason = `Funding=${Number(r.funding) || 0}, Vol5m=${Number(r.vol5m) || 0}, %24h=${Number(r.change) || 0}`;
      out.push({
        symbol: r.symbol,
        side,
        strategyType: mode,
        orderType: levels.orderType,
        entry: levels.entry,
        tp: levels.tp,
        sl: levels.sl,
        strength,
        strengthLabel,
        reason,
        currency
      });
      used.add(r.symbol);
      break;
    }
  }

  // Ưu tiên cơ cấu 3 Scalping + 2 Swing nếu đủ
  const need = Math.max(1, Math.min(10, desired));
  if (need >= 1) pushByMode('Scalping');
  if (need >= 2) pushByMode('Scalping');
  if (need >= 3) pushByMode('Scalping');
  if (need >= 4) pushByMode('Swing');
  if (need >= 5) pushByMode('Swing');

  // Nếu vẫn thiếu do dữ liệu ít, tiếp tục nhặt theo bất kỳ mode
  while (out.length < need) {
    // xen kẽ mode để đa dạng
    pushByMode(out.length % 2 === 0 ? 'Scalping' : 'Swing');
    if (used.size === scored.length) break;
  }

  return out.slice(0, need);
}
