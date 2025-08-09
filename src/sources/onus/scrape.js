import axios from 'axios';
import * as cheerio from 'cheerio';

const URL = 'https://goonus.io/future'; // đúng tên path bạn yêu cầu
const TIMEOUT = 10000;
const RETRY = 3;
const GAP = 300; // ms giữa 2 lần
const FRESH_S = 5; // dữ liệu “tươi” tối đa
const CROSS_TOL = 0.003; // 0.3%

const COLUMN_ALIASES = {
  symbol: ['symbol','mã','coin','cặp'],
  last:   ['price','giá','last','last price'],
  funding:['funding','funding rate','tỷ lệ funding'],
  change: ['24h','24h%','%24h','24h change'],
  vol5m:  ['vol 5m','volume 5m','5m vol']
};

const http = axios.create({
  timeout: TIMEOUT,
  headers: { 'User-Agent': 'autiner-bot', 'Accept-Language': 'vi-VN,vi;q=0.9' }
});

function norm(s){ return String(s||'').toLowerCase().trim().replace(/\s+/g,' '); }
function parseNum(s){
  const t = String(s||'').replace(/[, ]/g,'').replace(/\u00A0/g,'').replace(/[^0-9.\-]/g,'');
  if(!t) return null; const n = Number(t); return Number.isFinite(n)?n:null;
}
function mapHeaders(headers){
  const map = {};
  headers.forEach((h,i)=>{
    const n = norm(h);
    for (const [k, list] of Object.entries(COLUMN_ALIASES)){
      if (list.some(a => n.includes(a))) { map[i]=k; break; }
    }
  });
  if (!Object.values(map).includes('symbol') || !Object.values(map).includes('last')){
    throw new Error(`missing required columns (headers: ${headers.join(' | ')})`);
  }
  return map;
}
function pickMainTable($){
  let best=null, rows=0;
  $('table').each((_,el)=>{ const r=$(el).find('tr').length; if(r>rows){rows=r; best=el;} });
  return best;
}
function parseOnce(html){
  const $=cheerio.load(html);
  const t = pickMainTable($); if(!t) throw new Error('no table');
  const headers=[], body=[];
  $(t).find('thead tr th, thead tr td').each((_,th)=> headers.push($(th).text().trim()));
  const map = mapHeaders(headers);

  $(t).find('tbody tr').each((_,tr)=>{
    const obj={symbol:null,last:null, funding:null, change:null, vol5m:null};
    $(tr).find('td').each((i,td)=>{
      const k = map[i]; if(!k) return;
      const raw = $(td).text().trim();
      if (k==='symbol') obj.symbol = raw.replace(/\s+/g,'');
      else obj[k] = parseNum(raw);
    });
    if (obj.symbol && Number.isFinite(obj.last)) body.push(obj);
  });

  return { rows: body, fetchedAt: Date.now() };
}
async function fetchHtml(){
  let lastErr;
  for (let i=0;i<RETRY;i++){
    try {
      const {data} = await http.get(URL);
      if (typeof data === 'string' && data.length>1000) return data;
    } catch(e){ lastErr=e; }
    await new Promise(r=>setTimeout(r,GAP));
  }
  throw lastErr || new Error('fetch failed');
}
function crossMerge(p1,p2){
  const map2 = new Map(p2.rows.map(r=>[r.symbol,r]));
  const out=[];
  for (const r1 of p1.rows){
    const r2 = map2.get(r1.symbol); if(!r2) continue;
    const diff = Math.abs(r1.last - r2.last) / Math.max(1, r1.last);
    if (diff > CROSS_TOL) continue; // lệch >0.3% bỏ
    out.push({
      symbol: r1.symbol,
      last: Math.round((r1.last + r2.last)/2), // VND, không thập phân
      funding: Number.isFinite(r1.funding)? r1.funding : r2.funding ?? null,
      change:  Number.isFinite(r1.change)?  r1.change  : r2.change  ?? null,
      vol5m:   Number.isFinite(r1.vol5m)?   r1.vol5m   : r2.vol5m   ?? null
    });
  }
  return { rows: out, fetchedAt: Math.max(p1.fetchedAt,p2.fetchedAt) };
}

export async function getOnusSnapshot(){
  const p1 = parseOnce(await fetchHtml());
  await new Promise(r=>setTimeout(r,150));
  const p2 = parseOnce(await fetchHtml());
  const merged = crossMerge(p1,p2);
  const age = (Date.now()-merged.fetchedAt)/1000;
  if (age > FRESH_S) throw new Error(`Onus data stale ${age.toFixed(1)}s`);
  return merged.rows; // [{symbol, last(VND int), funding, change, vol5m}]
}
