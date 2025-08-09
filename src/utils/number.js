// VND: không thập phân, dấu . tách nghìn
export function formatVND(n) {
  const i = Math.round(Number(n) || 0);
  return i.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

// USD: giữ thập phân, không động chạm
export function formatUSD(n) {
  return String(n);
}
