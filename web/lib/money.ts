const DOLLARS = /^\d+(\.\d{1,2})?$/;

/** Whole cents from a typed dollar amount, or null when it is not a plain positive amount. */
export function parseDollarsToCents(text: string): number | null {
  const trimmed = text.trim();
  if (!DOLLARS.test(trimmed)) return null;
  const cents = Math.round(Number(trimmed) * 100);
  return cents > 0 ? cents : null;
}
