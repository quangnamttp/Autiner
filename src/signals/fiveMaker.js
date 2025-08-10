// src/signals/fiveMaker.js
// Lấy LIVE từ ONUS và gửi NGAY 5 lệnh. Không dùng cache/DB.

import { getOnusSnapshot } from '../sources/onus/scrape.js';
import { pickSignals } from './generator.js';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function mergeUniqueBySymbol(buckets) {
  const map = new Map();
  for (const arr of buckets) {
    for (const r of arr) {
      const sym = String(r.symbol || '').trim();
      if (!sym) continue;
      if (!map.has(sym)) map.set(sym, r);
    }
  }
  return Array.from(map.values());
}

/**
 * Quét ONUS nhiều vòng LIỀN TAY (live), gộp dữ liệu, chọn đúng 5 kèo.
 * - Thử tối đa 12 vòng (~60s): mỗi vòng scrape 1 lần.
 * - Mỗi vòng gộp thêm symbol mới vào tập dữ liệu.
 * - Khi đủ 5 → chọn & trả ngay, không chờ hết vòng.
 * - Chỉ dùng dữ liệu ONUS (live), không bù từ nơi khác.
 */
export async function makeFiveOnusSignalsLive() {
  const buckets = [];
  for (let i = 0; i < 12; i++) {
    try {
      const rows = await getOnusSnapshot(); // đã có retry/cross-check trong scrape.js
      if (Array.isArray(rows) && rows.length) {
        buckets.push(rows);
        const merged = mergeUniqueBySymbol(buckets);
        const sigs = pickSignals(merged, 5, 'VND');
        if (sigs.length >= 5) return sigs.slice(0, 5);
      }
    } catch (_) {
      // bỏ qua vòng lỗi, thử tiếp
    }
    await sleep(5000); // đợi 5s rồi quét tiếp
  }

  // Nếu vẫn chưa đủ (rất khó xảy ra với ONUS): chọn tốt nhất có thể (>=1)
  const merged = mergeUniqueBySymbol(buckets);
  const sigs = pickSignals(merged, 5, 'VND');
  return sigs.slice(0, 5); // có bao nhiêu trả bấy nhiêu (theo merged)
}

/** Top 5 tăng (chào sáng) — lấy ngay từ lần scrape hiện tại */
export async function getOnusTop5GainersInstant() {
  try {
    const rows = await getOnusSnapshot();
    if (!Array.isArray(rows) || !rows.length) return [];
    return [...rows]
      .filter(r => Number.isFinite(Number(r.change)))
      .sort((a, b) => Number(b.change) - Number(a.change))
      .slice(0, 5)
      .map(r => r.symbol);
  } catch {
    return [];
  }
}
