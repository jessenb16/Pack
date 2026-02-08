/**
 * Parse a YYYY-MM-DD string as a local calendar date.
 * Avoids JS treating "2024-10-13" as UTC midnight, which shows as the previous day in western timezones.
 */
export function parseLocalDate(dateStr: string): Date | null {
  if (!dateStr || typeof dateStr !== 'string') return null;
  const parts = dateStr.trim().split('-').map(Number);
  if (parts.length !== 3 || parts.some((n) => Number.isNaN(n))) return null;
  const [y, m, d] = parts;
  const date = new Date(y, m - 1, d);
  if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d) return null;
  return date;
}

/** Format doc_date (YYYY-MM-DD) for display in the user's locale. */
export function formatDocDate(dateStr: string): string {
  const date = parseLocalDate(dateStr);
  return date ? date.toLocaleDateString() : dateStr || '—';
}
