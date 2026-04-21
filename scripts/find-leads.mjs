#!/usr/bin/env node
/*
 * find-leads.mjs — pluggable lead discovery for the contact-form outreach lane.
 *
 * Two search providers are supported:
 *   exa    — neural search; uses NL prompts from docs/outreach/exa-queries.md
 *            and can also run /findSimilar against seed URLs in leads.json.
 *   brave  — keyword search with Google-style operators; uses the existing
 *            dork library in docs/outreach/dorks.md.
 *
 * Both write to the same Google Sheet, distinguished by the `source` column
 * (exa-search, exa-similar, brave-search). Dedup by URL is global across
 * providers, so you never get duplicate rows regardless of who found the
 * article first.
 *
 * After Exa/Brave returns results, each row is enriched with a best-effort
 * contact_url probe (HTTP HEAD/GET against common contact paths). Detection
 * runs with a per-URL budget so slow sites can't blow the Action timeout.
 *
 * Required env vars by provider:
 *   common: GOOGLE_SHEETS_SA_KEY, LEADS_SHEET_ID
 *   exa:    EXA_API_KEY
 *   brave:  BRAVE_SEARCH_KEY
 *
 * Usage:
 *   node scripts/find-leads.mjs --provider exa --mode both --limit 20
 *   node scripts/find-leads.mjs --provider brave --limit 20
 *   node scripts/find-leads.mjs --provider exa --dry-run
 *
 * Options:
 *   --provider <p>     exa | brave                    (default: exa)
 *   --mode <m>         search | find-similar | both   (exa only; default: both)
 *   --limit <n>        max queries/seeds per mode     (default: 20)
 *   --per-query <n>    results per call (1–25)        (default: 10)
 *   --queries <file>   override query file            (default depends on provider)
 *   --seeds <file>     override seeds file (Exa only) (default: docs/outreach/leads.json)
 *   --sections <re>    regex filter on section headings
 *   --since <iso>      pages/results after this date (YYYY-MM-DD)
 *   --no-detect        skip contact_url auto-detection
 *   --csv <path>       write to a local CSV file instead of Google Sheets
 *                      (useful for smoke-testing before Sheets is set up)
 *   --dry-run          preview queries, no API or Sheet calls
 */

import { readFileSync, existsSync, appendFileSync } from "node:fs";
import { resolve } from "node:path";
import { argv, env, exit } from "node:process";

import { search as exaSearch, findSimilar as exaFindSimilar } from "./lib/exa.mjs";
import { search as braveSearch } from "./lib/brave.mjs";
import { makeClient, rowFromResult, SHEET_COLUMNS } from "./lib/sheets.mjs";
import { makeCsvClient } from "./lib/csv.mjs";
import { enrichWithContactUrls } from "./lib/contact-form.mjs";

const DEFAULTS = {
  exa: { queries: "docs/outreach/exa-queries.md", seeds: "docs/outreach/leads.json" },
  brave: { queries: "docs/outreach/dorks.md" },
};

function parseArgs(raw) {
  const out = {
    provider: "exa",
    mode: "both",
    limit: 20,
    perQuery: 10,
    queries: null,
    seeds: DEFAULTS.exa.seeds,
    sections: null,
    since: null,
    detect: true,
    csv: null,
    dryRun: false,
  };
  for (let i = 2; i < raw.length; i++) {
    const a = raw[i];
    const next = () => raw[++i];
    if (a === "--provider") out.provider = next();
    else if (a === "--mode") out.mode = next();
    else if (a === "--limit") out.limit = Number(next());
    else if (a === "--per-query") out.perQuery = Math.min(25, Number(next()));
    else if (a === "--queries") out.queries = next();
    else if (a === "--seeds") out.seeds = next();
    else if (a === "--sections") out.sections = new RegExp(next(), "i");
    else if (a === "--since") out.since = next();
    else if (a === "--no-detect") out.detect = false;
    else if (a === "--csv") out.csv = next();
    else if (a === "--dry-run") out.dryRun = true;
    else if (a === "-h" || a === "--help") {
      console.log(readFileSync(new URL(import.meta.url), "utf8").split("*/")[0]);
      exit(0);
    } else {
      console.error(`unknown arg: ${a}`);
      exit(2);
    }
  }
  if (!["exa", "brave"].includes(out.provider)) {
    console.error(`--provider must be exa or brave`);
    exit(2);
  }
  if (!["search", "find-similar", "both"].includes(out.mode)) {
    console.error(`--mode must be search, find-similar, or both`);
    exit(2);
  }
  if (!out.queries) out.queries = DEFAULTS[out.provider].queries;
  return out;
}

// Natural-language query parser: H2 sections, `-` bullets, strip quotes.
// Used by Exa (exa-queries.md). Bullets before the first H2 are treated as
// intro/notes and ignored.
function parseNlQueries(path, sectionFilter) {
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n");
  const out = [];
  let section = null;
  for (const line of lines) {
    if (line.startsWith("## ")) {
      section = line.replace(/^##+\s*/, "").trim();
      continue;
    }
    if (!section) continue;
    const m = line.match(/^\s*[-*]\s+"?(.+?)"?\s*$/);
    if (!m) continue;
    const q = m[1].replace(/\\"/g, '"').trim();
    if (!q || q.startsWith("TODO") || q.startsWith("#")) continue;
    if (sectionFilter && !sectionFilter.test(section)) continue;
    out.push({ section, query: q });
  }
  return out;
}

// Dork parser: H2 sections, queries inside ``` fenced blocks, one per line.
// Used by Brave (dorks.md). `YEAR` tokens are replaced with the current year
// so section 1 templates stay runnable; lines with other placeholders
// (NICHE, BLOG_SPEAR, SUBREDDIT) are skipped as truly templated.
function parseDorkQueries(path, sectionFilter) {
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n");
  const out = [];
  const CURRENT_YEAR = String(new Date().getFullYear());
  let section = "uncategorized";
  let inFence = false;
  for (const line of lines) {
    if (line.startsWith("## ")) {
      section = line.replace(/^##+\s*/, "").trim();
      inFence = false;
      continue;
    }
    if (line.startsWith("### ")) {
      const sub = line.replace(/^#+\s*/, "").trim();
      section = section.split(" — ")[0] + " — " + sub;
      continue;
    }
    if (line.trim().startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (!inFence) continue;
    let q = line.trim();
    if (!q || q.startsWith("#") || q.startsWith("//")) continue;
    q = q.replace(/\bYEAR\b/g, CURRENT_YEAR);
    // After YEAR substitution, skip anything still templated.
    if (/\b(NICHE|BLOG_SPEAR|SUBREDDIT)\b/.test(q)) continue;
    if (sectionFilter && !sectionFilter.test(section)) continue;
    out.push({ section, query: q });
  }
  return out;
}

function loadSeedUrls(path) {
  if (!existsSync(path)) return [];
  try {
    const data = JSON.parse(readFileSync(path, "utf8"));
    const leads = Array.isArray(data) ? data : data.leads || [];
    return leads
      .map((l) => l.article_url || l.url)
      .filter((u) => typeof u === "string" && u.startsWith("http"));
  } catch (e) {
    console.error(`could not parse seeds file ${path}: ${e.message}`);
    return [];
  }
}

function collect({ items, source, seed, seen, rows }) {
  const foundAt = new Date().toISOString().slice(0, 10);
  let kept = 0;
  for (const it of items) {
    if (!it || !it.url || seen.has(it.url)) continue;
    seen.add(it.url);
    rows.push(rowFromResult(it, { source, seed, foundAt }));
    kept++;
  }
  return kept;
}

async function runExaSearch({ queries, perQuery, since, apiKey, seen, stats, dryRun }) {
  console.error(`\n== exa search (${queries.length} queries) ==`);
  const rows = [];
  for (const { section, query } of queries) {
    if (dryRun) {
      console.error(`  [dry] [${section}] ${query}`);
      continue;
    }
    stats.queries++;
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
      stats.errors++;
      continue;
    }
    const kept = collect({ items, source: "exa-search", seed: query, seen, rows });
    console.error(`  + [${kept}/${items.length}]  ${query.slice(0, 70)}`);
  }
  return rows;
}

async function runExaFindSimilar({ seeds, perQuery, apiKey, seen, stats, dryRun }) {
  console.error(`\n== exa find-similar (${seeds.length} seed URLs) ==`);
  const rows = [];
  for (const seedUrl of seeds) {
    if (dryRun) {
      console.error(`  [dry] similar-to: ${seedUrl}`);
      continue;
    }
    stats.seeds++;
    let items;
    try {
      items = await exaFindSimilar({ apiKey, url: seedUrl, numResults: perQuery });
    } catch (e) {
      console.error(`  ! ${seedUrl.slice(0, 60)} — ${e.message}`);
      stats.errors++;
      continue;
    }
    const kept = collect({ items, source: "exa-similar", seed: seedUrl, seen, rows });
    console.error(`  + [${kept}/${items.length}]  ${seedUrl.slice(0, 70)}`);
  }
  return rows;
}

async function runBraveSearch({ queries, perQuery, since, apiKey, seen, stats, dryRun }) {
  console.error(`\n== brave search (${queries.length} queries) ==`);
  const rows = [];
  for (const { section, query } of queries) {
    if (dryRun) {
      console.error(`  [dry] [${section}] ${query}`);
      continue;
    }
    stats.queries++;
    let items;
    try {
      items = await braveSearch({ apiKey, query, numResults: perQuery, since });
    } catch (e) {
      console.error(`  ! ${query.slice(0, 60)} — ${e.message}`);
      stats.errors++;
      continue;
    }
    const kept = collect({ items, source: "brave-search", seed: query, seen, rows });
    console.error(`  + [${kept}/${items.length}]  ${query.slice(0, 70)}`);
  }
  return rows;
}

async function enrichContactUrls(rows, dryRun) {
  if (dryRun || rows.length === 0) return 0;
  console.error(`\n== contact-form detection (${rows.length} rows) ==`);
  const tmpRows = rows.map((r) => ({
    url: r[SHEET_COLUMNS.indexOf("url")],
    contact_url: "",
  }));
  const detected = await enrichWithContactUrls(tmpRows);
  const idx = SHEET_COLUMNS.indexOf("contact_url");
  for (let i = 0; i < rows.length; i++) {
    if (tmpRows[i].contact_url) rows[i][idx] = tmpRows[i].contact_url;
  }
  console.error(`  detected ${detected}/${rows.length} contact URLs`);
  return detected;
}

function writeStepSummary({ provider, mode, stats, sheetId, csvPath }) {
  const path = env.GITHUB_STEP_SUMMARY;
  if (!path) return;
  const md = [
    `## Lead discovery — ${provider}`,
    ``,
    `| metric | value |`,
    `| --- | --- |`,
    `| provider | \`${provider}\` |`,
    `| mode | \`${mode}\` |`,
    `| sink | ${csvPath ? `CSV (\`${csvPath}\`)` : "Google Sheets"} |`,
    `| queries run | ${stats.queries} |`,
    `| seeds run | ${stats.seeds} |`,
    `| new rows appended | **${stats.appended}** |`,
    `| contact URLs detected | ${stats.contactDetected} |`,
    `| duplicates skipped | ${stats.duplicates} |`,
    `| API errors | ${stats.errors} |`,
    ``,
  ];
  if (sheetId) {
    md.push(`[Open the Sheet →](https://docs.google.com/spreadsheets/d/${sheetId})`);
  } else if (csvPath) {
    md.push(`Download the CSV from the **Artifacts** section at the top of this run.`);
  }
  appendFileSync(path, md.join("\n") + "\n");
}

async function main() {
  const opts = parseArgs(argv);
  const exaKey = env.EXA_API_KEY;
  const braveKey = env.BRAVE_SEARCH_KEY;
  const saKeyJson = env.GOOGLE_SHEETS_SA_KEY;
  const sheetId = env.LEADS_SHEET_ID;

  if (!opts.dryRun) {
    const missing = [];
    if (opts.provider === "exa" && !exaKey) missing.push("EXA_API_KEY");
    if (opts.provider === "brave" && !braveKey) missing.push("BRAVE_SEARCH_KEY");
    if (!opts.csv) {
      if (!saKeyJson) missing.push("GOOGLE_SHEETS_SA_KEY");
      if (!sheetId) missing.push("LEADS_SHEET_ID");
    }
    if (missing.length) {
      console.error(`error: missing env vars: ${missing.join(", ")}`);
      console.error(`       (re-run with --dry-run to preview without secrets,`);
      console.error(`        or --csv <path> to write locally instead of Sheets)`);
      exit(1);
    }
  }

  const parseQueries = opts.provider === "exa" ? parseNlQueries : parseDorkQueries;
  const queries = parseQueries(resolve(opts.queries), opts.sections).slice(0, opts.limit);
  const seeds = opts.provider === "exa"
    ? loadSeedUrls(resolve(opts.seeds)).slice(0, opts.limit)
    : [];

  console.error(`provider: ${opts.provider}  mode: ${opts.mode}`);
  console.error(`queries available: ${queries.length}  seeds available: ${seeds.length}`);
  if (opts.since) console.error(`since: ${opts.since}`);

  const stats = {
    queries: 0,
    seeds: 0,
    appended: 0,
    contactDetected: 0,
    duplicates: 0,
    errors: 0,
  };

  if (opts.dryRun) {
    if (opts.provider === "exa") {
      if (opts.mode !== "find-similar") await runExaSearch({ queries, ...stubArgs(opts, stats) });
      if (opts.mode !== "search") await runExaFindSimilar({ seeds, ...stubArgs(opts, stats) });
    } else {
      await runBraveSearch({ queries, ...stubArgs(opts, stats) });
    }
    return;
  }

  const sink = opts.csv
    ? makeCsvClient({ path: resolve(opts.csv) })
    : makeClient({ saKeyJson, sheetId });
  await sink.ensureHeader();
  const seen = await sink.readUrls();
  const seenBefore = seen.size;
  console.error(
    opts.csv
      ? `csv sink: ${opts.csv}  existing URLs: ${seenBefore}`
      : `existing URLs in sheet: ${seenBefore}`,
  );

  const allRows = [];
  if (opts.provider === "exa") {
    if (opts.mode !== "find-similar") {
      allRows.push(
        ...(await runExaSearch({
          queries,
          perQuery: opts.perQuery,
          since: opts.since,
          apiKey: exaKey,
          seen,
          stats,
          dryRun: false,
        })),
      );
    }
    if (opts.mode !== "search") {
      allRows.push(
        ...(await runExaFindSimilar({
          seeds,
          perQuery: opts.perQuery,
          apiKey: exaKey,
          seen,
          stats,
          dryRun: false,
        })),
      );
    }
  } else {
    allRows.push(
      ...(await runBraveSearch({
        queries,
        perQuery: opts.perQuery,
        since: opts.since,
        apiKey: braveKey,
        seen,
        stats,
        dryRun: false,
      })),
    );
  }

  // Duplicates skipped = total returned by providers minus what we collected.
  // We don't count them here because `seen` already filters; instead track
  // growth of `seen` since start as the new-URL count.
  stats.duplicates = 0; // left as 0 — the producer loops skip silently

  if (opts.detect) {
    stats.contactDetected = await enrichContactUrls(allRows, false);
  }

  stats.appended = await sink.appendRows(allRows);

  console.error(
    `\ndone. appended ${stats.appended} new rows, ${stats.contactDetected} with contact_url.`,
  );
  writeStepSummary({
    provider: opts.provider,
    mode: opts.mode,
    stats,
    sheetId: opts.csv ? null : sheetId,
    csvPath: opts.csv,
  });
}

function stubArgs(opts, stats) {
  return {
    perQuery: opts.perQuery,
    since: opts.since,
    apiKey: null,
    seen: new Set(),
    stats,
    dryRun: true,
  };
}

main().catch((e) => {
  console.error(e.stack || e.message);
  exit(1);
});
