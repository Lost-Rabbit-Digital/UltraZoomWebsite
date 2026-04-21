// Minimal Brave Search API client. Docs: https://api-dashboard.search.brave.com
//
// Single endpoint:
//   GET /res/v1/web/search?q=<query>&count=<n>
//
// Auth: X-Subscription-Token header.
//
// Rate limit: 1 request/sec on the free tier. We serialize calls and enforce
// the gap here so callers don't need to think about it.

const BASE = "https://api.search.brave.com/res/v1";
const MIN_GAP_MS = 1100; // free tier: 1 rps; leave 100ms slack
const RETRY_STATUSES = new Set([408, 429, 500, 502, 503, 504]);
const MAX_ATTEMPTS = 4;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Domains we strip from results. Same list as exa.mjs; duplicated so each
// provider module stays standalone.
const SKIP_DOMAINS = new Set([
  "chromewebstore.google.com",
  "chrome.google.com",
  "addons.mozilla.org",
  "microsoftedge.microsoft.com",
  "play.google.com",
  "apps.apple.com",
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
  "ultrazoom.app",
]);

let lastCallAt = 0;

async function throttle() {
  const now = Date.now();
  const gap = now - lastCallAt;
  if (gap < MIN_GAP_MS) await sleep(MIN_GAP_MS - gap);
  lastCallAt = Date.now();
}

async function call(params, apiKey) {
  const url = new URL(BASE + "/web/search");
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    await throttle();
    let res;
    try {
      res = await fetch(url, {
        headers: {
          accept: "application/json",
          "accept-encoding": "gzip",
          "x-subscription-token": apiKey,
        },
      });
    } catch (err) {
      if (attempt === MAX_ATTEMPTS) throw err;
      const wait = 2 ** attempt * 1000;
      console.error(`  retry ${attempt}/${MAX_ATTEMPTS - 1} after ${wait}ms — network: ${err.message}`);
      await sleep(wait);
      continue;
    }
    const text = await res.text();
    if (res.ok) {
      try {
        return JSON.parse(text);
      } catch {
        throw new Error(`Brave: non-JSON response: ${text.slice(0, 200)}`);
      }
    }
    if (RETRY_STATUSES.has(res.status) && attempt < MAX_ATTEMPTS) {
      const wait = 2 ** attempt * 1000;
      console.error(`  retry ${attempt}/${MAX_ATTEMPTS - 1} after ${wait}ms — Brave ${res.status}`);
      await sleep(wait);
      continue;
    }
    throw new Error(`Brave ${res.status}: ${text.slice(0, 300)}`);
  }
  throw new Error(`Brave: exhausted ${MAX_ATTEMPTS} attempts`);
}

// Brave freshness param: pd (24h), pw (week), pm (month), py (year), or
// absolute range "YYYY-MM-DDtoYYYY-MM-DD".
function toFreshness(since) {
  if (!since) return undefined;
  const today = new Date().toISOString().slice(0, 10);
  return `${since}to${today}`;
}

export async function search({ apiKey, query, numResults = 10, since }) {
  const json = await call(
    {
      q: query,
      count: Math.min(20, numResults), // Brave max is 20
      safesearch: "moderate",
      freshness: toFreshness(since),
    },
    apiKey,
  );
  const items = json?.web?.results || [];
  return items.map(normalize).filter((r) => r && !SKIP_DOMAINS.has(r.domain));
}

function normalize(r) {
  if (!r.url) return null;
  return {
    url: r.url,
    title: r.title || "",
    domain: hostOf(r.url),
    published_date: r.page_age || r.age || "",
    author: "",
    summary: (r.description || "").replace(/\s+/g, " ").trim().slice(0, 300),
    score: null,
  };
}

function hostOf(u) {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
