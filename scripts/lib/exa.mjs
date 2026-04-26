// Minimal Exa API client. Docs: https://docs.exa.ai
//
// Two endpoints are used:
//   - /search         → neural search from a natural-language query
//   - /findSimilar    → given a seed URL, return similar pages
//
// Auth: single API key in the `x-api-key` header.

import { toIsoDate } from "./util.mjs";

const BASE = "https://api.exa.ai";

const EXCLUDE_DOMAINS = [
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
  // Blogspot subdomains essentially never expose a usable contact channel,
  // so skip the whole TLD instead of burning probe budget on them.
  "blogspot.com",
];

const RETRY_STATUSES = new Set([408, 429, 500, 502, 503, 504]);
const MAX_ATTEMPTS = 4; // 1 initial + 3 retries → 2s, 4s, 8s backoff
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function call(path, body, apiKey) {
  let lastErr;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    let res;
    try {
      res = await fetch(BASE + path, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": apiKey,
        },
        body: JSON.stringify(body),
      });
    } catch (err) {
      lastErr = err;
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
        throw new Error(`Exa ${path}: non-JSON response: ${text.slice(0, 200)}`);
      }
    }
    if (RETRY_STATUSES.has(res.status) && attempt < MAX_ATTEMPTS) {
      const wait = 2 ** attempt * 1000;
      console.error(`  retry ${attempt}/${MAX_ATTEMPTS - 1} after ${wait}ms — Exa ${path} ${res.status}`);
      await sleep(wait);
      continue;
    }
    throw new Error(`Exa ${path} ${res.status}: ${text.slice(0, 300)}`);
  }
  throw lastErr || new Error(`Exa ${path}: exhausted ${MAX_ATTEMPTS} attempts`);
}

export async function search({ apiKey, query, numResults = 10, startPublishedDate }) {
  const body = {
    query,
    numResults,
    type: "neural",
    excludeDomains: EXCLUDE_DOMAINS,
    contents: { text: { maxCharacters: 300 } },
  };
  if (startPublishedDate) body.startPublishedDate = startPublishedDate;
  const json = await call("/search", body, apiKey);
  return (json.results || []).map(normalize);
}

export async function findSimilar({ apiKey, url, numResults = 10 }) {
  const body = {
    url,
    numResults,
    excludeSourceDomain: true,
    excludeDomains: EXCLUDE_DOMAINS,
    contents: { text: { maxCharacters: 300 } },
  };
  const json = await call("/findSimilar", body, apiKey);
  return (json.results || []).map(normalize);
}

function normalize(r) {
  const host = hostOf(r.url);
  return {
    url: r.url,
    title: r.title || "",
    domain: host,
    published_date: toIsoDate(r.publishedDate || ""),
    author: r.author || "",
    summary: (r.text || r.summary || "").replace(/\s+/g, " ").trim().slice(0, 300),
    score: typeof r.score === "number" ? r.score : null,
  };
}

function hostOf(u) {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}
