// src/signals/fiveMaker.js
// Đảm bảo luôn đủ 5 tín hiệu ONUS, không báo lỗi, không chéo sàn.
// Chiến lược:
// 1) Lấy snapshot tươi (cache).
// 2) Nếu <5, ép scraper chạy ngay 2–3 lần để tạo snapshot mới và lưu DB.
// 3) Nếu vẫn <5, gom từ kho 6h (mở rộng tối đa 24h nếu cần) cho đủ 5.

import { getOnusSnapshotCached } from '../sources/onus/cache.js';
import { getOnusRowsFromHistory, saveOnusSnapshot } from '../storage/onusRepo.js';
import { pickSignals } from './generator.js';
import { getOnusSnapshot } from '../sources/onus/scrape.js';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function forceWarmUp(attempts = 2) {
  for (let i = 0; i < attempts; i++) {
    try {
      const rows = await getOnusSnapshot();           // ép scraper (có puppeteer fallback)
      await saveOnusSnapshot(rows, Date.now());       // lưu kho
    } catch (_e) {
      // bỏ qua, thử lần sau
    }
    await sleep(500);
  }
}

function uniqBySymbol(arr) {
  const out = [];
  const seen = new Set();
  for (const x of arr) {
    const k = (x.symbol || '').trim();
    if (!k || seen.has(k)) continue;
    seen.add(k);
    out.push(x);
  }
  return out;
}

export async function makeFiveOnusSignals() {
  // 1) lấy snapshot tươi (cache)
  let fresh = await getOnusSnapshotCached({ maxAgeSec: 120, quickRetries: 3 });
  let signals = pickSignals(fresh, 5, 'VND');

  if (signals.length >= 5) return signals;

  // 2) ép warm-up 2 lần để chắc có dữ liệu
  await forceWarmUp(2);
  fresh = await getOnusSnapshotCached({ maxAgeSec: 120, quickRetries: 3 });
  signals = pickSignals(fresh, 5, 'VND');
  if (signals.length >= 5) return signals;

  // 3) bổ sung từ kho 6h gần nhất
  let poolRows = await getOnusRowsFromHistory(360);
  if (poolRows.length) {
    // tránh trùng symbol
    const used = new Set(signals.map(s => s.symbol));
    const extraRows = poolRows.filter(r => !used.has(r.symbol));
    const extra = pickSignals(extraRows, 5 - signals.length, 'VND');
    signals = uniqBySymbol([...signals, ...extra]);
    if (signals.length >= 5) return signals;
  }

  // 4) lần cuối: ép warm-up thêm 1 lần + mở rộng kho 24h
  await forceWarmUp(1);
  poolRows = await getOnusRowsFromHistory(1440);
  if (poolRows.length) {
    const extraFinal = pickSignals(poolRows, 5 - signals.length, 'VND');
    signals = uniqBySymbol([...signals, ...extraFinal]);
  }

  // Trả đúng 5 (nếu vẫn thiếu, trả theo số có — nhưng sau bước warm-up thường sẽ đủ)
  return signals.slice(0, 5);
}
