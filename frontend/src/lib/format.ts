/**
 * Shared formatting helpers. All usage windows are IST, so dates are bucketed
 * in IST to match the backend quota counters and the bot.
 */

const IST_OFFSET_MINUTES = 330;

export function fmtLimit(value?: number | null): string {
  if (value === null || value === undefined) return '—';
  return value === -1 ? '∞' : value.toLocaleString('en-IN');
}

export function fmtTokens(value?: number | null): string {
  if (!value && value !== 0) return '—';
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  return String(value);
}

export function fmtRupees(amount?: number | null): string {
  if (amount === null || amount === undefined) return '—';
  if (amount === 0) return 'Free';
  return `₹${amount.toLocaleString('en-IN')}`;
}

export function pct(used: number, limit: number): number {
  if (!limit || limit === -1) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

/** IST calendar date (yyyy-mm-dd) for a UTC timestamp. */
export function istDayKey(value: string | Date | number): string {
  const date = value instanceof Date ? value : new Date(value);
  const ist = new Date(date.getTime() + IST_OFFSET_MINUTES * 60_000);
  return ist.toISOString().slice(0, 10);
}

export function fmtDateTime(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  const ist = new Date(date.getTime() + IST_OFFSET_MINUTES * 60_000);
  return ist.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    timeZone: 'UTC',
  });
}

export function fmtRelative(value?: string | null): string {
  if (!value) return '';
  const diff = Date.now() - new Date(value).getTime();
  const mins = Math.round(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

/** Buckets conversations by activity date. */
export function groupByRecency<T>(items: T[], activityOf: (item: T) => string): {
  label: string;
  items: T[];
}[] {
  const today = istDayKey(new Date());
  const yesterday = istDayKey(Date.now() - 86_400_000);
  const weekAgo = Date.now() - 7 * 86_400_000;

  const buckets: Record<string, T[]> = { Today: [], Yesterday: [], 'Previous 7 days': [], Older: [] };

  for (const item of items) {
    const activity = activityOf(item);
    const key = istDayKey(activity);
    if (key === today) buckets.Today.push(item);
    else if (key === yesterday) buckets.Yesterday.push(item);
    else if (new Date(activity).getTime() >= weekAgo) buckets['Previous 7 days'].push(item);
    else buckets.Older.push(item);
  }

  return Object.entries(buckets)
    .filter(([, list]) => list.length > 0)
    .map(([label, list]) => ({ label, items: list }));
}
