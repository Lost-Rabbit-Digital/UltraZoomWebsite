// Local CSV sink that mirrors the Google Sheets client shape
// ({ ensureHeader, readUrls, appendRows }). Useful for smoke-testing the
// full discovery + contact-probe pipeline before the Sheets integration
// is wired up, or for one-off local runs.
//
// Dedup behavior matches the Sheet: we read the URL column from the file
// on startup and skip any result whose URL is already present. Header is
// written once on first run.
//
// Safe assumption about content: the provider normalizers collapse all
// whitespace in `summary` to single spaces before trimming, so no field
// we write contains embedded newlines. The parser therefore treats each
// file line as one row.

import { existsSync, readFileSync, appendFileSync, writeFileSync } from "node:fs";
import { SHEET_COLUMNS, URL_COLUMN_INDEX } from "./sheets.mjs";

function escape(v) {
  const s = v == null ? "" : String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function toLine(cols) {
  return cols.map(escape).join(",") + "\n";
}

function parseLine(line) {
  const out = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQ) {
      if (c === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
      } else if (c === '"') {
        inQ = false;
      } else {
        cur += c;
      }
    } else if (c === '"') {
      inQ = true;
    } else if (c === ",") {
      out.push(cur);
      cur = "";
    } else {
      cur += c;
    }
  }
  out.push(cur);
  return out;
}

export function makeCsvClient({ path }) {
  async function ensureHeader() {
    if (!existsSync(path)) {
      writeFileSync(path, toLine(SHEET_COLUMNS));
    }
  }

  async function readUrls() {
    const seen = new Set();
    if (!existsSync(path)) return seen;
    const text = readFileSync(path, "utf8");
    const lines = text.split(/\r?\n/);
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i]) continue;
      const cols = parseLine(lines[i]);
      const u = cols[URL_COLUMN_INDEX];
      if (u) seen.add(u);
    }
    return seen;
  }

  async function appendRows(rows) {
    if (rows.length === 0) return 0;
    let buf = "";
    for (const row of rows) buf += toLine(row);
    appendFileSync(path, buf);
    return rows.length;
  }

  return { ensureHeader, readUrls, appendRows };
}
