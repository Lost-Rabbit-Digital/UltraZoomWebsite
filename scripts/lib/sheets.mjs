// Minimal Google Sheets client for the lead-discovery workflow.
//
// Auth: Application Default Credentials via google-auth-library. In CI,
// google-github-actions/auth@v2 exchanges the workflow's OIDC token for a
// short-lived service-account credential and points GOOGLE_APPLICATION_-
// CREDENTIALS at the credential file. Locally, run
// `gcloud auth application-default login` once and ADC will pick up your
// user credentials.
//
// Only two operations:
//   - readColumn(range)   → read a single column, for URL dedup
//   - appendRows(rows)    → append rows to the first sheet tab

import { GoogleAuth } from "google-auth-library";

const SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets";
const SCOPE = "https://www.googleapis.com/auth/spreadsheets";

export const SHEET_TAB = "Leads";

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

export function makeClient({ sheetId }) {
  if (!sheetId) throw new Error("sheetId required (LEADS_SHEET_ID env var)");

  const auth = new GoogleAuth({ scopes: [SCOPE] });

  async function authHeaders() {
    const token = await auth.getAccessToken();
    if (!token) {
      throw new Error(
        "no Google credentials found. In CI, confirm the google-github-" +
          "actions/auth step ran. Locally, run `gcloud auth application-" +
          "default login`.",
      );
    }
    return { authorization: `Bearer ${token}` };
  }

  async function ensureHeader() {
    // Read row 1; if it's empty, write the header.
    const range = `${SHEET_TAB}!A1:${columnLetter(SHEET_COLUMNS.length - 1)}1`;
    const url = `${SHEETS_BASE}/${sheetId}/values/${encodeURIComponent(range)}`;
    const res = await fetch(url, { headers: await authHeaders() });
    if (!res.ok) throw new Error(`sheets read header ${res.status}: ${await res.text()}`);
    const json = await res.json();
    const firstRow = json.values?.[0] || [];
    if (firstRow.length >= SHEET_COLUMNS.length) return;
    const putUrl = `${SHEETS_BASE}/${sheetId}/values/${encodeURIComponent(range)}?valueInputOption=RAW`;
    const put = await fetch(putUrl, {
      method: "PUT",
      headers: { ...(await authHeaders()), "content-type": "application/json" },
      body: JSON.stringify({ values: [SHEET_COLUMNS] }),
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
  // Match SHEET_COLUMNS order. Human columns (status onward) left blank.
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
    "", // template
    "", // contact_url
    "", // assigned_to
    "", // message_sent
    "", // reply
    "", // notes
  ];
}
