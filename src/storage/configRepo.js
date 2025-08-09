import { getDb } from './db.js';

export async function getConfig() {
  const db = getDb();
  const { rows } = await db.query(`SELECT value FROM config WHERE key='app'`);
  if (rows.length === 0) {
    // fallback an toàn
    return { active_exchange: 'ONUS' };
  }
  const v = rows[0].value || {};
  return {
    active_exchange: v.active_exchange || 'ONUS'
  };
}

export async function setActiveExchange(ex) {
  const db = getDb();
  await db.query(
    `INSERT INTO config (key, value)
     VALUES ('app', $1::jsonb)
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()`,
    [JSON.stringify({ active_exchange: ex })]
  );
}

export async function appendAudit(user_id, action, payload = {}) {
  const db = getDb();
  await db.query(
    `INSERT INTO audit_log (user_id, action, payload) VALUES ($1, $2, $3::jsonb)`,
    [String(user_id), action, JSON.stringify(payload)]
  );
}
