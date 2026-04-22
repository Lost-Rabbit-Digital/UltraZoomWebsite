// Pick a contact-form template + draft a short message from a discovery result.
//
// Canonical human-readable templates live in docs/outreach/contact-form-templates.md.
// The drafts below mirror them as short, form-safe variants (no markdown, one URL,
// ~500 chars) so the `message_draft` column is copy-paste-ready. Humans can edit
// or swap templates during triage — this is a starting point, not a final message.
//
// Rotation: two variants per bucket, selected deterministically from a hash of
// the URL. Same lead → same draft across re-runs; across leads we alternate.

const SIGN_OFF = "— Boden Garman, Lost Rabbit Digital LLC\nhttps://ultrazoom.app";

const BUCKETS = [
  {
    id: "form-genealogy",
    pattern: /\b(genealog|ancestry|familysearch|findagrave|find a grave|census|archive\.org|old photos?|family history)\b/i,
  },
  {
    id: "form-real-estate",
    pattern: /\b(zillow|redfin|realtor|real[-\s]?estate|house[-\s]?hunt|home[-\s]?buyer|mortgage|property listing)\b/i,
  },
  {
    id: "form-shopping",
    pattern: /\b(ebay|amazon|dropship|reseller|resell|auction|online shopping|deal hunter|product research)\b/i,
  },
  {
    id: "form-photo-design",
    pattern: /\b(photograph|designer|pinterest|dribbble|behance|moodboard|mood board|figma|reference image|visual research)\b/i,
  },
  {
    id: "form-privacy",
    pattern: /\b(privacy|tracking|telemetry|surveillance|anti[-\s]?fingerprint|data broker|zero[-\s]?knowledge)\b/i,
  },
  {
    id: "form-listicle",
    pattern: /\b(best\s+(chrome|firefox|edge|brave|browser)\s+extensions?|must[-\s]?have\s+extensions?|extensions?\s+(i\s+use|to\s+try|for\s+\w+)|top\s+\d+\s+extensions?)\b/i,
  },
];

const TEMPLATES = {
  "form-genealogy": [
    ({ title }) =>
`Hi there,

Found your "${title}" while looking for genealogy research tools worth sharing. Wanted to share one back: Ultra Zoom.

It's a free hover-to-zoom browser extension. On Ancestry, FamilySearch, Findagrave, and 50+ other sites you hover a scanned document or photo and see the full-resolution image instantly — no modal, no re-loading. Saves a lot of clicks when reviewing census pages or old photos. Chrome + Firefox, no tracking.

If it's useful to your readers, a mention would mean a lot.

${SIGN_OFF}`,
    ({ title }) =>
`Hi,

"${title}" came up while I was researching tools the genealogy community actually uses. Thought I'd flag Ultra Zoom in case it's a fit for a future roundup.

It's a hover-to-zoom extension (Chrome + Firefox, free, no tracking). Hover thumbnails on Ancestry, FamilySearch, Findagrave or scanned archive pages and the full-resolution image pops up immediately. Makes long research sessions much less click-heavy.

Happy to share example workflows if useful.

${SIGN_OFF}`,
  ],
  "form-real-estate": [
    ({ title }) =>
`Hi,

Came across "${title}" and wanted to flag a browser tool that fits well with house-hunting research: Ultra Zoom.

It's a free hover-to-zoom extension for Chrome and Firefox. On Zillow, Redfin, Realtor.com, and 50+ other sites you hover any listing photo and see the full-size image — no lightbox, no clicking through 40 photos individually. Much faster for filtering homes at the shortlist stage.

If it's worth a mention, I'd be grateful. Can share a short GIF of the Zillow workflow.

${SIGN_OFF}`,
    ({ title }) =>
`Hi there,

Your "${title}" popped up while I was looking for resources people actually recommend to house-hunters. Wanted to flag Ultra Zoom.

Free Chrome/Firefox extension, hover-to-zoom on Zillow, Redfin, Realtor.com and 50+ other sites — skip the lightbox, see the full-res listing photo instantly. Makes the shortlisting phase a lot less tedious.

Can send a quick GIF if it helps.

${SIGN_OFF}`,
  ],
  "form-shopping": [
    ({ title }) =>
`Hi,

I read your "${title}" piece — useful for anyone who spends time sourcing on eBay or Amazon. Wanted to flag a tool that fits the workflow: Ultra Zoom.

It's a hover-to-zoom browser extension. Hover a listing thumbnail on eBay, Amazon, and dozens of other shopping sites and you see the full-resolution photo — no click-through, no back-button dance. Really handy for inspecting condition on used items. Free, Chrome + Firefox.

If it's a fit, I'd love a mention. Can send a GIF on request.

${SIGN_OFF}`,
    ({ title }) =>
`Hi there,

"${title}" came up while I was researching resources for people who research before they buy. Wanted to share Ultra Zoom in case it's worth covering.

Free Chrome/Firefox extension — hover a thumbnail on eBay, Amazon, or 50+ other shopping sites and instantly see the full-resolution listing photo. No click, no new tab. Saves real time when comparing used items side by side.

Happy to send screenshots if useful.

${SIGN_OFF}`,
  ],
  "form-photo-design": [
    ({ title, publication }) =>
`Hi ${publication} team,

Your "${title}" post popped up while I was researching tools for image-heavy workflows. Wanted to share Ultra Zoom in case it's worth a mention in a future update.

It's a hover-to-zoom browser extension that previews full-size images on Pinterest, Behance, Dribbble, Google Images, and 50+ other sites without opening a new tab. Makes moodboard browsing and reference hunting a lot faster. Free, no tracking, Chrome + Firefox.

Happy to send a GIF if it helps.

${SIGN_OFF}`,
    ({ title }) =>
`Hi,

Found "${title}" while researching visual-workflow tools worth recommending. Wanted to flag Ultra Zoom in case it fits a future piece.

Free Chrome/Firefox extension — hover any image on Pinterest, Behance, Dribbble, Google Images and 50+ other sites and you get the full-size preview immediately, no new tab. Reference hunting and moodboard browsing get noticeably less click-heavy. No tracking, runs client-side.

Can share a quick GIF of the Pinterest workflow.

${SIGN_OFF}`,
  ],
  "form-privacy": [
    ({ title }) =>
`Hi,

Your "${title}" came up while I was looking for privacy-minded publications. Wanted to share a project that fits the angle: Ultra Zoom.

It's a hover-to-zoom browser extension, which is a category with an ugly history (the original Hover Zoom was caught selling browsing data in 2014). Ultra Zoom is the counter-argument: zero telemetry, no analytics, no history collection, no third-party servers — everything runs in-browser. Chrome and Firefox, free with optional Pro.

Happy to walk through the architecture if useful.

${SIGN_OFF}`,
    ({ title }) =>
`Hi there,

"${title}" came up in my research and I wanted to flag Ultra Zoom in case the privacy angle is interesting to you.

Hover-to-zoom extensions have a long history of shipping telemetry (the original Hover Zoom sold browsing data). Ultra Zoom takes the opposite approach — zero telemetry, no analytics, no remote servers, everything runs locally. Chrome + Firefox, free tier covers everyone.

Glad to answer anything if you cover the category.

${SIGN_OFF}`,
  ],
  "form-listicle": [
    ({ title, section }) =>
`Hi there,

I came across your piece "${title}" while researching browser extension roundups and wanted to flag one that fits the ${section} section: Ultra Zoom, a hover-to-zoom extension for Chrome and Firefox.

It works on 60+ sites (Google Images, Amazon, Reddit, Pinterest, eBay, Zillow, Ancestry, etc.) — hover any thumbnail, see the full-size image, no click, no new tab. Free, no tracking, client-side only.

If it's useful, I'd be grateful for a mention. Happy to send screenshots or a GIF.

${SIGN_OFF}`,
    ({ title, section }) =>
`Hi,

Found "${title}" while researching extension roundups and wanted to flag one I think fits the ${section} angle: Ultra Zoom.

Free Chrome + Firefox extension, hover-to-zoom on 60+ sites — Google Images, Amazon, Reddit, Pinterest, eBay, Zillow, Ancestry and more. Hover a thumbnail, see the full-size image, no click or new tab. Client-side only, no tracking.

Happy to send a GIF or screenshots if helpful.

${SIGN_OFF}`,
  ],
  "form-generic": [
    ({ title }) =>
`Hi,

Found you through "${title}" and wanted to briefly introduce a project that might be a fit for your audience: Ultra Zoom, a hover-to-zoom browser extension for Chrome and Firefox.

It works on 60+ websites — hover any image thumbnail, see the full-size image instantly, no click, no new tab. Free, privacy-first (no tracking), built by a small indie studio.

If it's something you'd consider covering, I'd love that. Can send screenshots, a GIF, or anything else useful.

${SIGN_OFF}`,
    ({ title }) =>
`Hi there,

"${title}" came up in my research and I wanted to briefly flag Ultra Zoom in case it's a fit for your audience.

Free hover-to-zoom extension for Chrome and Firefox — works on 60+ sites (Google Images, Amazon, Pinterest, eBay, Zillow, Ancestry, and more). Hover a thumbnail, see the full-size image, no click, no new tab. No tracking, built by a small indie studio.

Happy to send a GIF or answer anything useful.

${SIGN_OFF}`,
  ],
};

function hash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

// Turn "pinchofyum.com" → "Pinchofyum", "tech-crunch.com" → "Tech Crunch".
// Good enough for a greeting; humans retouch during triage.
function publicationFromDomain(domain) {
  if (!domain) return "there";
  const base = domain.split(".")[0].replace(/[-_]+/g, " ").trim();
  if (!base) return "there";
  return base
    .split(" ")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ");
}

// Best-effort section label for listicle drafts ("productivity", "design", …).
// Falls back to a neutral word so the draft always reads.
function sectionFromTitle(title) {
  const t = (title || "").toLowerCase();
  if (/\b(productivity|workflow|focus)\b/.test(t)) return "productivity";
  if (/\b(design|designer|creative)\b/.test(t)) return "design";
  if (/\b(image|photo|visual|picture)\b/.test(t)) return "image tools";
  if (/\b(shopping|deals|buyer|sourcing)\b/.test(t)) return "shopping";
  if (/\b(research|study|scholar|academic)\b/.test(t)) return "research";
  if (/\b(privacy|security|safety)\b/.test(t)) return "privacy";
  return "productivity";
}

export function pickTemplate(result) {
  const blob = `${result.title || ""} ${result.summary || ""} ${result.domain || ""}`;
  const bucket = BUCKETS.find((b) => b.pattern.test(blob));
  const id = bucket ? bucket.id : "form-generic";
  const variants = TEMPLATES[id];
  const idx = hash(result.url || "") % variants.length;
  const draft = variants[idx]({
    title: result.title || "",
    publication: publicationFromDomain(result.domain),
    section: sectionFromTitle(result.title),
  });
  return { templateId: id, draft };
}
