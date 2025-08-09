import { readFileSync } from 'fs';
import { Pool } from 'pg';
import path from 'path';
import { fileURLToPath } from 'url';

let pool;

export function getDb() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error('Missing DATABASE_URL');
  if (!pool) {
    const ssl = url.includes('render.com') ? { rejectUnauthorized: false } : false;
    pool = new Pool({ connectionString: url, ssl });
  }
  return pool;
}

export async function initDb() {
  const db = getDb();
  const __filename = fileURLToPath(import.meta.url);
  const __dirname = path.dirname(__filename);
  const sql = readFileSync(path.join(__dirname, 'models.sql'), 'utf8');
  await db.query(sql);
}
