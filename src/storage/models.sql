CREATE TABLE IF NOT EXISTS config (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO config (key, value)
VALUES ('app', '{"active_exchange":"ONUS"}'::jsonb)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS errors (
  id BIGSERIAL PRIMARY KEY,
  exchange TEXT NOT NULL,
  error_message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lưu vòng đệm snapshot ONUS: mỗi bản ghi chứa mảng tickers dạng JSONB
CREATE TABLE IF NOT EXISTS onus_snapshots (
  id BIGSERIAL PRIMARY KEY,
  fetched_at TIMESTAMPTZ NOT NULL,
  rows JSONB NOT NULL,          -- [{symbol,last,change,funding,vol5m}]
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Chỉ mục thời gian để truy xuất nhanh
CREATE INDEX IF NOT EXISTS idx_onus_snapshots_fetched_at ON onus_snapshots(fetched_at DESC);
