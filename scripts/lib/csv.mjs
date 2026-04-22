// Local CSV sink that mirrors the Google Sheets client shape
// ({ ensureHeader, readUrls, appendRows }). Useful for smoke-testing the
// full discovery + contact-probe pipeline before the Sheets integration
// is wired up, or for one-off local runs.
//
// Dedup behavior matches the Sheet: we read the URL column from the file
// on startup and skip any result whose URL is already present. Header is
// written once on first run.
//
// The parser below walks the whole file with a single state machine so it
// correctly handles fields that contain embedded newlines (e.g.
// `message_draft` with paragraph breaks). Quoted cells preserve any
// whitespace or commas verbatim.

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

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"' && text[i + 1] === '"') {
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
      row.push(cur);
      cur = "";
    } else if (c === "\n" || c === "\r") {
      // Skip \r in \r\n line endings
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cur);
      rows.push(row);
      row = [];
      cur = "";
    } else {
      cur += c;
    }
  }
  if (cur.length > 0 || row.length > 0) {
    row.push(cur);
    rows.push(row);
  }
  return rows;
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
    const rows = parseCsv(readFileSync(path, "utf8"));
    for (let i = 1; i < rows.length; i++) {
      const u = rows[i][URL_COLUMN_INDEX];
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
