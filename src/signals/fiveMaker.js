// src/signals/fiveMaker.js
// Tạo ĐÚNG 5 tín hiệu ONUS. Nếu không đủ 5 → trả null (để batch/test không gửi gì).

import { getOnusSnapshotCached } from '../sources/onus/cache.js';
import { getOnusRowsFromHistory, saveOnusSnapshot } from '../storage/onusRepo.js';
import { getOnusSnapshot } from '../sources/onus/scrape.js';
import { pickSignals } from './generator.js';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function warmUp(times = 2) {
  for (let i = 0; i < times; i++) {
    try {
      const rows = await getOnusSnapshot();          // axios → fallback puppeteer
      await saveOnusSnapshot(rows, Date.now());
    } catch (_) {}
    await sleep(400);
  }
}

// luôn trả mảng dài đúng 5; nếu không thể → trả null
export async function makeExactlyFiveOnusSignals() {
  // vòng cố gắng tối đa ~90s
  for (let round = 0; round < 6; round++) {
    // 1) chộp snapshot tươi
    let fresh = await getOnusSnapshotCached({ maxAgeSec: 120, quickRetries: 3 });
    let sigs = pickSignals(fresh, 5, 'VND');

    // 2) nếu thiếu → dùng kho 6h/24h để bù cho đủ 5 (vẫn dữ liệu ONUS)
    if (sigs.length < 5) {
      const used = new Set(sigs.map(s => s.symbol));
      const pool6h = await getOnusRowsFromHistory(360);
      const extra6 = pickSignals(pool6h.filter(r => !used.has(r.symbol)), 5 - sigs.length, 'VND');
      sigs = sigs.concat(extra6);
    }
    if (sigs.length < 5) {
      const used = new Set(sigs.map(s => s.symbol));
      const pool24h = await getOnusRowsFromHistory(1440);
      const extra24 = pickSignals(pool24h.filter(r => !used.has(r.symbol)), 5 - sigs.length, 'VND');
      sigs = sigs.concat(extra24);
    }

    if (sigs.length >= 5) return sigs.slice(0, 5);

    // 3) nếu vẫn thiếu → ép lấy thêm dữ liệu rồi lặp lại
    await warmUp(round < 2 ? 2 : 1);
  }
  return null; // chấp nhận không gửi batch thay vì báo lỗi
}

// Dùng cho 06:00 chào sáng (Top 5 tăng từ dữ liệu ONUS thật)
export async function getOnusTop5GainersForMorning() {
  const rows = await getOnusRowsFromHistory(120); // 2h gần nhất
  if (!rows.length) return [];
  return [...rows]
    .filter(r => Number.isFinite(Number(r.change)))
    .sort((a, b) => Number(b.change) - Number(a.change))
    .slice(0, 5)
    .map(r => r.symbol);
}
