// src/sources/onus/cache.js
import { getOnusSnapshot } from './scrape.js';

let lastGood = null; // { rows, fetchedAt }
let polling = false;

/** Poll ONUS định kỳ (06:00–22:00 tăng nhịp) */
export function startOnusPoller(opt = {}) {
  if (polling) return;
  polling = true;

  const base = Number(opt.intervalMs) || 20000;

  async function tick() {
    const now = new Date();
    const h = now.getHours();
    const active = h >= 6 && h <= 22;
    const intervalMs = active ? Math.min(10000, base) : base;

    try {
      const rows = await getOnusSnapshot();   // lấy snapshot mới
      lastGood = { rows, fetchedAt: Date.now() };
    } catch (_e) {
      // giữ lastGood, lần sau thử tiếp
    } finally {
      setTimeout(tick, intervalMs);
    }
  }

  tick(); // chạy ngay 1 lần
}

/** Lấy snapshot ưu tiên cache; nếu quá hạn → retry; nếu vẫn fail → dùng last-good ≤ 60' */
export async function getOnusSnapshotCached(opt = {}) {
  const maxAgeSec = Number(opt.maxAgeSec) || 120;
  const quickRetries = Number(opt.quickRetries) || 3;

  const now = Date.now();
  if (lastGood && (now - lastGood.fetchedAt) / 1000 <= maxAgeSec) {
    return lastGood.rows;
  }

  for (let i = 0; i < quickRetries; i++) {
    try {
      const rows = await getOnusSnapshot();
      lastGood = { rows, fetchedAt: Date.now() };
      return rows;
    } catch (_e) {
      await new Promise(r => setTimeout(r, 250));
    }
  }

  if (lastGood && (now - lastGood.fetchedAt) / 1000 <= 3600) {
    return lastGood.rows;
  }

  throw new Error('Onus không có dữ liệu hợp lệ (>60 phút)');
}

/** Meta cho /source */
export function getOnusMeta() {
  if (!lastGood) return { fetchedAt: null, ageSec: null, hasData: false };
  const ageSec = Math.max(0, Math.round((Date.now() - lastGood.fetchedAt) / 1000));
  return { fetchedAt: lastGood.fetchedAt, ageSec, hasData: !!(lastGood.rows?.length) };
}

/** ⬅️ HÀM NÀY LÀ NGUYÊN NHÂN THIẾU — thêm export để scheduler dùng bù kèo */
export function getOnusLastGood() {
  return lastGood; // { rows, fetchedAt } | null
}
