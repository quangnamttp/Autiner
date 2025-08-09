CREATE TABLE IF NOT EXISTS config (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO config (key, value)
VALUES ('app', '{"active_exchange":"ONUS"}'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- bảng ghi log lỗi nguồn dữ liệu
CREATE TABLE IF NOT EXISTS errors (
  id BIGSERIAL PRIMARY KEY,
  exchange TEXT NOT NULL,
  error_message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
