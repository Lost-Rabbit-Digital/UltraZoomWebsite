# Cold-opener rules — HailBytes outreach

The `find-leads-hailbytes.mjs` pipeline scrapes four very different kinds of
pages: service pages (~55%), homepages (~30%), contact pages (~8%), and
articles (~7%). A single opener like "Saw your `{TITLE}` piece…" reads fine
for articles but becomes nonsense for the other three buckets (e.g. "Saw your
`Contact Us – x1itservices.com` piece"), which is an obvious tell that the
message is templated and that the sender didn't read anything.

This doc captures:
1. The page-type classifier + topic-normalizer the JS picker implements
   (`scripts/lib/template-picker-hailbytes.mjs`).
2. A drop-in LLM prompt, kept here for when any part of the drafting is moved
   behind a model call. Today's pipeline is deterministic JS; the prompt is
   reference-only.

## Page-type classifier (JS)

See `classifyPageType(url, title)` in
`scripts/lib/template-picker-hailbytes.mjs`. Returns one of:

- `off_topic` — apparel / copywriting / forum domains (also pre-filtered in
  `find-leads-hailbytes.mjs` so rows never reach the sheet).
- `contact_page` — URL contains `/contact`, `contact-us`, `get-in-touch`, etc.
- `homepage` — bare `scheme://host`, no path.
- `article` — path under `/blog/`, `/insights/`, `/case-stud*`, etc., or
  title starting with "How to", "What is", "Top 10", etc.
- `service_page` — anything else with a non-empty path.
- `other` — true fall-through.

## Topic normalization (JS)

`normalizeTopic({ title, seed, templateId })` in the picker scans title +
seed query for canonical topic phrases before falling back to the bucket's
default topic. The canonical phrases are chosen to read naturally in all
three opener frames:

- `your work on {topic}` (service_page)
- `working on {topic}` (homepage / contact_page / other)
- `write-up on {topic}` (article)

Bucket-level defaults when no keyword matches:

| Bucket            | Default topic                                            |
|-------------------|----------------------------------------------------------|
| `hb-asm-mssp`     | MDR and managed security                                 |
| `hb-asm-vciso`    | vCISO and GRC services                                   |
| `hb-asm-pentest`  | offensive security                                       |
| `hb-asm-generic`  | cybersecurity services                                   |
| `hb-sat-training` | security awareness training and phishing simulation      |

If you add a new topic, sanity-check it in all three opener slots.

## Opener sentences by page type

| page_type      | Opener sentence                                                                                     |
|----------------|-----------------------------------------------------------------------------------------------------|
| `service_page` | `Came across your work on {topic} while researching firms in the space.`                            |
| `homepage`     | `Came across {company} while researching firms working on {topic}.`                                 |
| `contact_page` | `Reaching out directly — I've been researching firms working on {topic} and wanted to get in touch.` |
| `article`      | `Came across your write-up on {topic} while researching firms in the space.`                        |
| `off_topic`    | (skip — empty draft, flagged for manual removal)                                                    |
| `other`        | `I've been researching firms working on {topic} and wanted to reach out.`                           |

Intro line is standardized to `David McHale from HailBytes here.` across all
variants. The bare `David McHale here.` form was dropped because it
sometimes preceded a pitch that doesn't mention HailBytes at all.

## Optional enrichment for contact pages (not implemented)

Contact pages have the weakest opener because the scraped content is a form
and a phone number, so there's no page-specific signal to anchor against.
They're also the rows most likely to reach a real inbox, so they're worth
more effort when the budget allows.

Proposed flow:

1. For each `contact_page` row, run one domain-scoped search on
   `site:{domain}` for recent content.
2. Pick the highest-ranked result that is not the homepage, contact page,
   or a pricing/legal page.
3. Re-run `classifyPageType` + topic extraction on that new URL. If the
   result classifies as `article` or `service_page` with a non-default
   topic, use that URL's opener and topic.
4. Otherwise, fall back to the standard contact-page opener.

Enriched opener frames:

| Source page found | Opener sentence |
|-------------------|----------------|
| article           | `Came across your write-up on {enriched_topic} while researching firms working on {template_topic} — wanted to reach out directly since I hit your contact page.` |
| service_page      | `Came across your work on {enriched_topic} while looking for firms in the {template_topic} space — wanted to reach out directly.` |

Cost (~$0.007 × ~40 contact-page rows/run ≈ $0.30/run) is trivial if it
lifts reply rate. Needs A/B split vs. the plain contact-page opener before
rolling out.

## Data-quality flags (handled upstream)

`find-leads-hailbytes.mjs` drops two classes of rows before they reach the
sheet:

1. Domains in `SKIP_DOMAINS` — includes apparel stores
   (`thetinyclosetshop.com`, `junkfoodclothing.com`, `juliannarae.com`), a
   copywriting shop (`hdcopywriting.com`), and forum hosts (`quora.com`,
   `reddit.com`, `medium.com`) that the Exa/Brave clients don't already
   exclude globally.
2. Any title matching `OFF_TOPIC_TITLE_RE`
   (`sizing | fit guide | size chart | size & fit | apparel | clothing`),
   catching clothing fit-guides on new apparel domains.

The `classifyPageType` `off_topic` bucket is a belt-and-braces safety net
for anything that slips through.

---

## Drop-in LLM prompt

Kept here verbatim in case drafting is partially handed off to a model. Feed
the prompt the row data and have it return just the draft body.

```
You are drafting a cold outreach email from David McHale (HailBytes) to a cybersecurity firm.

INPUTS:
- company: {company_display}
- topic: {topic_normalized}           # e.g. "MDR", "penetration testing", "vCISO services"
- page_type: {page_type}              # one of: service_page, homepage, contact_page, article
- pitch: {template_pitch_paragraph}   # pre-written, do not alter
- cta: {template_cta_sentence}        # pre-written, do not alter

OPTIONAL (contact_page only — omit all three if enrichment was skipped or failed):
- enriched_page_type: {article | service_page}   # result of classifying the enriched URL
- enriched_topic: {topic_normalized}             # topic from the enriched page
- enriched_confidence: {high | low}              # low = fall back to standard contact_page opener

RULES:
1. Never quote the scraped page title. Never use the word "piece" unless page_type is "article".
2. Open with one of these exact sentence frames:
   - service_page → "Came across your work on {topic} while researching firms in the space."
   - homepage     → "Came across {company} while researching firms working on {topic}."
   - article      → "Came across your write-up on {topic} while researching firms in the space."
   - contact_page (no enrichment, or enriched_confidence=low) →
       "Reaching out directly — I've been researching firms working on {topic} and wanted to get in touch."
   - contact_page + enriched_page_type=article + enriched_confidence=high →
       "Came across your write-up on {enriched_topic} while researching firms working on {topic} — wanted to reach out directly since I hit your contact page."
   - contact_page + enriched_page_type=service_page + enriched_confidence=high →
       "Came across your work on {enriched_topic} while looking for firms in the {topic} space — wanted to reach out directly."
3. Do NOT add extra context, flattery, or claims about their work that weren't provided in the inputs.
4. Do NOT change the pitch or cta wording.
5. If enrichment inputs are present but `enriched_confidence` is low, ignore them and use the plain contact_page opener.
6. The draft MUST follow this structure exactly — greeting, blank line, intro paragraph (David McHale from HailBytes here. + opener + pitch), blank line, cta sentence, blank line, signature.

OUTPUT:
Hi {company} team,

David McHale from HailBytes here. <opener per rules above> <pitch>

<cta>

Thanks,
David McHale, HailBytes
https://hailbytes.com
```
