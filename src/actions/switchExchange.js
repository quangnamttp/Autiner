// src/actions/switchExchange.js
import { getDb } from '../storage/db.js';

export async function switchExchange(ex) {
  const name = String(ex || 'ONUS').toUpperCase();
  if (!['ONUS','MEXC','NAMI'].includes(name)) throw new Error('exchange invalid');

  // lưu vào bảng config.key='app' field active_exchange
  await getDb().query(
    `
    INSERT INTO config (key, value)
    VALUES ('app', jsonb_build_object('active_exchange',$1))
    ON CONFLICT (key) DO UPDATE
      SET value = jsonb_set(config.value, '{active_exchange}', to_jsonb($1::text)),
          updated_at = NOW()
    `,
    [name]
  );
}
