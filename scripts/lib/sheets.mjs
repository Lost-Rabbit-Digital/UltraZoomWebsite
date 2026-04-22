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
import { pickTemplate as defaultPickTemplate } from "./template-picker.mjs";

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
  "contact_email",
  "contact_method",
  "last_checked_at",
  "personalization_hook",
  "lead_score",
  "priority",
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

// Pull a short, copy-paste-ready hook out of the article summary the human
// can drop into the first sentence of an outreach message. We grab the
// first complete sentence with some signal-bearing words; if nothing
// matches we just take the first sentence outright. Falls back to "" so
// the column is always written.
function personalizationHook(result) {
  const text = (result.summary || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const sentences = text.split(/(?<=[.!?])\s+/).filter((s) => s.length >= 30 && s.length <= 220);
  if (sentences.length === 0) {
    return text.length <= 200 ? text : text.slice(0, 197) + "…";
  }
  const SIGNAL = /\b(extension|browser|chrome|firefox|hover|zoom|image|photo|tool|recommend|favorite|use|workflow)\b/i;
  const ranked = sentences.find((s) => SIGNAL.test(s)) || sentences[0];
  return ranked;
}

// Composite lead-score in [0, 100]. Combines Exa's neural-similarity
// score with freshness and a small bonus for a known author. Designed
// for sorting, not statistics — the human just wants top-N per day.
function leadScore(result) {
  let score = 0;
  if (typeof result.score === "number") {
    // Exa scores cluster around 0.1-0.5 for good results.
    score += Math.min(60, Math.round(result.score * 120));
  } else {
    score += 30; // Brave doesn't return a score; assume midrange.
  }
  if (result.published_date) {
    const ageDays =
      (Date.now() - new Date(result.published_date).getTime()) / 86_400_000;
    if (Number.isFinite(ageDays)) {
      if (ageDays < 90) score += 25;
      else if (ageDays < 365) score += 15;
      else if (ageDays < 730) score += 5;
    }
  }
  if (result.author) score += 5;
  return Math.max(0, Math.min(100, score));
}

export function rowFromResult(result, { source, seed, foundAt, pickTemplate = defaultPickTemplate }) {
  // Match SHEET_COLUMNS order. `template` and `message_draft` are pre-filled
  // from the keyword picker so triage starts with a copy-paste-ready message;
  // humans override as needed. Other human columns (status onward) stay blank.
  //
  // `pickTemplate` is injectable so additional outreach lanes (e.g. the
  // HailBytes PoC in find-leads-hailbytes.mjs) can plug in their own picker
  // without forking this module.
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
    "", // contact_url — filled by enrichment
    "", // assigned_to
    "", // message_sent
    "", // reply
    "", // notes
    result.author || "", // author
    draft, // message_draft
    "", // contact_email — filled by enrichment
    "", // contact_method — filled by enrichment ("form" | "email" | "")
    "", // last_checked_at — filled when we probe contact info
    personalizationHook(result),
    String(leadScore(result)),
    "", // priority — human-assigned
  ];
}
