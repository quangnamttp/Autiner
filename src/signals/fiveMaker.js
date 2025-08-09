// src/signals/fiveMaker.js
// Bảo đảm luôn tạo đủ 5 tín hiệu từ dữ liệu ONUS (không báo lỗi, không chéo sàn)

import { getOnusSnapshotCached } from '../sources/onus/cache.js';
import { getOnusRowsFromHistory } from '../storage/onusRepo.js';
import { pickSignals } from './generator.js';

/**
 * Tạo đúng 5 tín hiệu ONUS:
 * 1) Dùng snapshot mới nhất (cache/quick-retry)
 * 2) Nếu <5, bổ sung từ kho DB (6h gần nhất) cho đủ 5 (vẫn dữ liệu ONUS)
 * 3) Nếu vẫn <5 (rất hiếm), cố chọn lặp theo symbol khác trong kho để đủ 5
 */
export async function makeFiveOnusSignals() {
  // 1) snapshot tươi
  const fresh = await getOnusSnapshotCached({ maxAgeSec: 120, quickRetries: 3 });
  let signals = pickSignals(fresh, 5, 'VND');

  if (signals.length >= 5) return signals;

  // 2) bổ sung từ kho DB (6 giờ)
  const poolRows = await getOnusRowsFromHistory(360);
  if (poolRows.length) {
    const used = new Set(signals.map(s => s.symbol));
    const candidates = poolRows.filter(r => !used.has(r.symbol));
    if (candidates.length) {
      const extra = pickSignals(candidates, 5 - signals.length, 'VND');
      signals = signals.concat(extra);
    }
  }

  // 3) nếu vẫn thiếu, thử nới tiếp từ pool (cho phép trùng mode/symbol khác)
  if (signals.length < 5 && poolRows.length) {
    const extra = pickSignals(poolRows, 5 - signals.length, 'VND');
    // lọc trùng symbol nếu có
    const final = [];
    const seen = new Set();
    for (const s of [...signals, ...extra]) {
      if (seen.has(s.symbol)) continue;
      seen.add(s.symbol);
      final.push(s);
      if (final.length === 5) break;
    }
    signals = final;
  }

  // nếu vẫn ít hơn 5: trả về những gì có (khả năng cực thấp khi mới khởi động)
  return signals.slice(0, 5);
}
