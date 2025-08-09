// src/sources/onus/scrape.js
import axios from 'axios';
import * as cheerio from 'cheerio';

const URL = 'https://goonus.io/future';   // đường dẫn futures của Onus
const TIMEOUT = 10000;
const RETRY = 3;
const GAP_MS = 250;
const FRESH_S_MAX = 5;        // dữ liệu “tươi” tối đa
const CROSS_TOL = 0.003;      // 0.3% lệch giữa 2 lần đọc -> bỏ

const http = axios.create({
  timeout: TIMEOUT,
  headers: {
    'User-Agent': 'autiner-bot',
    'Accept-Language': 'vi-VN,vi;q=0.9'
  }
});

const COL = {
  symbol: ['symbol','mã','coin','cặp'],
  last:   ['price','giá','last','last price'],
  change: ['24h','24h%','%24h','24h change'],
  funding:['funding','funding rate','tỷ lệ funding'],
  vol5m:  ['vol 5m','volume 5m','5m vol']
};

const norm = s => String(s||'').toLowerCase().trim().replace(/\s+/g,' ');
const num  = s => {
  const t = String(s||'').replace(/[, ]/g,'').replace(/\u00A0/g,'').replace(/[^0-9.\-]/g,'');
  if (!t) return null; const n = Number(t);
  return Number.isFinite(n) ? n : null;
};

async function fetchHtml(){
  let lastErr;
  for (let i=0;i<RETRY;i++){
    try {
      const { data } = await http.get(URL);
      if (typeof data === 'string' && data.length>1000) return data;
    } catch(e){ lastErr = e; }
    await new Promise(r=>setTimeout(r,GAP_MS));
  }
  throw lastErr || new Error('fetch failed');
}

function pickTable($){
  let best=null, rows=0;
  $('table').each((_,el)=>{ const r=$(el).find('tr').length; if(r>rows){rows=r; best=el;} });
  return best;
}

function mapHeaders(headers){
  const map = {};
  headers.forEach((h,i)=>{
    const nh = norm(h);
    for (const [k, aliases] of Object.entries(COL)){
      if (aliases.some(a => nh.includes(a))) { map[i]=k; break; }
    }
  });
  if (!Object.values(map).includes('symbol') || !Object.values(map).includes('last')) {
    throw new Error(`missing required columns (headers: ${headers.join(' | ')})`);
  }
  return map;
}

function parseOnce(html){
  const $ = cheerio.load(html);
  const t = pickTable($);
  if (!t) throw new Error('no table found');

  const headers = [];
  $(t).find('thead tr th, thead tr td').each((_,th)=> headers.push($(th).text().trim()));
  const map = mapHeaders(headers);

  const rows = [];
  $(t).find('tbody tr').each((_,tr)=>{
    const o={symbol:null,last:null,change:null,funding:null,vol5m:null};
    $(tr).find('td').each((i,td)=>{
      const k = map[i]; if (!k) return;
      const raw = $(td).text().trim();
      if (k==='symbol') o.symbol = raw.replace(/\s+/g,'');
      else o[k] = num(raw);
    });
    if (o.symbol && Number.isFinite(o.last)) rows.push(o);
  });

  return { rows, fetchedAt: Date.now() };
}

function crossMerge(a,b){
  const m = new Map(b.rows.map(r=>[r.symbol,r]));
  const out = [];
  for (const r of a.rows){
    const q = m.get(r.symbol); if(!q) continue;
    const diff = Math.abs(r.last - q.last)/Math.max(1,r.last);
    if (diff > CROSS_TOL) continue;
    out.push({
      symbol: r.symbol,
      last: Math.round((r.last + q.last)/2),    // VND, làm tròn, KHÔNG thập phân
      change:  Number.isFinite(r.change)  ? r.change  : q.change  ?? null,
      funding: Number.isFinite(r.funding) ? r.funding : q.funding ?? null,
      vol5m:   Number.isFinite(r.vol5m)   ? r.vol5m   : q.vol5m   ?? null
    });
  }
  return { rows: out, fetchedAt: Math.max(a.fetchedAt,b.fetchedAt) };
}

export async function getOnusSnapshot() {
  const p1 = parseOnce(await fetchHtml());
  await new Promise(r=>setTimeout(r,GAP_MS));
  const p2 = parseOnce(await fetchHtml());

  const merged = crossMerge(p1,p2);
  const age = (Date.now()-merged.fetchedAt)/1000;
  if (age > FRESH_S_MAX) throw new Error(`Onus data stale ${age.toFixed(1)}s`);
  if (!merged.rows.length) throw new Error('Onus empty rows');
  return merged.rows; // [{symbol,last,change,funding,vol5m}]
}
