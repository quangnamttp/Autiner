const OWNER_ID = process.env.ALLOWED_TELEGRAM_USER_ID;

export function isOwner(chatId) {
  return String(chatId) === String(OWNER_ID);
}

// Format: HH:mm DD/MM/YYYY theo VN
export function fmtVN(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  const d = new Date(date);
  const dd = pad(d.getDate());
  const mm = pad(d.getMonth() + 1);
  const yyyy = d.getFullYear();
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  return `${hh}:${mi} ${dd}/${mm}/${yyyy}`;
}
