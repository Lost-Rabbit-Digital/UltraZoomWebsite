// Minimal Google Sheets client for the lead-discovery workflow.
//
// Auth: service-account JWT via google-auth-library. The SA JSON key is
// passed in as a string (GOOGLE_SHEETS_SA_KEY env var, raw JSON).
//
// Only two operations:
//   - readColumn(range)   → read a single column, for URL dedup
//   - appendRows(rows)    → append rows to the first sheet tab

import { JWT } from "google-auth-library";
import { pickTemplate } from "./template-picker.mjs";

const SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets";
const SCOPE = "https://www.googleapis.com/auth/spreadsheets";

export const SHEET_TAB = "Leads";

// Column order is append-only. New columns always go at the end so that
// existing Sheets can be extended in place without reshuffling data — see
// ensureHeader for the drift handling.
export const SHEET_COLUMNS = [
  "found_at",
  "source",
  "seed",
  "title",
  "url",
  "domain",
  "published_date",
  "summary",
  "status",
  "template",
  "contact_url",
  "assigned_to",
  "message_sent",
  "reply",
  "notes",
  "author",
  "message_draft",
];

export const URL_COLUMN_INDEX = SHEET_COLUMNS.indexOf("url"); // 4 → column E

function columnLetter(i) {
  // 0 → A, 25 → Z, 26 → AA
  let s = "";
  let n = i;
  do {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return s;
}

export function makeClient({ saKeyJson, sheetId }) {
  let creds;
  try {
    creds = typeof saKeyJson === "string" ? JSON.parse(saKeyJson) : saKeyJson;
  } catch (e) {
    throw new Error("GOOGLE_SHEETS_SA_KEY is not valid JSON: " + e.message);
  }
  if (!creds.client_email || !creds.private_key) {
    throw new Error("service account JSON missing client_email or private_key");
  }
  if (!sheetId) throw new Error("sheetId required (LEADS_SHEET_ID env var)");

  const jwt = new JWT({
    email: creds.client_email,
    key: creds.private_key,
    scopes: [SCOPE],
  });

  async function authHeaders() {
    const { token } = await jwt.getAccessToken();
    return { authorization: `Bearer ${token}` };
  }

  async function ensureHeader() {
    // Read row 1. If it's shorter than the target schema, extend it by
    // appending the missing columns — existing data is untouched. We don't
    // rename or reorder columns the human may have customized.
    const range = `${SHEET_TAB}!A1:${columnLetter(SHEET_COLUMNS.length - 1)}1`;
    const url = `${SHEETS_BASE}/${sheetId}/values/${encodeURIComponent(range)}`;
    const res = await fetch(url, { headers: await authHeaders() });
    if (!res.ok) throw new Error(`sheets read header ${res.status}: ${await res.text()}`);
    const json = await res.json();
    const firstRow = json.values?.[0] || [];
    if (firstRow.length >= SHEET_COLUMNS.length) return;
    const target = [...firstRow];
    while (target.length < SHEET_COLUMNS.length) target.push(SHEET_COLUMNS[target.length]);
    const putUrl = `${SHEETS_BASE}/${sheetId}/values/${encodeURIComponent(range)}?valueInputOption=RAW`;
    const put = await fetch(putUrl, {
      method: "PUT",
      headers: { ...(await authHeaders()), "content-type": "application/json" },
      body: JSON.stringify({ values: [target] }),
    });
    if (!put.ok) throw new Error(`sheets write header ${put.status}: ${await put.text()}`);
  }

  async function readUrls() {
    const col = columnLetter(URL_COLUMN_INDEX);
    const range = `${SHEET_TAB}!${col}2:${col}`;
    const url = `${SHEETS_BASE}/${sheetId}/values/${encodeURIComponent(range)}`;
    const res = await fetch(url, { headers: await authHeaders() });
    if (!res.ok) throw new Error(`sheets readUrls ${res.status}: ${await res.text()}`);
    const json = await res.json();
    return new Set((json.values || []).map((r) => r[0]).filter(Boolean));
  }

  async function appendRows(rows) {
    if (rows.length === 0) return 0;
    const range = `${SHEET_TAB}!A1`;
    const url =
      `${SHEETS_BASE}/${sheetId}/values/${encodeURIComponent(range)}:append` +
      `?valueInputOption=RAW&insertDataOption=INSERT_ROWS`;
    const res = await fetch(url, {
      method: "POST",
      headers: { ...(await authHeaders()), "content-type": "application/json" },
      body: JSON.stringify({ values: rows }),
    });
    if (!res.ok) throw new Error(`sheets append ${res.status}: ${await res.text()}`);
    return rows.length;
  }

  return { ensureHeader, readUrls, appendRows };
}

export function rowFromResult(result, { source, seed, foundAt }) {
  // Match SHEET_COLUMNS order. `template` and `message_draft` are pre-filled
  // from the keyword picker so triage starts with a copy-paste-ready message;
  // humans override as needed. Other human columns (status onward) stay blank.
  const { templateId, draft } = pickTemplate(result);
  return [
    foundAt,
    source,
    seed,
    result.title,
    result.url,
    result.domain,
    result.published_date || "",
    result.summary,
    "new", // status
    templateId, // template
    "", // contact_url
    "", // assigned_to
    "", // message_sent
    "", // reply
    "", // notes
    result.author || "", // author
    draft, // message_draft
  ];
}
