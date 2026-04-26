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
 * (exa-search, exa-similar, brave-search). Dedup is per-domain and global
 * across providers and prior runs: once a domain has been written to the
 * sheet, no further articles from that domain will be appended. Contact
 * forms tend to be a single shared inbox per site, so a second article from
 * the same domain just means a duplicate message to the same person.
 *
 * After Exa/Brave returns results, each row is enriched with a best-effort
 * contact_url probe (HTTP HEAD/GET against common contact paths). Detection
 * runs with a per-URL budget so slow sites can't blow the Action timeout.
 *
 * Required env vars by provider:
 *   common: LEADS_SHEET_ID  (plus Google ADC — see scripts/lib/sheets.mjs)
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
 *   --sections <re>    regex filter on section headings
 *   --since <iso>      pages/results after this date (YYYY-MM-DD)
 *   --no-detect        skip contact_url auto-detection
 *   --rotate <mode>    daily | shuffle | none. Controls which slice of
 *                      the query file we run when --limit < total.
 *                      daily (default): rotate a window so every query
 *                        runs within ceil(total/limit) days.
 *                      shuffle: randomize and pick the first --limit.
 *                      none: take the first --limit in file order
 *                        (legacy behavior).
 *   --csv <path>       write to a local CSV file instead of Google Sheets
 *                      (useful for smoke-testing before Sheets is set up)
 *   --dry-run          preview queries, no API or Sheet calls
 */

import { readFileSync, appendFileSync } from "node:fs";
import { resolve } from "node:path";
import { argv, env, exit } from "node:process";

import { search as exaSearch, findSimilar as exaFindSimilar } from "./lib/exa.mjs";
import { search as braveSearch } from "./lib/brave.mjs";
import { makeClient, rowFromResult, SHEET_COLUMNS } from "./lib/sheets.mjs";
import { makeCsvClient } from "./lib/csv.mjs";
import { enrichWithContactUrls } from "./lib/contact-form.mjs";

const DEFAULTS = {
  exa: { queries: "docs/outreach/exa-queries.md" },
  brave: { queries: "docs/outreach/dorks.md" },
};

function parseArgs(raw) {
  const out = {
    provider: "exa",
    mode: "both",
    limit: 20,
    perQuery: 10,
    queries: null,
    sections: null,
    since: null,
    detect: true,
    rotate: "daily",
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
    else if (a === "--sections") out.sections = new RegExp(next(), "i");
    else if (a === "--since") out.since = next();
    else if (a === "--no-detect") out.detect = false;
    else if (a === "--rotate") out.rotate = next();
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
  if (!["daily", "shuffle", "none"].includes(out.rotate)) {
    console.error(`--rotate must be daily, shuffle, or none`);
    exit(2);
  }
  if (!out.queries) out.queries = DEFAULTS[out.provider].queries;
  return out;
}

// Stable hash of an arbitrary string. Used to seed the daily-rotation
// window so a query's bucket position is deterministic but well-mixed
// across the file.
function hashStr(s) {
  let h = 2166136261; // FNV-1a basis
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Deterministic shuffle (Fisher-Yates) seeded by an integer. Used by
// rotate=shuffle so reruns within the same process pick the same set,
// but different seeds give different orderings.
function seededShuffle(arr, seed) {
  const out = arr.slice();
  let state = seed >>> 0 || 1;
  for (let i = out.length - 1; i > 0; i--) {
    // xorshift32
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    state >>>= 0;
    const j = state % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

// Pick which `limit` queries to run today.
//   daily   — sort queries by hash(query, dayOfYear), take first `limit`.
//             Rolls through all queries within ceil(total/limit) days.
//   shuffle — randomize once per process and slice.
//   none    — file order, slice. Legacy behavior, useful for debugging.
function selectQueries(queries, limit, mode, provider) {
  if (queries.length <= limit || mode === "none") {
    return queries.slice(0, limit);
  }
  if (mode === "shuffle") {
    return seededShuffle(queries, Date.now() & 0xffffffff).slice(0, limit);
  }
  // daily: stable per-day window. Bucket each query by hash(query+day) so
  // every day produces a different but deterministic ordering.
  const day = Math.floor(Date.now() / 86_400_000);
  const tagged = queries.map((q) => ({
    q,
    rank: hashStr(`${provider}|${day}|${q.section}|${q.query}`),
  }));
  tagged.sort((a, b) => a.rank - b.rank);
  return tagged.slice(0, limit).map((t) => t.q);
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
    // After YEAR substitution, skip anything still templated. The
    // contact-info-finding section uses FIRSTNAME/LASTNAME/PUBLICATION
    // tokens that only make sense once you already have a lead.
    if (/\b(NICHE|BLOG_SPEAR|SUBREDDIT|FIRSTNAME|LASTNAME|PUBLICATION)\b/.test(q)) continue;
    if (sectionFilter && !sectionFilter.test(section)) continue;
    out.push({ section, query: q });
  }
  return out;
}

const FIVE_YEARS_MS = 5 * 365.25 * 24 * 60 * 60 * 1000;

function collect({ items, source, seed, seenDomains, rows }) {
  const foundAt = new Date().toISOString().slice(0, 10);
  const cutoff = Date.now() - FIVE_YEARS_MS;
  let kept = 0;
  for (const it of items) {
    if (!it || !it.url || !it.domain) continue;
    if (seenDomains.has(it.domain)) continue;
    if (it.published_date) {
      const pub = new Date(it.published_date).getTime();
      if (Number.isFinite(pub) && pub < cutoff) continue;
    }
    seenDomains.add(it.domain);
    rows.push(rowFromResult(it, { source, seed, foundAt }));
    kept++;
  }
  return kept;
}

async function runExaSearch({ queries, perQuery, since, apiKey, seenDomains, stats, dryRun }) {
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
    const kept = collect({ items, source: "exa-search", seed: query, seenDomains, rows });
    console.error(`  + [${kept}/${items.length}]  ${query.slice(0, 70)}`);
  }
  return rows;
}

async function runExaFindSimilar({ seeds, perQuery, apiKey, seenDomains, stats, dryRun }) {
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
    const kept = collect({ items, source: "exa-similar", seed: seedUrl, seenDomains, rows });
    console.error(`  + [${kept}/${items.length}]  ${seedUrl.slice(0, 70)}`);
  }
  return rows;
}

async function runBraveSearch({ queries, perQuery, since, apiKey, seenDomains, stats, dryRun }) {
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
    const kept = collect({ items, source: "brave-search", seed: query, seenDomains, rows });
    console.error(`  + [${kept}/${items.length}]  ${query.slice(0, 70)}`);
  }
  return rows;
}

async function enrichContactUrls(rows, dryRun) {
  if (dryRun || rows.length === 0) return 0;
  console.error(`\n== contact-form detection (${rows.length} rows) ==`);
  const urlIdx = SHEET_COLUMNS.indexOf("url");
  const tmpRows = rows.map((r) => ({
    url: r[urlIdx],
    contact_url: "",
    contact_email: "",
    contact_method: "",
  }));
  const detected = await enrichWithContactUrls(tmpRows);
  const today = new Date().toISOString().slice(0, 10);
  const cuIdx = SHEET_COLUMNS.indexOf("contact_url");
  const ceIdx = SHEET_COLUMNS.indexOf("contact_email");
  const cmIdx = SHEET_COLUMNS.indexOf("contact_method");
  const lcIdx = SHEET_COLUMNS.indexOf("last_checked_at");
  let formCount = 0;
  let emailCount = 0;
  for (let i = 0; i < rows.length; i++) {
    if (tmpRows[i].contact_url) {
      rows[i][cuIdx] = tmpRows[i].contact_url;
      formCount++;
    }
    if (tmpRows[i].contact_email) {
      rows[i][ceIdx] = tmpRows[i].contact_email;
      if (!tmpRows[i].contact_url) emailCount++;
    }
    if (tmpRows[i].contact_method) rows[i][cmIdx] = tmpRows[i].contact_method;
    rows[i][lcIdx] = today;
  }
  console.error(
    `  detected ${detected}/${rows.length}: ${formCount} forms, ${emailCount} email-only`,
  );
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
  const sheetId = env.LEADS_SHEET_ID;

  if (!opts.dryRun) {
    const missing = [];
    if (opts.provider === "exa" && !exaKey) missing.push("EXA_API_KEY");
    if (opts.provider === "brave" && !braveKey) missing.push("BRAVE_SEARCH_KEY");
    if (!opts.csv && !sheetId) missing.push("LEADS_SHEET_ID");
    if (missing.length) {
      console.error(`error: missing env vars: ${missing.join(", ")}`);
      console.error(`       (re-run with --dry-run to preview without secrets,`);
      console.error(`        or --csv <path> to write locally instead of Sheets)`);
      exit(1);
    }
  }

  const parseQueries = opts.provider === "exa" ? parseNlQueries : parseDorkQueries;
  const allQueries = parseQueries(resolve(opts.queries), opts.sections);
  const queries = selectQueries(allQueries, opts.limit, opts.rotate, opts.provider);

  console.error(`provider: ${opts.provider}  mode: ${opts.mode}  rotate: ${opts.rotate}`);
  console.error(`queries: ${queries.length}/${allQueries.length}`);
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
      if (opts.mode !== "search") {
        console.error(`\n== exa find-similar (seeds will be read from sheet at runtime) ==`);
      }
    } else {
      await runBraveSearch({ queries, ...stubArgs(opts, stats) });
    }
    return;
  }

  const sink = opts.csv
    ? makeCsvClient({ path: resolve(opts.csv) })
    : makeClient({ sheetId });
  await sink.ensureHeader();
  // Dedup is by domain. We derive the seed set from the URLs already in the
  // sheet rather than reading the `domain` column directly so that
  // hand-edited rows missing a domain value still count.
  const existingUrls = await sink.readUrls();
  const seenDomains = new Set();
  for (const u of existingUrls) {
    try {
      const host = new URL(u).hostname.replace(/^www\./, "");
      if (host) seenDomains.add(host);
    } catch {
      // ignore malformed URLs
    }
  }
  console.error(
    opts.csv
      ? `csv sink: ${opts.csv}  existing domains: ${seenDomains.size}`
      : `existing domains in sheet: ${seenDomains.size}`,
  );

  // For find-similar: pick seed URLs at random from URLs already in the sheet.
  // This keeps seeds current without any manually maintained JSON file.
  const allSeeds = opts.provider === "exa" ? [...existingUrls] : [];
  const seeds =
    allSeeds.length === 0 || allSeeds.length <= opts.limit || opts.rotate === "none"
      ? allSeeds.slice(0, opts.limit)
      : opts.rotate === "shuffle"
        ? seededShuffle(allSeeds, Date.now() & 0xffffffff).slice(0, opts.limit)
        : allSeeds
            .map((u) => ({ u, r: hashStr(`seed|${Math.floor(Date.now() / 86_400_000)}|${u}`) }))
            .sort((a, b) => a.r - b.r)
            .slice(0, opts.limit)
            .map((t) => t.u);
  if (opts.provider === "exa") {
    console.error(`seeds: ${seeds.length}/${allSeeds.length} (from sheet)`);
  }

  const allRows = [];
  if (opts.provider === "exa") {
    if (opts.mode !== "find-similar") {
      allRows.push(
        ...(await runExaSearch({
          queries,
          perQuery: opts.perQuery,
          since: opts.since,
          apiKey: exaKey,
          seenDomains,
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
          seenDomains,
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
        seenDomains,
        stats,
        dryRun: false,
      })),
    );
  }

  // Duplicates skipped = total returned by providers minus what we collected.
  // We don't count them here because `seenDomains` already filters; the
  // producer loops skip same-domain hits silently.
  stats.duplicates = 0;

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
    seenDomains: new Set(),
    stats,
    dryRun: true,
  };
}

main().catch((e) => {
  console.error(e.stack || e.message);
  exit(1);
});
