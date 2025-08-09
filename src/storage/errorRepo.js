// src/storage/errorRepo.js
import { getDb } from './db.js';

export async function logSourceError(exchange, error_message) {
  try {
    await getDb().query(
      `INSERT INTO errors (exchange, error_message) VALUES ($1, $2)`,
      [String(exchange || ''), String(error_message || '')]
    );
  } catch (e) {
    // tránh làm hỏng luồng chính nếu log lỗi DB thất bại
    // eslint-disable-next-line no-console
    console.error('[ERROR] logSourceError', e.message);
  }
}
