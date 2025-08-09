export function formatVND(n) {
  const i = Math.round(Number(n) || 0);
  return i.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}
export function formatUSD(n) {
  return String(n);
}
