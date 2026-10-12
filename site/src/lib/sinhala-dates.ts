// Sinhala date formatting with fixed month and weekday names.
// Intl.DateTimeFormat("si-LK") is not stable across ICU versions: newer
// releases print the traditional lunar month (වප්) instead of ඔක්තෝබර්, and
// some browsers have no Sinhala data at all. Kept free of other imports so the
// search page's browser script can use it without pulling in the site data.

export const SINHALA_MONTHS = [
  "ජනවාරි",
  "පෙබරවාරි",
  "මාර්තු",
  "අප්‍රේල්",
  "මැයි",
  "ජූනි",
  "ජූලි",
  "අගෝස්තු",
  "සැප්තැම්බර්",
  "ඔක්තෝබර්",
  "නොවැම්බර්",
  "දෙසැම්බර්",
];

export const SINHALA_WEEKDAYS = ["ඉරිදා", "සඳුදා", "අඟහරුවාදා", "බදාදා", "බ්‍රහස්පතින්දා", "සිකුරාදා", "සෙනසුරාදා"];

function parts(isoDate: string): [number, number, number] {
  const [year, month, day] = isoDate.split("-").map(Number);
  return [year, month, day];
}

/** "2026-10-11" -> "2026 ඔක්තෝබර් 11" */
export function formatLongDate(isoDate: string): string {
  const [year, month, day] = parts(isoDate);
  return `${year} ${SINHALA_MONTHS[month - 1]} ${day}`;
}

/** "2026-10-11" -> "ඉරිදා" */
export function formatWeekday(isoDate: string): string {
  const [year, month, day] = parts(isoDate);
  return SINHALA_WEEKDAYS[new Date(Date.UTC(year, month - 1, day)).getUTCDay()];
}

/** "2026-10-11" -> "2026 ඔක්තෝබර් 11, ඉරිදා" */
export function formatDate(isoDate: string): string {
  return `${formatLongDate(isoDate)}, ${formatWeekday(isoDate)}`;
}
