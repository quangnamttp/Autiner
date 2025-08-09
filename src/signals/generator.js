// src/signals/generator.js
// Chấm điểm đơn giản nhưng an toàn: funding | vol5m | change
// Trả 5 kèo: 3 Scalping + 2 Swing, Entry/TP/SL dựa quanh giá hiện tại.

function scoreRow(r){
  const f = Math.abs(Number(r.funding)||0);       // funding lệch càng lớn càng tốt
  const v = Number(r.vol5m)||0;                   // volume 5m
  const c = Number(r.change)||0;                  // %24h (định hướng)
  // chuẩn hóa thô (tùy biến sau)
  const s = (f*1000) + (Math.log10(v+1)*10) + (Math.abs(c)*0.5);
  return s;
}

function decideSide(change){
  // change dương → ưu tiên LONG; âm → SHORT
  if ((Number(change)||0) >= 0) return 'LONG';
  return 'SHORT';
}

function makeLevelsVND(price, side, mode){
  const p = Math.round(price);
  // biên độ an toàn tùy theo mode
  const step = mode==='Scalping' ? 0.006 : 0.012; // 0.6% | 1.2%
  const tpK  = mode==='Scalping' ? 0.004 : 0.008; // 0.4% | 0.8%
  const slK  = mode==='Scalping' ? 0.006 : 0.012; // 0.6% | 1.2%

  const entry = p;
  const tp  = Math.round(side==='LONG' ? p*(1+tpK) : p*(1-tpK));
  const sl  = Math.round(side==='LONG' ? p*(1-slK) : p*(1+slK));
  const orderType = 'Market';

  return { entry, tp, sl, orderType };
}

export function pickTop5SignalsFromOnus(snapshot){
  // chấm điểm & sort
  const scored = snapshot
    .map(r => ({...r, _score: scoreRow(r)}))
    .sort((a,b)=> b._score - a._score);

  // lấy 3 scalping + 2 swing, tránh trùng symbol
  const out = [];
  const used = new Set();

  function pushByMode(mode){
    for (const r of scored){
      if (used.has(r.symbol)) continue;
      const side = decideSide(r.change);
      const levels = makeLevelsVND(r.last, side, mode);
      const strength = Math.min(95, Math.round(r._score)); // 0..95
      const strengthLabel = strength >= 70 ? 'Mạnh' : (strength >= 50 ? 'Tiêu chuẩn' : 'Tham khảo');
      const reason = `Funding=${Number(r.funding)||0}, Vol5m=${Number(r.vol5m)||0}, %24h=${Number(r.change)||0}`;
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
        currency: 'VND'
      });
      used.add(r.symbol);
      break;
    }
  }

  // 3 Scalping
  pushByMode('Scalping'); pushByMode('Scalping'); pushByMode('Scalping');
  // 2 Swing
  pushByMode('Swing');    pushByMode('Swing');

  // nếu thiếu (dữ liệu ít), trả bấy nhiêu
  return out.slice(0, 5);
}
