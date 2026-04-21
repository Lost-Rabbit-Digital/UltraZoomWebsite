#!/usr/bin/env node
/*
 * find-leads.mjs — Exa-powered lead discovery for the contact-form outreach lane.
 *
 * Two modes:
 *   search        Runs natural-language queries from docs/outreach/exa-queries.md
 *                 against Exa's /search endpoint.
 *   find-similar  Reads seed URLs from docs/outreach/leads.json (and optional
 *                 --seeds <file>) and asks Exa's /findSimilar for more of the
 *                 same shape. This is the force-multiplier — 30 curated leads
 *                 can surface 300+ similar articles.
 *
 * Results are appended to a Google Sheet (dedup by URL before append) so
 * humans can edit status/template/assigned_to columns without the script
 * stomping their edits on the next run.
 *
 * Required env vars:
 *   EXA_API_KEY           — Exa API key
 *   GOOGLE_SHEETS_SA_KEY  — service-account JSON (raw string, see sheets-setup.md)
 *   LEADS_SHEET_ID        — target Google Sheet ID (from its URL)
 *
 * See docs/outreach/sheets-setup.md for a one-time service-account setup.
 *
 * Usage:
 *   node scripts/find-leads.mjs --mode search --limit 20
 *   node scripts/find-leads.mjs --mode find-similar --limit 30
 *   node scripts/find-leads.mjs --mode both --limit 20
 *   node scripts/find-leads.mjs --mode search --dry-run      (preview queries)
 *
 * Options:
 *   --mode <m>         search | find-similar | both   (default: both)
 *   --limit <n>        max queries/seeds per mode     (default: 20)
 *   --per-query <n>    results per Exa call           (default: 10, max 25)
 *   --queries <file>   override for NL query file     (default: docs/outreach/exa-queries.md)
 *   --seeds <file>     override for seed URL source   (default: docs/outreach/leads.json)
 *   --sections <re>    regex filter on query sections
 *   --since <iso>      filter to pages published after this date (YYYY-MM-DD)
 *   --dry-run          print what would run, skip API + Sheet calls
 */

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { argv, env, exit } from "node:process";

import { search as exaSearch, findSimilar as exaFindSimilar } from "./lib/exa.mjs";
import { makeClient, rowFromResult } from "./lib/sheets.mjs";

const DEFAULT_QUERIES = "docs/outreach/exa-queries.md";
const DEFAULT_SEEDS = "docs/outreach/leads.json";

function parseArgs(raw) {
  const out = {
    mode: "both",
    limit: 20,
    perQuery: 10,
    queries: DEFAULT_QUERIES,
    seeds: DEFAULT_SEEDS,
    sections: null,
    since: null,
    dryRun: false,
  };
  for (let i = 2; i < raw.length; i++) {
    const a = raw[i];
    const next = () => raw[++i];
    if (a === "--mode") out.mode = next();
    else if (a === "--limit") out.limit = Number(next());
    else if (a === "--per-query") out.perQuery = Math.min(25, Number(next()));
    else if (a === "--queries") out.queries = next();
    else if (a === "--seeds") out.seeds = next();
    else if (a === "--sections") out.sections = new RegExp(next(), "i");
    else if (a === "--since") out.since = next();
    else if (a === "--dry-run") out.dryRun = true;
    else if (a === "-h" || a === "--help") {
      console.log(readFileSync(new URL(import.meta.url), "utf8").split("*/")[0]);
      exit(0);
    } else {
      console.error(`unknown arg: ${a}`);
      exit(2);
    }
  }
  if (!["search", "find-similar", "both"].includes(out.mode)) {
    console.error(`--mode must be search, find-similar, or both`);
    exit(2);
  }
  return out;
}

// Parse docs/outreach/exa-queries.md. Format: H2 section headings, with
// markdown bullet points (- or *) as individual queries. Lines that start
// with `>` (blockquote) are treated as notes and skipped.
function parseQueries(path, sectionFilter) {
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n");
  const out = [];
  let currentSection = "uncategorized";
  for (const line of lines) {
    if (line.startsWith("## ")) {
      currentSection = line.replace(/^##+\s*/, "").trim();
      continue;
    }
    const m = line.match(/^\s*[-*]\s+"?(.+?)"?\s*$/);
    if (!m) continue;
    const q = m[1].replace(/\\"/g, '"').trim();
    if (!q || q.startsWith("TODO") || q.startsWith("#")) continue;
    if (sectionFilter && !sectionFilter.test(currentSection)) continue;
    out.push({ section: currentSection, query: q });
  }
  return out;
}

function loadSeedUrls(path) {
  if (!existsSync(path)) return [];
  const text = readFileSync(path, "utf8");
  try {
    const data = JSON.parse(text);
    const leads = Array.isArray(data) ? data : data.leads || [];
    return leads
      .map((l) => l.article_url || l.url)
      .filter((u) => typeof u === "string" && u.startsWith("http"));
  } catch (e) {
    console.error(`could not parse seeds file ${path}: ${e.message}`);
    return [];
  }
}

async function runSearchMode({ queries, perQuery, since, apiKey, sheet, seen, dryRun }) {
  console.error(`\n== search mode (${queries.length} queries) ==`);
  const rows = [];
  for (const { section, query } of queries) {
    if (dryRun) {
      console.error(`  [dry] [${section}] ${query}`);
      continue;
    }
    let items;
    try {
      items = await exaSearch({
        apiKey,
        query,
        numResults: perQuery,
        startPublishedDate: since || undefined,
      });
    } catch (e) {
      console.error(`  ! ${query.slice(0, 60)} — ${e.message}`);
      continue;
    }
    const kept = collect({
      items,
      source: "exa-search",
      seed: query,
      seen,
      rows,
    });
    console.error(`  + [${kept}/${items.length}]  ${query.slice(0, 70)}`);
  }
  if (!dryRun && rows.length) await sheet.appendRows(rows);
  return rows.length;
}

async function runFindSimilarMode({ seeds, perQuery, apiKey, sheet, seen, dryRun }) {
  console.error(`\n== find-similar mode (${seeds.length} seed URLs) ==`);
  const rows = [];
  for (const seedUrl of seeds) {
    if (dryRun) {
      console.error(`  [dry] similar-to: ${seedUrl}`);
      continue;
    }
    let items;
    try {
      items = await exaFindSimilar({ apiKey, url: seedUrl, numResults: perQuery });
    } catch (e) {
      console.error(`  ! ${seedUrl.slice(0, 60)} — ${e.message}`);
      continue;
    }
    const kept = collect({
      items,
      source: "exa-similar",
      seed: seedUrl,
      seen,
      rows,
    });
    console.error(`  + [${kept}/${items.length}]  ${seedUrl.slice(0, 70)}`);
  }
  if (!dryRun && rows.length) await sheet.appendRows(rows);
  return rows.length;
}

function collect({ items, source, seed, seen, rows }) {
  const foundAt = new Date().toISOString().slice(0, 10);
  let kept = 0;
  for (const it of items) {
    if (!it.url || seen.has(it.url)) continue;
    seen.add(it.url);
    rows.push(rowFromResult(it, { source, seed, foundAt }));
    kept++;
  }
  return kept;
}

async function main() {
  const opts = parseArgs(argv);
  const apiKey = env.EXA_API_KEY;
  const saKeyJson = env.GOOGLE_SHEETS_SA_KEY;
  const sheetId = env.LEADS_SHEET_ID;

  if (!opts.dryRun) {
    const missing = [];
    if (!apiKey) missing.push("EXA_API_KEY");
    if (!saKeyJson) missing.push("GOOGLE_SHEETS_SA_KEY");
    if (!sheetId) missing.push("LEADS_SHEET_ID");
    if (missing.length) {
      console.error(`error: missing env vars: ${missing.join(", ")}`);
      console.error(`       (or re-run with --dry-run to preview)`);
      exit(1);
    }
  }

  const queries = parseQueries(resolve(opts.queries), opts.sections).slice(0, opts.limit);
  const seeds = loadSeedUrls(resolve(opts.seeds)).slice(0, opts.limit);

  console.error(`mode: ${opts.mode}`);
  console.error(`queries available: ${queries.length}  seeds available: ${seeds.length}`);

  if (opts.dryRun) {
    if (opts.mode !== "find-similar") await runSearchMode({ queries, ...stub(opts) });
    if (opts.mode !== "search") await runFindSimilarMode({ seeds, ...stub(opts) });
    return;
  }

  const sheet = makeClient({ saKeyJson, sheetId });
  await sheet.ensureHeader();
  const seen = await sheet.readUrls();
  console.error(`existing URLs in sheet: ${seen.size}`);

  let appended = 0;
  if (opts.mode !== "find-similar") {
    appended += await runSearchMode({
      queries,
      perQuery: opts.perQuery,
      since: opts.since,
      apiKey,
      sheet,
      seen,
      dryRun: false,
    });
  }
  if (opts.mode !== "search") {
    appended += await runFindSimilarMode({
      seeds,
      perQuery: opts.perQuery,
      apiKey,
      sheet,
      seen,
      dryRun: false,
    });
  }

  console.error(`\ndone. appended ${appended} new rows.`);
}

function stub(opts) {
  return {
    perQuery: opts.perQuery,
    since: opts.since,
    apiKey: null,
    sheet: null,
    seen: new Set(),
    dryRun: true,
  };
}

main().catch((e) => {
  console.error(e.stack || e.message);
  exit(1);
});
