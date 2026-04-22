// Pick a contact-form template + draft a short message for the HailBytes
// outreach lane (PoC).
//
// Canonical human-readable templates live in
// docs/outreach-hailbytes/contact-form-templates.md. The drafts below mirror
// them as short, form-safe variants (no markdown, one URL, ~500-800 chars)
// so the `message_draft` column is copy-paste-ready.
//
// Drafting has two layers:
//   1. Template picker (bucket)   — which product pitch fits the firm?
//        hb-sat-training, hb-asm-pentest, hb-asm-mssp, hb-asm-vciso,
//        hb-asm-generic (fallback).
//   2. Opener picker (page type)  — what kind of page did we scrape?
//        service_page | homepage | contact_page | article | off_topic | other
//      Each page type gets a different opener sentence so we don't quote a
//      "Contact Us" page as if it were an article. See classifyPageType.
//
// Topic normalization: rather than slicing raw page titles (which yields
// truncated strings like "NIST 800" or "Managed Detection"), a canonical
// topic table scans title + seed query for known terms and returns a
// natural-reading phrase. Falls back per template when nothing matches.
//
// Rotation: two pitch/CTA variants per bucket, selected deterministically
// from a hash of the URL so re-runs produce the same draft for the same lead.

const SIGN_OFF = "Thanks,\nDavid McHale, HailBytes\nhttps://hailbytes.com";

// ---- Bucket (product pitch) classification ---------------------------------
//
// Order matters: SAT first, then pentest, MSSP, vCISO, then fallback.
const BUCKETS = [
  {
    id: "hb-sat-training",
    pattern:
      /\b(phishing\s+simulation|security\s+awareness\s+training|awareness\s+training|human\s+risk|phishing\s+testing|phishing\s+training|security\s+culture|user\s+training|employee\s+training|knowbe4)\b/i,
  },
  {
    id: "hb-asm-pentest",
    pattern:
      /\b(penetration\s+testing|pen[-\s]?test(?:ing)?|pentest(?:er|ing)?|offensive\s+security|red\s+team|adversary\s+emulation|purple\s+team|social\s+engineering\s+assessment|ethical\s+hacking)\b/i,
  },
  {
    id: "hb-asm-mssp",
    pattern:
      /\b(mssp|managed\s+security\s+service|managed\s+detection|mdr\b|xdr\b|managed\s+siem|soc[-\s]?as[-\s]?a[-\s]?service|soc\s+as\s+a\s+service|24\/7\s+monitoring|managed\s+cybersecurity|security\s+operations\s+center)\b/i,
  },
  {
    id: "hb-asm-vciso",
    pattern:
      /\b(vciso|virtual\s+ciso|fractional\s+ciso|ciso[-\s]?as[-\s]?a[-\s]?service|grc\s+consult|compliance\s+consult|soc\s*2|hipaa|pci[-\s]?dss|cmmc|nist\s*800|iso\s*27001|risk\s+advisory|cybersecurity\s+advisory)\b/i,
  },
];

// ---- Template pitches + CTAs -----------------------------------------------
//
// Variants are paired: variant i uses pitch i and cta i. Each pitch MUST
// read naturally when prefixed with a page-type opener (see OPENERS below),
// so none of them assume prior context about what was scraped.

const TEMPLATES = {
  "hb-asm-pentest": {
    defaultTopic: "offensive security",
    variants: [
      {
        pitch:
          "I'm launching HailBytes ASM, an attack surface management platform built for pen-testing and offensive-security firms. It orchestrates 30+ recon tools (subfinder, nmap, nuclei, httpx, ffuf, and more) into one continuous pipeline, runs in your own Azure or AWS tenant, and has no per-asset fee, so you can monitor every engagement's external surface without per-target licensing.",
        cta: "Would you try it free for 30 days and share honest feedback? Happy to set up a short demo.",
      },
      {
        pitch:
          "We're launching HailBytes ASM, an attack surface management platform aimed at pentest firms that want continuous external recon across all their engagements without per-target licensing. It chains 30+ tools (subfinder, nmap, nuclei, httpx, ffuf, etc.) into one pipeline, runs in your own cloud tenant, correlates findings in Postgres, and adds AI-assisted triage.",
        cta: "I'd love to get it in front of working pentesters. Free 30-day trial in exchange for feedback. Interested?",
      },
    ],
  },
  "hb-asm-mssp": {
    defaultTopic: "MDR and managed security",
    variants: [
      {
        pitch:
          "I'm launching HailBytes ASM, an attack surface management platform built for MSSPs that want to add continuous external recon to their managed service catalog. It runs 7 automated scan phases across 30+ tools, deploys in your own Azure or AWS tenant (so client data never leaves your cloud), supports multi-tenant project isolation and RBAC, and has no per-asset fee, with unlimited targets at every tier.",
        cta: "Would you try it free for 30 days and share feedback from an MSSP's perspective?",
      },
      {
        pitch:
          "We're launching HailBytes ASM, an attack surface management platform designed for MSSPs and MDR providers. It gives you continuous external recon across all your clients from a single deployment in your own tenant, with multi-tenant project isolation, RBAC, and unlimited targets (no per-asset fee). AI-powered triage generates executive reports automatically.",
        cta: "Free 30-day trial. I'd love your feedback on whether it fits into an MSSP workflow. Happy to set up a demo.",
      },
    ],
  },
  "hb-asm-vciso": {
    defaultTopic: "vCISO and GRC services",
    variants: [
      {
        pitch:
          "I'm launching HailBytes ASM, an attack surface management platform that fits naturally into a vCISO or GRC engagement. It gives your clients continuous external-asset discovery and vulnerability monitoring from a single deployment in their own cloud tenant, with audit-logged findings that map to SOC 2, HIPAA, and PCI controls. No per-asset fee, with unlimited targets.",
        cta: "Would you try it free for 30 days and share feedback? Useful to hear whether it fits the vCISO toolkit.",
      },
      {
        pitch:
          "We're launching HailBytes ASM, an attack surface management platform that's been getting interest from vCISO and compliance-led practices. Deploys into a client's own Azure or AWS tenant, correlates 30+ tools into one scan pipeline, produces executive-ready risk reports via AI, and has full audit logging for SOC 2, HIPAA, and PCI programs. No per-asset fee at any tier.",
        cta: "Free 30-day trial in exchange for honest feedback. Interested?",
      },
    ],
  },
  "hb-sat-training": {
    defaultTopic: "security awareness training and phishing simulation",
    variants: [
      {
        pitch:
          "I'm launching HailBytes SAT, a security awareness training and phishing simulation platform built for firms that deliver SAT to their clients. It runs in your own Azure or AWS tenant (no client data in a vendor cloud), is Entra ID native with SCIM, has AI-assisted template generation, and critically, no per-user fee. Unlimited users on a single VM.",
        cta: "Would you try it free for 30 days and share feedback? I'd love to hear from a firm that actually runs awareness programs.",
      },
      {
        pitch:
          "We're launching HailBytes SAT, a phishing simulation and security awareness training platform for MSSPs, consultancies, and training providers that deliver SAT as a service. One VM in your (or your client's) cloud tenant supports up to 5,000 users with no per-user licensing. AI-assisted template generation, Entra ID SSO, and webhook-driven SIEM integration are built in.",
        cta: "Free 30-day trial. Would you try it and share feedback? Happy to set up a demo.",
      },
    ],
  },
  "hb-asm-generic": {
    defaultTopic: "cybersecurity services",
    variants: [
      {
        pitch:
          "I'm launching HailBytes ASM, an attack surface management platform built for cybersecurity firms that want to add continuous external recon to their client offerings. It runs in your own cloud tenant, chains 30+ recon and vulnerability tools into one automated pipeline, has AI-powered triage, and charges no per-asset fee, with unlimited targets at every tier. We're also launching HailBytes SAT (phishing simulation, no per-user fee) in the same family, in case that's a closer fit.",
        cta: "Free 30-day trial of either in exchange for feedback. Which would be the better fit for your team?",
      },
      {
        pitch:
          "We're launching two platforms aimed at cybersecurity firms: HailBytes ASM (attack surface management, 30+ tools, unlimited targets, no per-asset fee) and HailBytes SAT (phishing simulation and awareness training, unlimited users, no per-user fee). Both deploy into your own Azure or AWS tenant, so client data stays in your cloud.",
        cta: "We're offering a free 30-day trial of either in exchange for honest feedback. Would one fit your current service mix better than the other?",
      },
    ],
  },
};

// ---- Page-type classifier --------------------------------------------------
//
// Deterministic URL/title inspection. Returns one of:
//   service_page | homepage | contact_page | article | off_topic | other
// Match order matters — `off_topic` must short-circuit before anything else
// so we don't bother drafting for domains we've already flagged as junk.

const OFF_TOPIC_DOMAIN_FRAGMENTS = [
  "thetinyclosetshop",
  "junkfoodclothing",
  "juliannarae",
  "quora.com",
  "reddit.com",
  "hdcopywriting",
];

const CONTACT_LAST_SEGMENTS = new Set([
  "contact",
  "contact-us",
  "contact_us",
  "hiring-us",
  "get-in-touch",
  "reach-us",
  "get-more-info",
]);

const ARTICLE_PATH_FRAGMENTS = [
  "/blog/",
  "/news/",
  "/insights/",
  "/articles/",
  "/post/",
  "/posts/",
  "/resources/",
  "/knowledge-base/",
  "/learn/",
  "/guide/",
  "/guides/",
  "/white-paper",
  "/whitepaper",
  "/ebook",
  "/case-stud",
  "/webinar",
];

const ARTICLE_TITLE_RE =
  /^(how to|what is|what are|why |when |the \d|\d+ ways|top \d|ways to|guide to|\d+ best)/i;

const CONTACT_URL_RE = /\/contact($|\/|-us|_us|\?)/i;

export function classifyPageType(url, title) {
  const u = (url || "").toLowerCase().replace(/\/+$/, "");
  const t = (title || "").toLowerCase();
  const lastSeg = u.includes("/") ? u.slice(u.lastIndexOf("/") + 1) : "";

  if (OFF_TOPIC_DOMAIN_FRAGMENTS.some((d) => u.includes(d))) return "off_topic";

  if (
    CONTACT_URL_RE.test(u) ||
    CONTACT_LAST_SEGMENTS.has(lastSeg) ||
    (lastSeg.includes("contact") && lastSeg !== "contact-form") ||
    u.includes("get-in-touch")
  ) {
    return "contact_page";
  }

  if (/^https?:\/\/[^/]+$/.test(u)) return "homepage";

  if (ARTICLE_PATH_FRAGMENTS.some((p) => u.includes(p))) return "article";
  if (ARTICLE_TITLE_RE.test(t)) return "article";

  if (/^https?:\/\/[^/]+\/.+/.test(u)) return "service_page";

  return "other";
}

// ---- Topic normalization ---------------------------------------------------
//
// Scans title + seed query for canonical topic phrases. The canonical strings
// are chosen to read naturally in all three opener frames:
//   "your work on {topic}", "working on {topic}", "write-up on {topic}".
// If you add new topics, sanity-check them in those three slots.
//
// Order matters — earlier matchers win. More-specific acronyms are listed
// before broader phrases (e.g. "SOC 2" before "SOC-as-a-Service").

const TOPIC_MATCHERS = [
  { re: /NIST\s*800-171\b/i, topic: "NIST 800-171" },
  { re: /\bCMMC\b/i, topic: "CMMC" },
  { re: /\bPCI[- ]?DSS\b/i, topic: "PCI DSS" },
  { re: /\bSOC\s*2\b/i, topic: "SOC 2" },
  { re: /\bISO\s*27001\b/i, topic: "ISO 27001" },
  { re: /\bHIPAA\b/i, topic: "HIPAA" },
  { re: /\bHITRUST\b/i, topic: "HITRUST" },
  {
    re: /\b(virtual\s*CISO|vCISO|CISO[- ]as[- ]a[- ]Service|fractional\s*CISO)\b/i,
    topic: "vCISO services",
  },
  { re: /\b(managed\s*detection\s*(and|&)\s*response|MDR)\b/i, topic: "MDR" },
  {
    re: /\b(SOC[- ]as[- ]a[- ]Service|SOCaaS|SOC\s+in\s+a\s+Box)\b/i,
    topic: "SOC-as-a-Service",
  },
  { re: /\bmanaged\s*SIEM\b/i, topic: "managed SIEM" },
  { re: /\bXDR\b/i, topic: "XDR" },
  { re: /\bMSSPs?\b/i, topic: "MSSP services" },
  { re: /\bpurple\s*team\b/i, topic: "purple team assessments" },
  { re: /\bred\s*team\b/i, topic: "red team assessments" },
  { re: /\badversary\s*emulation\b/i, topic: "adversary emulation" },
  { re: /\bphysical\s*pen(etration)?\s*test/i, topic: "physical penetration testing" },
  { re: /\bsocial\s*engineering\b/i, topic: "social engineering assessments" },
  { re: /\bphishing\s*simulation\b/i, topic: "phishing simulation" },
  { re: /\bphishing\s*test(ing)?\b/i, topic: "phishing testing" },
  {
    re: /\b(security\s*awareness\s*training|awareness\s*training)\b/i,
    topic: "security awareness training",
  },
  { re: /\b(pen(etration)?\s*test(ing)?|pentest(ing)?)\b/i, topic: "penetration testing" },
  { re: /\boffensive\s*security\b/i, topic: "offensive security" },
  {
    re: /\b(attack\s*surface\s*management|ASM|CTEM|continuous\s*threat\s*exposure)\b/i,
    topic: "attack surface management",
  },
  {
    re: /\bcontinuous\s*(risk\s*scanning|monitoring|exposure)\b/i,
    topic: "continuous external monitoring",
  },
  { re: /\bvulnerability\s*management\b/i, topic: "vulnerability management" },
  { re: /\bshadow\s*IT\b/i, topic: "shadow IT discovery" },
  { re: /\bGRC\b/i, topic: "GRC services" },
];

export function normalizeTopic({ title, seed, templateId }) {
  const blob = `${title || ""} ${seed || ""}`;
  for (const { re, topic } of TOPIC_MATCHERS) {
    if (re.test(blob)) return topic;
  }
  return TEMPLATES[templateId]?.defaultTopic || "cybersecurity services";
}

// ---- Opener sentence per page type -----------------------------------------

export function buildOpener({ pageType, topic, company }) {
  switch (pageType) {
    case "service_page":
      return `Came across your work on ${topic} while researching firms in the space.`;
    case "homepage":
      return `Came across ${company} while researching firms working on ${topic}.`;
    case "contact_page":
      return `Reaching out directly — I've been researching firms working on ${topic} and wanted to get in touch.`;
    case "article":
      return `Came across your write-up on ${topic} while researching firms in the space.`;
    case "off_topic":
      return "";
    case "other":
    default:
      return `I've been researching firms working on ${topic} and wanted to reach out.`;
  }
}

// ---- Draft assembly --------------------------------------------------------

function hash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

// "hailbytes.com" → "HailBytes"; "pentest-pros.com" → "Pentest Pros".
// Used for the `{company}` slot (homepage opener) and the greeting.
// Falls back to "" when no domain is available.
function companyFromDomain(domain) {
  if (!domain) return "";
  const base = domain.split(".")[0].replace(/[-_]+/g, " ").trim();
  if (!base) return "";
  return base
    .split(" ")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

function greetingName(company) {
  return company ? `${company} team` : "there";
}

function buildDraft({ company, opener, pitch, cta }) {
  const greeting = greetingName(company);
  const introBody = opener ? `David McHale from HailBytes here. ${opener} ${pitch}` : pitch;
  return `Hi ${greeting},

${introBody}

${cta}

${SIGN_OFF}`;
}

// ---- Public API ------------------------------------------------------------

export function pickTemplate(result, { seed = "" } = {}) {
  const blob = `${result.title || ""} ${result.summary || ""} ${result.domain || ""}`;
  const bucket = BUCKETS.find((b) => b.pattern.test(blob));
  const templateId = bucket ? bucket.id : "hb-asm-generic";
  const pageType = classifyPageType(result.url, result.title);
  const company = companyFromDomain(result.domain);

  // Off-topic: the upstream pre-filter in find-leads-hailbytes.mjs should
  // have dropped these, but if one slips through we still want a stable
  // marker + empty draft so human triage can delete the row cleanly.
  if (pageType === "off_topic") {
    return { templateId: "off-topic", draft: "", pageType };
  }

  const { variants } = TEMPLATES[templateId];
  const idx = hash(result.url || "") % variants.length;
  const { pitch, cta } = variants[idx];
  const topic = normalizeTopic({ title: result.title, seed, templateId });
  const opener = buildOpener({ pageType, topic, company });
  const draft = buildDraft({ company, opener, pitch, cta });
  return { templateId, draft, pageType };
}
