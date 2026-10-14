/** Formatting helpers - Indonesian locale, Asia/Jakarta timezone, IDR currency. */

const DEFAULT_TZ = process.env.REACT_APP_DEFAULT_TIMEZONE || 'Asia/Jakarta';
const DEFAULT_CURRENCY = process.env.REACT_APP_DEFAULT_CURRENCY || 'IDR';

export function formatCurrency(value, currency = DEFAULT_CURRENCY) {
  const number = Number(value || 0);
  try {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(number);
  } catch (e) {
    return `${currency} ${number.toLocaleString('id-ID')}`;
  }
}

export function formatNumber(value, maximumFractionDigits = 2) {
  const number = Number(value || 0);
  return new Intl.NumberFormat('id-ID', { maximumFractionDigits }).format(number);
}

export function formatQty(value) {
  const number = Number(value || 0);
  if (Number.isInteger(number)) return number.toLocaleString('id-ID');
  return new Intl.NumberFormat('id-ID', { maximumFractionDigits: 3 }).format(number);
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: DEFAULT_TZ,
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: DEFAULT_TZ,
    dateStyle: 'medium',
  }).format(date);
}

export function relativeTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const diff = Date.now() - date.getTime();
  const minutes = Math.round(diff / 60000);
  if (Math.abs(minutes) < 1) return 'just now';
  if (Math.abs(minutes) < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 30) return `${days}d ago`;
  return formatDate(value);
}

export function titleCase(value) {
  if (!value) return '';
  return String(value)
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function initials(name, email) {
  const source = name || email || '';
  return source
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('');
}
