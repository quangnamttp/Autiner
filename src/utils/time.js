const OWNER_ID = process.env.ALLOWED_TELEGRAM_USER_ID;

export function isOwner(chatId) {
  return String(chatId) === String(OWNER_ID);
}
export function fmtVN(date = new Date()) {
  const p = (n)=>String(n).padStart(2,'0');
  const d=new Date(date);
  return `${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth()+1)}/${d.getFullYear()}`;
}
