import { getDb } from './db.js';

export async function getConfig() {
  const { rows } = await getDb().query(`SELECT value FROM config WHERE key='app'`);
  if (!rows.length) return { active_exchange: 'ONUS' };
  const v = rows[0].value || {};
  return { active_exchange: v.active_exchange || 'ONUS' };
}
export async function setActiveExchange(ex) {
  await getDb().query(
    `INSERT INTO config (key, value) VALUES ('app', $1::jsonb)
     ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()`,
    [JSON.stringify({ active_exchange: ex })]
  );
}
export async function appendAudit(user_id, action, payload = {}) {
  await getDb().query(
    `INSERT INTO audit_log (user_id, action, payload) VALUES ($1,$2,$3::jsonb)`,
    [String(user_id), action, JSON.stringify(payload)]
  );
}
