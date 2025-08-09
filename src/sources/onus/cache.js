// src/sources/onus/cache.js
import { getOnusSnapshot } from './scrape.js';
import { saveOnusSnapshot } from '../../storage/onusRepo.js';

let lastGood = null; // { rows, fetchedAt }
let polling = false;

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
      const rows = await getOnusSnapshot();
      lastGood = { rows, fetchedAt: Date.now() };
      // ✅ Lưu DB để làm “kho dự phòng”
      await saveOnusSnapshot(rows, lastGood.fetchedAt);
    } catch (_e) {
      // giữ lastGood, lần sau thử tiếp
    } finally {
      setTimeout(tick, intervalMs);
    }
  }

  tick(); // chạy ngay 1 lần
}

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
      await saveOnusSnapshot(rows, lastGood.fetchedAt);
      return rows;
    } catch (_e) {
      await new Promise(r => setTimeout(r, 250));
    }
  }

  // Cho phép dùng lastGood (nếu có), vẫn là dữ liệu ONUS
  if (lastGood) return lastGood.rows;

  // Không ném lỗi nữa (theo yêu cầu “không báo lỗi”)
  return [];
}

export function getOnusMeta() {
  if (!lastGood) return { fetchedAt: null, ageSec: null, hasData: false };
  const ageSec = Math.max(0, Math.round((Date.now() - lastGood.fetchedAt) / 1000));
  return { fetchedAt: lastGood.fetchedAt, ageSec, hasData: !!(lastGood.rows?.length) };
}

export function getOnusLastGood() {
  return lastGood;
}
