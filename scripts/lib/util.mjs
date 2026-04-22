// Shared helpers for the lead pipeline.

// Coerce provider-reported publish dates to a uniform YYYY-MM-DD string.
// Exa returns ISO-8601 already; Brave's page_age can be ISO, a long-form
// date ("September 1, 2024"), or a relative phrase ("3 days ago"). When
// the input is unparseable we return "" so downstream code can treat it
// the same as "no date".
export function toIsoDate(value) {
  if (!value) return "";
  const s = String(value).trim();
  if (!s) return "";

  const isoPrefix = s.match(/^(\d{4}-\d{2}-\d{2})/);
  if (isoPrefix) return isoPrefix[1];

  const rel = s.match(/^(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago$/i);
  if (rel) {
    const n = Number(rel[1]);
    const unit = rel[2].toLowerCase();
    const d = new Date();
    if (unit === "second") d.setSeconds(d.getSeconds() - n);
    else if (unit === "minute") d.setMinutes(d.getMinutes() - n);
    else if (unit === "hour") d.setHours(d.getHours() - n);
    else if (unit === "day") d.setDate(d.getDate() - n);
    else if (unit === "week") d.setDate(d.getDate() - n * 7);
    else if (unit === "month") d.setMonth(d.getMonth() - n);
    else if (unit === "year") d.setFullYear(d.getFullYear() - n);
    return d.toISOString().slice(0, 10);
  }

  const parsed = new Date(s);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return "";
}
