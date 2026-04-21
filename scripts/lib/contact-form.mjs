// Best-effort contact-form URL detection for a lead.
//
// Given an article URL, probe a handful of common contact paths on the same
// origin and return the first one that looks like it actually contains a
// form (or embeds a known form provider). Returns "" if nothing looks real
// — we'd rather skip than write a false lead into the Sheet.
//
// This is intentionally simple: HEAD/GET + regex. We don't execute JS, so
// forms rendered entirely client-side (rare in the listicle-blog niche)
// won't be detected. That's fine — the human can find those during triage.

const CANDIDATE_PATHS = [
  "/contact",
  "/contact-us",
  "/contact-us/",
  "/contact/",
  "/contact.html",
  "/contact.php",
  "/about/contact",
  "/get-in-touch",
  "/get-in-touch/",
  "/reach-us",
  "/reach-out",
  "/write-for-us",
  "/pitch",
  "/hire-us",
  "/about",
  "/about-us",
];

// Embedded third-party form providers we recognize from the HTML.
const EMBED_PATTERNS = [
  /formspree\.io/i,
  /typeform\.com/i,
  /jotform\.com/i,
  /forms\.gle/i,
  /hsforms\.com/i,
  /hsforms\.net/i,
  /hubspotforms/i,
  /google\.com\/forms/i,
  /wufoo\.com/i,
  /gravityforms/i,
];

const UA = "Mozilla/5.0 (compatible; UltraZoomLeadBot/1.0; +https://ultrazoom.app)";

async function fetchHtml(url, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      signal: ctrl.signal,
      redirect: "follow",
      headers: {
        "user-agent": UA,
        accept: "text/html,application/xhtml+xml",
      },
    });
    if (!res.ok) return null;
    // Cap at 500 KB — more than enough to find <form>, avoids huge pages.
    // Skip content-type check: many sites (including CF Workers) serve
    // HTML with text/plain or other wrong types.
    const text = (await res.text()).slice(0, 500_000);
    // Cheap sanity check that this is actually HTML of some kind.
    if (!/<html\b|<!doctype\s+html|<body\b|<form\b/i.test(text.slice(0, 2000))) {
      return null;
    }
    return text;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export function hasContactForm(html) {
  if (!html) return false;
  const hasForm = /<form\b/i.test(html);
  const hasTextarea = /<textarea\b/i.test(html);
  const hasEmailInput = /<input[^>]+type=["']?email["']?/i.test(html);
  const hasMessageInput = /name=["'](message|comments|inquiry|enquiry|body)["']/i.test(html);
  if (hasForm && (hasTextarea || hasEmailInput || hasMessageInput)) return true;
  for (const pat of EMBED_PATTERNS) {
    if (pat.test(html)) return true;
  }
  return false;
}

export async function findContactUrl(
  articleUrl,
  { timeoutMs = 3000, budgetMs = 8000 } = {},
) {
  let origin;
  try {
    origin = new URL(articleUrl).origin;
  } catch {
    return "";
  }
  const deadline = Date.now() + budgetMs;
  for (const path of CANDIDATE_PATHS) {
    if (Date.now() >= deadline) break;
    const remaining = Math.min(timeoutMs, deadline - Date.now());
    if (remaining <= 0) break;
    const url = origin + path;
    const html = await fetchHtml(url, remaining);
    if (html && hasContactForm(html)) return url;
  }
  return "";
}

// Simple concurrency limiter so we don't blast 200 domains sequentially.
export async function enrichWithContactUrls(
  rows,
  { concurrency = 8, timeoutMs = 3000, budgetMs = 8000 } = {},
) {
  let index = 0;
  let detected = 0;
  const workers = Array.from({ length: concurrency }, async () => {
    while (index < rows.length) {
      const i = index++;
      const row = rows[i];
      const url = await findContactUrl(row.url, { timeoutMs, budgetMs });
      if (url) {
        row.contact_url = url;
        detected++;
      }
    }
  });
  await Promise.all(workers);
  return detected;
}
