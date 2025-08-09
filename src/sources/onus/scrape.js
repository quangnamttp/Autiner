// src/sources/onus/scrape.js
// Scraping ONUS Futures với nhiều URL dự phòng + retry + cross-check 2 lần

import axios from 'axios';
import * as cheerio from 'cheerio';

// Nhiều URL có thể hiển thị bảng futures của ONUS
const CANDIDATE_URLS = [
  'https://goonus.io/futures',
  'https://goonus.io/future',
  'https://goonus.io/derivatives/futures'
];

const TIMEOUT = 12000;
const RETRY_PER_URL = 2;
const GAP_MS = 220;
const FRESH_S_MAX = 6;     // dữ liệu “tươi” tối đa 6s giữa 2 lần đọc
const CROSS_TOL = 0.003;   // chênh lệch > 0.3% giữa 2 lần → bỏ
const MIN_ROWS = 15;       // tối thiểu số cặp để coi là “đủ dữ liệu”

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 Version/16.5 Safari/605.1.15',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
];

const norm = s => String(s||'').toLowerCase().trim().replace(/\s+/g,' ');
const num  = s => {
  const t = String(s||'')
    .replace(/[, ]/g,'')
    .replace(/\u00A0/g,'')
    .replace(/[^0-9.\-]/g,'');
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
};

function rand(n){ return Math.floor(Math.random()*n); }
function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

function makeHttp() {
  return axios.create({
    timeout: TIMEOUT,
    headers: {
      'User-Agent': USER_AGENTS[rand(USER_AGENTS.length)],
      'Accept': 'text/html,application/xhtml+xml',
      'Accept-Encoding': 'gzip, deflate, br',
      'Accept-Language': 'vi-VN,vi;q=0.9,en;q=0.8',
      'Cache-Control': 'no-cache'
    },
    decompress: true,
    maxRedirects: 3,
    validateStatus: s => s >= 200 && s < 400
  });
}

const COL = {
  symbol: ['symbol','mã','coin','cặp','contract'],
  last:   ['price','giá','last','last price'],
  change: ['24h','24h%','%24h','24h change','change'],
  funding:['funding','funding rate','tỷ lệ funding'],
  vol5m:  ['vol 5m','volume 5m','5m vol']
};

async function fetchHtmlFromCandidates() {
  let lastErr;
  for (const url of CANDIDATE_URLS) {
    for (let i=0; i<RETRY_PER_URL; i++) {
      try {
        const http = makeHttp();
        const { data, status } = await http.get(url);
        if (status === 200 && typeof data === 'string' && data.length > 1000) {
          return { html: data, sourceUrl: url };
        }
      } catch (e) { lastErr = e; }
      await sleep(GAP_MS + rand(200));
    }
  }
  throw lastErr || new Error('All candidate URLs failed');
}

function pickTable($) {
  // chọn bảng có nhiều <tr> nhất
  let best=null, rows=0;
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

  // Fallback dạng “card”
  const cardRows = [];
  $('[class*=row],[class*=item],[class*=contract]').each((_, el) => {
    const txt = $(el).text().toLowerCase();
    if (txt.includes('usdt') || txt.includes('vnd')) {
      const sym = $(el).find('b, strong, [class*=symbol]').first().text().trim().replace(/\s+/g,'');
      const priceT = $(el).find('[class*=price]').first().text().trim();
      if (sym && priceT) {
        const last = num(priceT);
        if (Number.isFinite(last)) cardRows.push({ symbol: sym, last });
      }
    }
  });

  let rows = [];
  if (cardRows.length >= MIN_ROWS) {
    rows = cardRows;
  } else {
    // Layout dạng bảng
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

  // Lọc dữ liệu xấu (giá VND hợp lý)
  rows = rows.filter(r => Number.isFinite(r.last) && r.last > 10 && r.last < 1e10);

  return { rows, fetchedAt: Date.now() };
}

function crossMerge(a, b) {
  const m = new Map(b.rows.map(r => [r.symbol, r]));
  const out = [];
  for (const r of a.rows) {
    const q = m.get(r.symbol); if (!q) continue;
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
  // đọc 2 lần & cross-check để loại nhiễu
  const { html: h1 } = await fetchHtmlFromCandidates();
  const p1 = parseOnce(h1);
  await sleep(GAP_MS + rand(200));
  const { html: h2 } = await fetchHtmlFromCandidates();
  const p2 = parseOnce(h2);

  const merged = crossMerge(p1, p2);
  if (!merged.rows.length || merged.rows.length < MIN_ROWS) {
    throw new Error('Onus rows insufficient');
  }

  const age = (Date.now() - merged.fetchedAt) / 1000;
  if (age > FRESH_S_MAX) throw new Error(`Onus data stale ${age.toFixed(1)}s`);

  return merged.rows; // [{symbol,last,change,funding,vol5m}]
}
