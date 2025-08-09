// src/sources/onus/scrape.js
import axios from 'axios';
import * as cheerio from 'cheerio';

const CANDIDATE_URLS = [
  'https://goonus.io/futures',
  'https://goonus.io/future',
  'https://goonus.io/derivatives/futures'
];
const TIMEOUT = 10000;
const RETRY_PER_URL = 2;
const GAP_MS = 200;
const FRESH_S_MAX = 5;
const CROSS_TOL = 0.003; // 0.3%

const http = axios.create({
  timeout: TIMEOUT,
  headers: {
    'User-Agent': 'autiner-bot/1.0 (+render)',
    'Accept-Language': 'vi-VN,vi;q=0.9'
  },
});

const COL = {
  symbol: ['symbol','mã','coin','cặp','contract'],
  last:   ['price','giá','last','last price'],
  change: ['24h','24h%','%24h','24h change','change'],
  funding:['funding','funding rate','tỷ lệ funding'],
  vol5m:  ['vol 5m','volume 5m','5m vol']
};

const norm = s => String(s||'').toLowerCase().trim().replace(/\s+/g,' ');
const num  = s => {
  const t = String(s||'').replace(/[, ]/g,'').replace(/\u00A0/g,'').replace(/[^0-9.\-]/g,'');
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
};

async function fetchHtmlFromCandidates() {
  let lastErr;
  for (const url of CANDIDATE_URLS) {
    for (let i = 0; i < RETRY_PER_URL; i++) {
      try {
        const { data, status } = await http.get(url);
        if (status === 200 && typeof data === 'string' && data.length > 1000) {
          return { html: data, sourceUrl: url };
        }
      } catch (e) {
        lastErr = e;
      }
      await new Promise(r => setTimeout(r, GAP_MS));
    }
  }
  throw lastErr || new Error('All candidate URLs failed');
}

function pickTable($) {
  // chọn bảng có nhiều <tr> nhất
  let best = null, rows = 0;
  $('table').each((_, el) => {
    const r = $(el).find('tr').length;
    if (r > rows) { rows = r; best = el; }
  });
  return best;
}

function mapHeaders(headers) {
  const map = {};
  headers.forEach((h,i) => {
    const n = norm(h);
    for (const [k, aliases] of Object.entries(COL)) {
      if (aliases.some(a => n.includes(a))) { map[i] = k; break; }
    }
  });
  if (!Object.values(map).includes('symbol') || !Object.values(map).includes('last')) {
    throw new Error(`missing required columns (headers: ${headers.join(' | ')})`);
  }
  return map;
}

function parseOnce(html) {
  const $ = cheerio.load(html);

  // nếu trang không có bảng mà là list card → thử đọc theo class gợi ý
  const cardRows = [];
  $('[class*=row],[class*=item],[class*=contract]').each((_, el) => {
    const txt = $(el).text().toLowerCase();
    if (txt.includes('usdt') || txt.includes('vnd')) {
      const sym = $(el).find('b, strong, [class*=symbol]').first().text().trim().replace(/\s+/g,'');
      const priceT = $(el).find('[class*=price]').first().text().trim();
      if (sym && priceT) {
        const last = num(priceT);
        if (Number.isFinite(last)) {
          cardRows.push({ symbol: sym, last });
        }
      }
    }
  });

  let rows = [];
  if (cardRows.length >= 5) {
    rows = cardRows; // chấp nhận tối thiểu 5 hàng từ layout card
  } else {
    // layout bảng
    const t = pickTable($);
    if (!t) throw new Error('no table found');

    const headers = [];
    $(t).find('thead tr th, thead tr td').each((_, th) => headers.push($(th).text().trim()));
    const map = mapHeaders(headers);

    $(t).find('tbody tr').each((_, tr) => {
      const o = { symbol: null, last: null, change: null, funding: null, vol5m: null };
      $(tr).find('td').each((i, td) => {
        const k = map[i]; if (!k) return;
        const raw = $(td).text().trim();
        if (k === 'symbol') o.symbol = raw.replace(/\s+/g,'');
        else o[k] = num(raw);
      });
      if (o.symbol && Number.isFinite(o.last)) rows.push(o);
    });
  }

  return { rows, fetchedAt: Date.now() };
}

function crossMerge(a, b) {
  const m = new Map(b.rows.map(r => [r.symbol, r]));
  const out = [];
  for (const r of a.rows) {
    const q = m.get(r.symbol);
    if (!q) continue;
    const diff = Math.abs(r.last - q.last) / Math.max(1, r.last);
    if (diff > CROSS_TOL) continue;
    out.push({
      symbol: r.symbol,
      last: Math.round((r.last + q.last) / 2), // VND int
      change:  Number.isFinite(r.change)  ? r.change  : q.change  ?? null,
      funding: Number.isFinite(r.funding) ? r.funding : q.funding ?? null,
      vol5m:   Number.isFinite(r.vol5m)   ? r.vol5m   : q.vol5m   ?? null
    });
  }
  return { rows: out, fetchedAt: Math.max(a.fetchedAt, b.fetchedAt) };
}

export async function getOnusSnapshot() {
  // lần 1
  const { html: h1 } = await fetchHtmlFromCandidates();
  const p1 = parseOnce(h1);
  await new Promise(r => setTimeout(r, GAP_MS));
  // lần 2
  const { html: h2 } = await fetchHtmlFromCandidates();
  const p2 = parseOnce(h2);

  const merged = crossMerge(p1, p2);
  if (!merged.rows.length) throw new Error('Onus empty rows');

  const age = (Date.now() - merged.fetchedAt) / 1000;
  if (age > FRESH_S_MAX) throw new Error(`Onus data stale ${age.toFixed(1)}s`);

  return merged.rows; // [{symbol,last,change,funding,vol5m}]
}
