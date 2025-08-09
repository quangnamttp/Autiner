import { readFileSync } from 'fs';
import { Pool } from 'pg';
import { logger } from '../utils/logger.js';
import path from 'path';
import { fileURLToPath } from 'url';

let pool;

export function getDb() {
  if (!pool) {
    const url = process.env.DATABASE_URL;
    if (!url) throw new Error('Missing DATABASE_URL');
    pool = new Pool({ connectionString: url, ssl: getSslOption(url) });
  }
  return pool;
}

function getSslOption(url) {
  // Render PostgreSQL thường không yêu cầu SSL strict;
  // nếu cần có thể set { rejectUnauthorized: false }
  return url.includes('render.com') ? { rejectUnauthorized: false } : false;
}

export async function initDb() {
  const db = getDb();
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const sqlPath = path.join(__dirname, 'models.sql');
  const sql = readFileSync(sqlPath, 'utf8');
  await db.query(sql);
  logger.info('DB migrated (config, audit_log).');
}
