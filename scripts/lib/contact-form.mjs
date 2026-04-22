// Best-effort contact-form (and email) discovery for a lead.
//
// Strategy, in order, until something hits:
//   1. Fetch the article URL itself. Look for <a> tags whose text or href
//      hints at a contact page ("contact", "get in touch", "tip us", etc).
//      If the article doesn't surface one, fetch the homepage `/` and try
//      again. Almost every blog links to its contact page from nav/footer
//      so this is the single highest-yield signal.
//   2. Fall back to probing a long list of common contact paths against
//      the same origin (legacy behavior). Good safety net for sites that
//      don't link to contact from the article body.
//   3. For every candidate URL we visit, run the form detector. If we
//      find a real form (or recognized embed), return that URL.
//   4. If nothing has a form, scan visited HTML for `mailto:` links and
//      return the most plausible one. The caller writes this into a
//      separate `contact_email` column so a human can still send.
//
// All HTTP work is bounded by a per-lead budget so a slow site can't
// blow the whole job. Per-domain results are cached: if 12 articles are
// from the same blog, we only resolve its contact info once.

const CANDIDATE_PATHS = [
  "/contact",
  "/contact-us",
  "/contact-us/",
  "/contact/",
  "/contact.html",
  "/contact.php",
  "/about/contact",
  "/about/contact/",
  "/get-in-touch",
  "/get-in-touch/",
  "/getintouch",
  "/reach-us",
  "/reach-out",
  "/say-hi",
  "/sayhi",
  "/hello",
  "/connect",
  "/work-with-us",
  "/collab",
  "/collaborate",
  "/write-for-us",
  "/pitch",
  "/pitches",
  "/submit",
  "/submit-a-tip",
  "/tip",
  "/tips",
  "/tip-us",
  "/feedback",
  "/support",
  "/help",
  "/press",
  "/press-contact",
  "/about",
  "/about-us",
  "/about-me",
  "/colophon",
];

// Embedded third-party form providers we recognize from the HTML.
// Covers the common SaaS forms plus the dominant WordPress plugins.
const EMBED_PATTERNS = [
  /formspree\.io/i,
  /typeform\.com/i,
  /jotform\.com/i,
  /forms\.gle/i,
  /docs\.google\.com\/forms/i,
  /google\.com\/forms/i,
  /hsforms\.com/i,
  /hsforms\.net/i,
  /hubspotforms/i,
  /wufoo\.com/i,
  /gravityforms?/i,
  /\bwpforms\b/i,
  /\bwpcf7\b/i,
  /contact-form-7/i,
  /\bninja[-_]?forms\b/i,
  /\belementor[-_]?form\b/i,
  /\bfluent[-_]?forms?\b/i,
  /\bforminator\b/i,
  /\bkadence[-_]?form/i,
  /tally\.so/i,
  /fillout\.com/i,
  /paperform\.co/i,
  /getform\.io/i,
  /usebasin\.com/i,
  /data-netlify=["']?true/i,
  /netlify-forms?/i,
  /web3forms\.com/i,
  /formcarry\.com/i,
  /staticforms\.xyz/i,
  /\bmailerlite[-_]?form/i,
  /\bconvertkit\b.*form/i,
];

// Anchor text / href tokens that suggest a contact page. Ordered roughly
// by signal strength; first hit wins when we scan a page.
const CONTACT_LINK_PATTERNS = [
  { rx: /\b(contact[-\s]?us|contact[-\s]?me|contact)\b/i, weight: 10 },
  { rx: /\bget[-\s]?in[-\s]?touch\b/i, weight: 9 },
  { rx: /\b(reach[-\s]?out|reach[-\s]?us)\b/i, weight: 8 },
  { rx: /\b(work[-\s]?with[-\s]?(us|me)|hire[-\s]?(us|me))\b/i, weight: 7 },
  { rx: /\bwrite[-\s]?for[-\s]?us\b/i, weight: 7 },
  { rx: /\b(submit[-\s]?a[-\s]?tip|tip[-\s]?us|send[-\s]?a[-\s]?tip)\b/i, weight: 7 },
  { rx: /\b(pitch|pitches)\b/i, weight: 6 },
  { rx: /\b(say[-\s]?hi|say[-\s]?hello)\b/i, weight: 6 },
  { rx: /\b(press|press[-\s]?contact)\b/i, weight: 5 },
  { rx: /\bcollab(orate|oration)?\b/i, weight: 5 },
  { rx: /\babout[-\s]?(us|me)\b/i, weight: 3 },
  { rx: /\babout\b/i, weight: 2 },
];

// Email addresses we throw out — generic social/no-reply patterns or
// the kind of contact you'd never use for outreach.
const EMAIL_BLOCKLIST = [
  /@example\./i,
  /@sentry\.io/i,
  /@(wordpress|wp)\./i,
  /noreply|no-reply|donotreply|do-not-reply/i,
  /abuse@|postmaster@|webmaster@|hostmaster@/i,
  /privacy@|legal@|dmca@|copyright@|gdpr@/i,
  /unsubscribe@/i,
];

// Preference order when we find multiple mailto: addresses on a page.
// Earlier patterns rank higher.
const EMAIL_PREFERENCE = [
  /^(hi|hello|hey|hola)@/i,
  /^(tips?|pitch|pitches|press|editorial|editor|news|story|stories)@/i,
  /^(contact|inquiries|enquiries|outreach|collab|collabs|partnerships|partner)@/i,
  /^(team|info|mail|support|help)@/i,
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
    // Cap at 750 KB — enough to find footers, embeds, and mailtos
    // without buffering megabyte-sized listicle pages forever.
    const text = (await res.text()).slice(0, 750_000);
    if (!/<html\b|<!doctype\s+html|<body\b|<form\b/i.test(text.slice(0, 2000))) {
      return null;
    }
    return { html: text, finalUrl: res.url || url };
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
  const hasMessageInput =
    /name=["'](message|comments?|inquiry|enquiry|body|your[-_]?message)["']/i.test(html);
  if (hasForm && (hasTextarea || hasEmailInput || hasMessageInput)) return true;
  for (const pat of EMBED_PATTERNS) {
    if (pat.test(html)) return true;
  }
  return false;
}

// Pull all <a href="..."> ... </a> pairs out of HTML. Returns an array of
// { href, text } with text/href trimmed and decoded. Cheap regex parser —
// good enough since we just need to score links by token match.
function extractLinks(html) {
  const out = [];
  const rx = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
  let m;
  while ((m = rx.exec(html)) !== null) {
    const attrs = m[1];
    const inner = m[2];
    const hrefMatch = attrs.match(/\bhref\s*=\s*["']([^"']+)["']/i);
    if (!hrefMatch) continue;
    const href = hrefMatch[1].trim();
    if (!href || href.startsWith("#") || href.startsWith("javascript:")) continue;
    const text = inner.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    out.push({ href, text });
  }
  return out;
}

// Score each link against CONTACT_LINK_PATTERNS. Higher = more likely
// to be the contact page. Returns links sorted best-first.
function rankContactLinks(links, baseOrigin) {
  const scored = [];
  for (const { href, text } of links) {
    let abs;
    try {
      abs = new URL(href, baseOrigin).toString();
    } catch {
      continue;
    }
    // Same-origin only — we don't want to redirect outreach to a
    // third-party "contact our parent company" page.
    let originHost;
    try {
      originHost = new URL(abs).hostname.replace(/^www\./, "");
    } catch {
      continue;
    }
    const baseHost = new URL(baseOrigin).hostname.replace(/^www\./, "");
    if (originHost !== baseHost) continue;

    let best = 0;
    for (const { rx, weight } of CONTACT_LINK_PATTERNS) {
      if (rx.test(text) || rx.test(href)) {
        if (weight > best) best = weight;
      }
    }
    if (best > 0) scored.push({ url: abs, score: best });
  }
  scored.sort((a, b) => b.score - a.score);
  // De-dup by URL while preserving order.
  const seen = new Set();
  const out = [];
  for (const s of scored) {
    if (seen.has(s.url)) continue;
    seen.add(s.url);
    out.push(s.url);
  }
  return out;
}

// Pull mailto: addresses out of HTML. Returns the best-ranked address
// or "" if nothing usable was found.
//
// `allowLiteral` opts into scraping bare `name@host.tld` text — only safe
// on pages we already believe are contact/about pages, since article
// bodies routinely contain unrelated emails (visa support lines, source
// quotes, etc.) that would otherwise become false positives.
export function extractEmail(html, { allowLiteral = false } = {}) {
  if (!html) return "";
  const found = new Set();
  const mailtoRx = /mailto:([^"'?\s>]+)/gi;
  let m;
  while ((m = mailtoRx.exec(html)) !== null) {
    const addr = decodeURIComponent(m[1]).toLowerCase().trim();
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(addr)) found.add(addr);
  }
  if (found.size === 0 && allowLiteral) {
    const literalRx = /[a-z0-9][a-z0-9._+-]*@[a-z0-9][a-z0-9.-]*\.[a-z]{2,24}/gi;
    let lm;
    while ((lm = literalRx.exec(html)) !== null) {
      found.add(lm[0].toLowerCase().replace(/[.,;:)\]]+$/, ""));
    }
  }
  if (found.size === 0) return "";

  const candidates = [...found].filter(
    (e) => !EMAIL_BLOCKLIST.some((rx) => rx.test(e)),
  );
  if (candidates.length === 0) return "";

  // Rank by EMAIL_PREFERENCE order; unmatched addresses go last.
  candidates.sort((a, b) => {
    const ai = EMAIL_PREFERENCE.findIndex((rx) => rx.test(a));
    const bi = EMAIL_PREFERENCE.findIndex((rx) => rx.test(b));
    const aRank = ai === -1 ? 999 : ai;
    const bRank = bi === -1 ? 999 : bi;
    if (aRank !== bRank) return aRank - bRank;
    return a.localeCompare(b);
  });
  return candidates[0];
}

// Resolve contact info for a single article URL. Returns:
//   { contactUrl, contactEmail, method }
// where method is "form" | "email" | "" (none found). The detector tries
// link-scraping first, then path probing, then mailto: extraction.
export async function findContactInfo(
  articleUrl,
  { timeoutMs = 4000, budgetMs = 15000 } = {},
) {
  const empty = { contactUrl: "", contactEmail: "", method: "" };
  let origin;
  try {
    origin = new URL(articleUrl).origin;
  } catch {
    return empty;
  }

  const deadline = Date.now() + budgetMs;
  // Track which fetched HTML came from a contact/about-style page vs. the
  // article body. Only contact/about pages are safe for literal-email
  // extraction; article bodies leak unrelated addresses.
  const probedPages = []; // { html, isContactish }
  const visitedUrls = new Set();
  let foundUrl = "";

  const remaining = () => Math.max(0, deadline - Date.now());
  const budgetedFetch = async (url) => {
    if (visitedUrls.has(url)) return null;
    visitedUrls.add(url);
    const t = Math.min(timeoutMs, remaining());
    if (t <= 0) return null;
    return await fetchHtml(url, t);
  };
  // Step 1: scrape the article (and homepage) for contact-link candidates.
  const linkCandidates = [];
  for (const seed of [articleUrl, origin + "/"]) {
    if (remaining() <= 0) break;
    const r = await budgetedFetch(seed);
    if (!r) continue;
    // Article and homepage are not contact-ish; they get mailto-only.
    probedPages.push({ html: r.html, isContactish: false });
    const links = extractLinks(r.html);
    for (const u of rankContactLinks(links, origin)) {
      if (!linkCandidates.includes(u)) linkCandidates.push(u);
      if (linkCandidates.length >= 6) break;
    }
    if (linkCandidates.length >= 6) break;
  }

  // Step 2: probe the link candidates first, then the static path list.
  const probeOrder = [
    ...linkCandidates,
    ...CANDIDATE_PATHS.map((p) => origin + p),
  ];
  const probedSet = new Set();

  for (const url of probeOrder) {
    if (remaining() <= 0) break;
    if (probedSet.has(url)) continue;
    probedSet.add(url);
    const r = await budgetedFetch(url);
    if (!r) continue;
    probedPages.push({ html: r.html, isContactish: true });
    if (hasContactForm(r.html)) {
      foundUrl = r.finalUrl || url;
      break;
    }
  }

  // Step 3: email fallback. mailto: links are always trusted; literal
  // text-only emails are only trusted on contact/about pages.
  let foundEmail = "";
  for (const { html, isContactish: ci } of probedPages) {
    const e = extractEmail(html, { allowLiteral: ci });
    if (e) {
      foundEmail = e;
      break;
    }
  }

  if (foundUrl) return { contactUrl: foundUrl, contactEmail: foundEmail, method: "form" };
  if (foundEmail) return { contactUrl: "", contactEmail: foundEmail, method: "email" };
  return empty;
}

// Backwards-compatible single-URL helper. Kept so any callers that just
// want a contact_url string still work. New code should use findContactInfo.
export async function findContactUrl(articleUrl, opts) {
  const { contactUrl } = await findContactInfo(articleUrl, opts);
  return contactUrl;
}

// Enrich a batch of rows in parallel. Each row must have at least { url };
// after this returns the row also has { contact_url, contact_email,
// contact_method }. Per-domain results are cached so 12 articles from the
// same blog only cost one probe.
//
// Returns the count of rows where we found *something* (form or email).
export async function enrichWithContactUrls(
  rows,
  { concurrency = 8, timeoutMs = 4000, budgetMs = 15000 } = {},
) {
  const cache = new Map(); // domain → Promise<{ contactUrl, contactEmail, method }>
  let index = 0;
  let detected = 0;

  const resolveFor = (url) => {
    let host;
    try {
      host = new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return Promise.resolve({ contactUrl: "", contactEmail: "", method: "" });
    }
    if (!cache.has(host)) {
      cache.set(host, findContactInfo(url, { timeoutMs, budgetMs }));
    }
    return cache.get(host);
  };

  const workers = Array.from({ length: concurrency }, async () => {
    while (index < rows.length) {
      const i = index++;
      const row = rows[i];
      const info = await resolveFor(row.url);
      if (info.contactUrl) {
        row.contact_url = info.contactUrl;
      }
      if (info.contactEmail) {
        row.contact_email = info.contactEmail;
      }
      row.contact_method = info.method;
      if (info.contactUrl || info.contactEmail) detected++;
    }
  });
  await Promise.all(workers);
  return detected;
}
