// src/storage/onusRepo.js
import { getDb } from './db.js';

export async function saveOnusSnapshot(rows, fetchedAtMs) {
  if (!Array.isArray(rows) || !rows.length) return;
  const fetchedIso = new Date(fetchedAtMs || Date.now()).toISOString();
  await getDb().query(
    `INSERT INTO onus_snapshots (fetched_at, rows) VALUES ($1, $2::jsonb)`,
    [fetchedIso, JSON.stringify(rows)]
  );
}

/**
 * Lấy hợp nhất dữ liệu ONUS trong cửa sổ gần đây.
 * @param {number} lookbackMinutes  mặc định 360 (6 giờ)
 * @returns {Array<{symbol,last,change,funding,vol5m}>}
 */
export async function getOnusRowsFromHistory(lookbackMinutes = 360) {
  const { rows } = await getDb().query(
    `SELECT rows FROM onus_snapshots
     WHERE fetched_at >= NOW() - ($1 || ' minutes')::interval
     ORDER BY fetched_at DESC
     LIMIT 60`,
    [lookbackMinutes]
  );
  if (!rows.length) return [];
  // Gộp theo symbol, ưu tiên bản ghi mới hơn
  const map = new Map();
  for (const r of rows) {
    const arr = Array.isArray(r.rows) ? r.rows : r.rows?.items || [];
    for (const it of arr) {
      const sym = String(it.symbol || '').trim();
      if (!sym) continue;
      if (!map.has(sym)) {
        map.set(sym, {
          symbol: sym,
          last: Number(it.last) || null,
          change: Number(it.change) || null,
          funding: Number(it.funding) || null,
          vol5m: Number(it.vol5m) || null
        });
      }
    }
  }
  return Array.from(map.values());
}
