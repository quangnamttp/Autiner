// src/sources/onus/cache.js
import { getOnusSnapshot } from './scrape.js';

let lastGood = null; // { rows, fetchedAt }
let polling = false;

/**
 * Khởi động poll dữ liệu ONUS định kỳ.
 * @param {object} opt
 * @param {number} opt.intervalMs  Chu kỳ poll (mặc định 20000ms)
 */
export function startOnusPoller(opt = {}) {
  if (polling) return;
  polling = true;

  const intervalMs = Number(opt.intervalMs) || 20000;

  async function tick() {
    try {
      const rows = await getOnusSnapshot();
      lastGood = { rows, fetchedAt: Date.now() };
    } catch (_e) {
      // Giữ lastGood, lần sau thử tiếp
    }
  }

  tick(); // chạy ngay 1 lần
  setInterval(tick, intervalMs);
}

/**
 * Lấy snapshot ưu tiên từ cache, thử nhanh nếu cache quá hạn.
 * @param {object} opt
 * @param {number} opt.maxAgeSec    Tuổi tối đa cho cache (mặc định 120s)
 * @param {number} opt.quickRetries Số lần thử nhanh nếu cache quá hạn (mặc định 3)
 * @returns {Promise<Array>}
 */
export async function getOnusSnapshotCached(opt = {}) {
  const maxAgeSec = Number(opt.maxAgeSec) || 120;
  const quickRetries = Number(opt.quickRetries) || 3;

  const now = Date.now();
  if (lastGood && (now - lastGood.fetchedAt) / 1000 <= maxAgeSec) {
    return lastGood.rows;
  }

  // Cache quá hạn → thử nhanh
  for (let i = 0; i < quickRetries; i++) {
    try {
      const rows = await getOnusSnapshot();
      lastGood = { rows, fetchedAt: Date.now() };
      return rows;
    } catch (_e) {
      await new Promise(r => setTimeout(r, 250));
    }
  }

  // Không lấy được → dùng last-good nếu ≤ 10 phút
  if (lastGood && (now - lastGood.fetchedAt) / 1000 <= 600) {
    return lastGood.rows;
  }

  throw new Error('Onus không có dữ liệu hợp lệ (>10 phút)');
}

/**
 * Meta để lệnh /source hiển thị
 * @returns {{fetchedAt:number|null, ageSec:number|null, hasData:boolean}}
 */
export function getOnusMeta() {
  if (!lastGood) return { fetchedAt: null, ageSec: null, hasData: false };
  const ageSec = Math.max(0, Math.round((Date.now() - lastGood.fetchedAt) / 1000));
  return { fetchedAt: lastGood.fetchedAt, ageSec, hasData: !!(lastGood.rows?.length) };
}
