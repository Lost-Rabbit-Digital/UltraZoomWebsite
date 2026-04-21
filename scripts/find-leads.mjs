#!/usr/bin/env node
/*
 * find-leads.mjs — dork-driven lead discovery for contact-form outreach.
 *
 * Reads a markdown file of Google dorks (fenced code blocks), runs each query
 * against the Google Custom Search JSON API, dedupes + filters results, and
 * writes a CSV ready to import into Google Sheets.
 *
 * Setup (one-time, ~10 min):
 *   1. Create / pick a Google Cloud project:  https://console.cloud.google.com
 *   2. Enable "Custom Search API" in that project.
 *   3. Create an API key under "APIs & Services → Credentials".
 *   4. Create a Programmable Search Engine:  https://programmablesearchengine.google.com
 *      Toggle "Search the entire web" ON. Copy the "Search engine ID" (cx).
 *   5. Export the env vars:
 *        export GOOGLE_CSE_KEY=...
 *        export GOOGLE_CSE_ID=...
 *
 * Usage:
 *   node scripts/find-leads.mjs [options]
 *
 * Options:
 *   --dorks <file>      Path to a dorks markdown file. Parses fenced code
 *                       blocks; each non-empty line is one query.
 *                       Default: docs/outreach/dorks.md
 *   --out <file>        Output CSV path. Default: docs/outreach/leads-contact-form.csv
 *                       (appends if file exists, keeps URL dedupe)
 *   --limit <n>         Max queries to run this invocation. Default: 20.
 *   --per-query <n>     Results per query (CSE max is 10). Default: 10.
 *   --sections <re>     Regex to filter dork sections by heading text.
 *                       Example: --sections "listicle|photography"
 *   --dry-run           Print the queries that would run and exit.
 *
 * Notes:
 *   - Free CSE quota: 100 queries/day. Respect it; this script counts.
 *   - To swap in SerpAPI: replace `runQuery()` body with a SerpAPI call.
 *   - Known-bad domains (chrome store, addons.mozilla.org, etc.) are filtered
 *     so you don't have to scroll past them in the Sheet.
 */

import { readFileSync, appendFileSync, existsSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { argv, env, exit } from "node:process";

const DEFAULT_DORKS = "docs/outreach/dorks.md";
const DEFAULT_OUT = "docs/outreach/leads-contact-form.csv";

const CSV_COLUMNS = [
  "found_at",
  "category",
  "query",
  "rank",
  "title",
  "url",
  "domain",
  "snippet",
  "status",
  "template",
  "contact_url",
  "message_sent",
  "reply",
  "notes",
];

// Domains we never want in the output — first-party stores, search engines,
// social aggregators with no contact surface, etc.
const SKIP_DOMAINS = new Set([
  "chromewebstore.google.com",
  "chrome.google.com",
  "addons.mozilla.org",
  "microsoftedge.microsoft.com",
  "apps.apple.com",
  "play.google.com",
  "youtube.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "instagram.com",
  "linkedin.com",
  "pinterest.com",
  "github.com",
  "stackoverflow.com",
  "google.com",
  "bing.com",
  "duckduckgo.com",
]);

function parseArgs(raw) {
  const out = {
    dorks: DEFAULT_DORKS,
    out: DEFAULT_OUT,
    limit: 20,
    perQuery: 10,
    sections: null,
    dryRun: false,
  };
  for (let i = 2; i < raw.length; i++) {
    const a = raw[i];
    const next = () => raw[++i];
    if (a === "--dorks") out.dorks = next();
    else if (a === "--out") out.out = next();
    else if (a === "--limit") out.limit = Number(next());
    else if (a === "--per-query") out.perQuery = Math.min(10, Number(next()));
    else if (a === "--sections") out.sections = new RegExp(next(), "i");
    else if (a === "--dry-run") out.dryRun = true;
    else if (a === "-h" || a === "--help") {
      console.log(readFileSync(new URL(import.meta.url), "utf8").split("*/")[0]);
      exit(0);
    } else {
      console.error(`unknown arg: ${a}`);
      exit(2);
    }
  }
  return out;
}

// Extract queries grouped by section heading. A section is an H2 (## …) in
// the dorks markdown; queries are the non-empty, non-comment lines inside
// fenced ``` blocks under that heading.
function parseDorks(path, sectionFilter) {
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n");
  const results = [];
  let currentSection = "uncategorized";
  let inFence = false;
  for (const line of lines) {
    if (line.startsWith("## ")) {
      currentSection = line.replace(/^##+\s*/, "").trim();
      inFence = false;
      continue;
    }
    if (line.startsWith("### ")) {
      // treat H3 as a subsection appended to the parent
      const sub = line.replace(/^#+\s*/, "").trim();
      currentSection = currentSection.split(" — ")[0] + " — " + sub;
      continue;
    }
    if (line.trim().startsWith("```")) {
      inFence = !inFence;
      continue;
    }
    if (!inFence) continue;
    const q = line.trim();
    if (!q || q.startsWith("#") || q.startsWith("//")) continue;
    if (sectionFilter && !sectionFilter.test(currentSection)) continue;
    results.push({ section: currentSection, query: q });
  }
  return results;
}

function csvEscape(v) {
  if (v == null) return "";
  const s = String(v);
  if (s.includes('"') || s.includes(",") || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function loadExistingUrls(path) {
  const urls = new Set();
  if (!existsSync(path)) return urls;
  const text = readFileSync(path, "utf8");
  const lines = text.split("\n").slice(1); // skip header
  for (const line of lines) {
    // crude CSV parse — pull the url column (index 5)
    const cols = splitCsvRow(line);
    if (cols[5]) urls.add(cols[5]);
  }
  return urls;
}

function splitCsvRow(line) {
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
      } else cur += c;
    } else {
      if (c === ",") {
        out.push(cur);
        cur = "";
      } else if (c === '"' && cur === "") {
        inQ = true;
      } else cur += c;
    }
  }
  out.push(cur);
  return out;
}

async function runQuery({ query, perQuery, key, cx }) {
  const url = new URL("https://www.googleapis.com/customsearch/v1");
  url.searchParams.set("key", key);
  url.searchParams.set("cx", cx);
  url.searchParams.set("q", query);
  url.searchParams.set("num", String(perQuery));
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`CSE ${res.status}: ${body.slice(0, 200)}`);
  }
  const json = await res.json();
  return json.items || [];
}

function hostOf(u) {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

async function main() {
  const opts = parseArgs(argv);
  const key = env.GOOGLE_CSE_KEY;
  const cx = env.GOOGLE_CSE_ID;

  if (!opts.dryRun && (!key || !cx)) {
    console.error("error: set GOOGLE_CSE_KEY and GOOGLE_CSE_ID env vars");
    console.error("       (or re-run with --dry-run to preview queries)");
    exit(1);
  }

  const dorksPath = resolve(opts.dorks);
  const outPath = resolve(opts.out);
  const all = parseDorks(dorksPath, opts.sections);
  const queries = all.slice(0, opts.limit);

  console.error(`parsed ${all.length} queries from ${opts.dorks} (running ${queries.length})`);

  if (opts.dryRun) {
    for (const { section, query } of queries) {
      console.log(`[${section}]  ${query}`);
    }
    return;
  }

  const existing = loadExistingUrls(outPath);
  const newUrls = new Set();

  if (!existsSync(outPath)) {
    writeFileSync(outPath, CSV_COLUMNS.join(",") + "\n");
  }

  const today = new Date().toISOString().slice(0, 10);
  let appended = 0;
  let skippedDup = 0;
  let skippedDomain = 0;

  for (const { section, query } of queries) {
    let items;
    try {
      items = await runQuery({ query, perQuery: opts.perQuery, key, cx });
    } catch (err) {
      console.error(`  ! ${query.slice(0, 60)} — ${err.message}`);
      if (String(err.message).includes("429") || String(err.message).includes("quota")) {
        console.error("  hit quota, stopping.");
        break;
      }
      continue;
    }

    let kept = 0;
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const host = hostOf(it.link);
      if (SKIP_DOMAINS.has(host)) {
        skippedDomain++;
        continue;
      }
      if (existing.has(it.link) || newUrls.has(it.link)) {
        skippedDup++;
        continue;
      }
      newUrls.add(it.link);
      const row = [
        today,
        section,
        query,
        i + 1,
        it.title || "",
        it.link,
        host,
        (it.snippet || "").replace(/\s+/g, " ").slice(0, 240),
        "new",
        "",
        "",
        "",
        "",
        "",
      ];
      appendFileSync(outPath, row.map(csvEscape).join(",") + "\n");
      appended++;
      kept++;
    }
    console.error(`  + [${kept}/${items.length}]  ${query.slice(0, 70)}`);
  }

  console.error(
    `\ndone. wrote ${appended} new rows to ${opts.out} (skipped ${skippedDup} dup, ${skippedDomain} bad-domain)`,
  );
}

main().catch((e) => {
  console.error(e);
  exit(1);
});
