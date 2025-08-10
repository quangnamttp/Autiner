// src/sources/onus/scrape.js
// Lấy dữ liệu ONUS Futures trực tiếp bằng Puppeteer (mặc định), quét toàn bộ symbol.
// Có retry, chờ render SPA, chống đổi layout (đa selector) + cross-check hạn chế nhiễu.

import * as cheerio from 'cheerio';

let puppeteer;

// ==== Cấu hình ====
const CANDIDATE_URLS = [
  'https://goonus.io/futures',
  'https://goonus.io/future',
  'https://goonus.io/derivatives/futures',
  'https://goonus.io/futures?lang=vi',
  'https://goonus.io/future?lang=vi',
];

const LAUNCH_ARGS = ['--no-sandbox','--disable-setuid-sandbox'];
const PAGE_TIMEOUT_MS = 25000;          // tổng thời gian chờ cho 1 lần load
const WAIT_TABLE_MS   = 12000;          // chờ bảng/các card
const BETWEEN_READ_MS = 350;            // nghỉ giữa 2 lần đọc để cross-check
const RETRY_ROUNDS    = 2;              // số vòng retry theo URL

// Cross-check: nếu giá lệch >0.6% giữa 2 lần đọc thì loại
const CROSS_TOL = 0.006;

// tối thiểu số dòng để coi là có dữ liệu thật
const MIN_ROWS   = 15;

// ==== utils ====
const UA_POOL = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 Version/16.5 Safari/605.1.15',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
];
const rand = (n) => Math.floor(Math.random()*n);
const sleep = (ms) => new Promise(r=>setTimeout(r,ms));
const toNum = (s) => {
  const t = String(s||'').replace(/\u00A0/g,'').replace(/[, ]/g,'').replace(/[^0-9.\-]/g,'');
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
};
const toPct = (s) => {
  if (s == null) return null;
  const m = String(s).match(/-?\d+(\.\d+)?/);
  return m ? Number(m[0]) : null;
};

// Chuẩn hóa bản ghi
function normRow(r) {
  if (!r) return null;
  const symbol = String(r.symbol||'').toUpperCase().replace(/\s+/g,'').trim();
  if (!symbol) return null;

  // last (VND) — làm tròn tới đồng
  const last  = toNum(r.last);
  if (!Number.isFinite(last) || last <= 0) return null;

  const change  = r.change != null ? toPct(r.change) : null;          // % 24h
  const funding = r.funding != null ? toPct(r.funding) : null;        // % funding
  const vol5m   = r.vol5m != null ? toNum(r.vol5m) : null;

  return {
    symbol,
    last: Math.round(last),
    change: change,        // % (có thể âm)
    funding: funding,      // % (có thể âm)
    vol5m: vol5m           // số
  };
}

// Đọc HTML hiện tại từ page và parse ra rows (đa layout)
function parseDom(html) {
  const $ = cheerio.load(html);
  const rows = [];

  // 1) Layout dạng bảng
  let bestTable = null, bestRows = 0;
  $('table').each((_, t) => {
    const r = $(t).find('tr').length;
    if (r > bestRows) { bestRows = r; bestTable = t; }
  });

  if (bestTable) {
    // tìm header
    const headers = [];
    $(bestTable).find('thead tr th, thead tr td').each((_, th) => headers.push($(th).text().trim().toLowerCase()));
    // map cột linh hoạt
    const idx = { sym: -1, last: -1, chg: -1, fund: -1, vol5: -1 };
    headers.forEach((h, i) => {
      if (idx.sym  < 0 && /(symbol|mã|coin|cặp|contract)/.test(h)) idx.sym = i;
      if (idx.last < 0 && /(price|giá|last|last\s*price)/.test(h)) idx.last = i;
      if (idx.chg  < 0 && /(24h|\%24|change|thay.*đổi)/.test(h)) idx.chg = i;
      if (idx.fund < 0 && /(funding|funding\s*rate|tỷ.*fund)/.test(h)) idx.fund = i;
      if (idx.vol5 < 0 && /(vol|volume).*(5m|5 m)/.test(h)) idx.vol5 = i;
    });

    $(bestTable).find('tbody tr').each((_, tr) => {
      const tds = $(tr).find('td');
      if (!tds.length) return;
      const r = normRow({
        symbol: idx.sym  >= 0 ? $(tds[idx.sym]).text()  : $(tds[0]).text(),
        last:   idx.last >= 0 ? $(tds[idx.last]).text() : null,
        change: idx.chg  >= 0 ? $(tds[idx.chg]).text()  : null,
        funding:idx.fund >= 0 ? $(tds[idx.fund]).text() : null,
        vol5m:  idx.vol5 >= 0 ? $(tds[idx.vol5]).text() : null,
      });
      if (r) rows.push(r);
    });
  }

  // 2) Layout dạng “card/list” (khi futures render bằng div)
  if (rows.length < MIN_ROWS) {
    $('[class*=row],[class*=item],[class*=contract],[class*=symbol]').each((_, el) => {
      const $el = $(el);
      const text = $el.text().toLowerCase();
      if (!/(usdt|vnd)/.test(text)) return;

      // tìm symbol
      const sym =
        $el.find('[class*=symbol], b, strong').first().text().trim() ||
        $el.attr('data-symbol') || '';

      // tìm price
      const priceText =
        $el.find('[class*=price]').first().text().trim() ||
        $el.find('[data-field=price]').first().text().trim() || '';

      if (!sym || !priceText) return;

      // optional: change/funding/vol5m
      const chgText =
        $el.find('[class*=change]').first().text().trim() ||
        $el.find('[data-field=change]').first().text().trim() || '';

      const fundText =
        $el.find('[class*=fund]').first().text().trim() ||
        $el.find('[data-field=funding]').first().text().trim() || '';

      const volText =
        $el.find('[class*=vol]').first().text().trim() ||
        $el.find('[data-field*=vol]').first().text().trim() || '';

      const r = normRow({ symbol: sym, last: priceText, change: chgText, funding: fundText, vol5m: volText });
      if (r) rows.push(r);
    });
  }

  // Lọc bất thường
  return rows.filter(r =>
    r.last > 10 && r.last < 1e10 && r.symbol.length >= 3
  );
}

// Chờ trang render xong (có bảng/có card + số lượng đủ)
async function waitForFutures(page) {
  await page.waitForFunction(() => {
    const enoughTableRows = document.querySelectorAll('table tbody tr').length >= 10;
    const enoughCards     = document.querySelectorAll('[class*=price]').length >= 10;
    return enoughTableRows || enoughCards;
  }, { timeout: WAIT_TABLE_MS }).catch(()=>{});
}

// Đọc 1 lần (render → lấy HTML → parse)
async function readOnce(page) {
  await waitForFutures(page);
  const html = await page.content();
  return parseDom(html);
}

// Cross-check 2 lần để lọc nhiễu
function crossMerge(a, b) {
  const m = new Map(b.map(r => [r.symbol, r]));
  const out = [];
  for (const r of a) {
    const q = m.get(r.symbol); if (!q) continue;
    const diff = Math.abs(r.last - q.last) / Math.max(1, r.last);
    if (diff > CROSS_TOL) continue;
    out.push({
      symbol: r.symbol,
      last: Math.round((r.last + q.last)/2),
      change: Number.isFinite(r.change)  ? r.change  : q.change ?? null,
      funding:Number.isFinite(r.funding) ? r.funding : q.funding ?? null,
      vol5m:  Number.isFinite(r.vol5m)   ? r.vol5m   : q.vol5m   ?? null,
    });
  }
  return out;
}

// === API chính: trả về mảng [{symbol,last,change,funding,vol5m}] ===
export async function getOnusSnapshot() {
  if (!puppeteer) puppeteer = (await import('puppeteer')).default;

  const browser = await puppeteer.launch({ args: LAUNCH_ARGS });
  try {
    const page = await browser.newPage();
    await page.setUserAgent(UA_POOL[rand(UA_POOL.length)]);
    await page.setViewport({ width: 1366, height: 900 });
    // Chặn tài nguyên nặng
    await page.setRequestInterception(true);
    page.on('request', (req) => {
      const type = req.resourceType();
      if (['image','media','font'].includes(type)) return req.abort();
      return req.continue();
    });

    let first = null, second = null;

    // Thử qua các URL ứng viên + retry
    for (const url of CANDIDATE_URLS) {
      for (let i = 0; i < RETRY_ROUNDS; i++) {
        try {
          await page.goto(url, { waitUntil: 'domcontentloaded', timeout: PAGE_TIMEOUT_MS });
          const r1 = await readOnce(page);
          if (r1.length >= MIN_ROWS) {
            first = r1;
            await sleep(BETWEEN_READ_MS);
            const r2 = await readOnce(page);
            second = r2;
            break;
          }
        } catch (_) {
          // thử URL khác hoặc vòng sau
        }
      }
      if (first && second) break;
    }

    const rows = (first && second) ? crossMerge(first, second) : (first || []);
    if (!rows.length || rows.length < MIN_ROWS) {
      // Thử chụp lần cuối cùng thêm 1 URL nhanh (nếu chưa đủ)
      for (const url of CANDIDATE_URLS) {
        try {
          await page.goto(url, { waitUntil: 'domcontentloaded', timeout: PAGE_TIMEOUT_MS });
          const r = await readOnce(page);
          if (r.length >= MIN_ROWS) return r;
        } catch (_) {}
      }
      throw new Error('Onus rows insufficient');
    }
    return rows;
  } finally {
    try { await browser.close(); } catch {}
  }
}
