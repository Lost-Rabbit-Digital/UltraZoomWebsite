# Exa Queries — Ultra Zoom lead discovery

Natural-language queries used by `scripts/find-leads.mjs` (search mode). Exa
is semantic, not keyword, so write these the way you'd describe the article
you want to an intern, not as Google operators. Think: "a blog post that…".

**Parsing rules for `find-leads.mjs`:**
- `## Heading` defines a section (used by `--sections` regex filter).
- Each `-` bullet is one query. Wrapping quotes are stripped.
- Blockquotes (`>`) are notes/context, ignored by the parser.

**Two complementary engines:**
- **This file** drives *topic discovery*: "find me articles about X".
- **`leads.json` via `--mode find-similar`** drives *shape discovery*: "find
  me more articles that look like the 30 we already curated." That second
  lane usually outperforms the first — when in doubt, run `find-similar`.

---

## Listicle roundups (generic)

- a blog post listicle of the best Chrome browser extensions published in the last year
- a blog post listing must-have Firefox add-ons for power users
- an article titled "browser extensions I use every day" from an indie developer
- a 2026 roundup of underrated Chrome extensions
- a "best paid Chrome extensions worth buying" blog post
- a personal blog post about favorite browser extensions for productivity

## Photography and design

- a listicle of the best Chrome extensions for photographers
- a blog post about browser tools for graphic designers who use Pinterest and Behance
- an article recommending Chrome extensions for moodboard research
- a design blog post about tools for finding visual inspiration online
- a roundup of browser extensions for stock photo research
- a blog about Dribbble and Behance workflow tools

## Online shopping, eBay, Amazon, auctions

- a blog post listing Chrome extensions that help with online shopping on Amazon and eBay
- an article about tools for eBay sellers and flippers to inspect listing photos
- a blog post with browser extensions for dropshippers researching suppliers
- an article about tools collectors use to inspect auction listing photos
- a coin or stamp collecting blog discussing browser tools for photo inspection
- a roundup of browser extensions for online auction bidders

## Real estate research

- a blog post about Chrome extensions that help with Zillow and Redfin home shopping
- an article listing browser tools for first-time home buyers
- a real estate agent blog post about tools to review listing photos faster
- a house-hunting tips article that mentions browser extensions

## Genealogy and family history

- a blog post listing Chrome extensions useful for genealogy research on Ancestry and FamilySearch
- an article about browser tools for reviewing digitized family history documents
- a genealogy blog post about tools to inspect scanned census records and old photos
- a family history research tips article mentioning browser-based tools

## Privacy and security

- a blog post about privacy-respecting Chrome extensions with no telemetry
- an article about browser extensions that got caught selling user browsing data
- a 2026 roundup of privacy-first browser extensions
- a blog post about Hover Zoom's privacy scandal and its alternatives
- an article about zero-knowledge browser extension architecture

## Accessibility

- a blog post about browser extensions that help low-vision users zoom in on images
- an accessibility blog post listing assistive browser tools
- an article about visual impairment accommodations using browser extensions

## Productivity and power users

- a Medium post titled "the chrome extensions I install on every new machine"
- a Substack newsletter about favorite browser extensions
- a personal blog "tools I use" post that includes browser extensions
- a 2026 article about the most underrated Chrome extensions nobody knows about
- a productivity blog post about saving time with browser extensions

## Hover Zoom and Imagus alternatives (warmest leads)

- a blog post reviewing Hover Zoom Plus or listing its alternatives
- an article comparing image-zoom Chrome extensions like Imagus
- a review of hover-to-zoom browser extensions for Chrome or Firefox
- a blog post about the best image zoom extensions in 2026

## Developer and engineering blogs

- a web engineering blog post about Chrome extension development
- an article about Manifest V3 and its impact on Chrome extensions
- a developer blog about browser extension performance and bundle size
- a Preact or React blog post about building browser UIs

## Teachers, librarians, and educators

- a teacher blog post about Chrome extensions for the classroom
- an article listing browser extensions for K-12 educators
- a librarian blog post recommending browser tools for digital reference work
- a school library blog about Chrome extensions for student research
- a roundup of Chrome extensions for higher education instructors
- a blog post about browser extensions that help with grading and lesson planning
- an EdTech blog post about must-have Chrome extensions for 2026

## Academic researchers and grad students

- a grad student blog post about Chrome extensions for academic research
- a digital humanities blog about browser tools for archival research
- an article about Chrome extensions for reading and annotating PDFs in research
- a researcher's "tools I use" Substack post mentioning browser extensions
- a librarian blog post about browser tools for working with digitized manuscripts

## Writers, editors, and translators

- a writer's blog post titled "the chrome extensions in my writing toolkit"
- a freelance editor's blog post recommending browser extensions
- a translator blog post about Chrome extensions for translation work
- a journalist's "my workflow" post that mentions browser extensions
- a Substack newsletter from a working writer about their tool stack

## Newsletter curators and "tool of the week" pubs

- a Substack newsletter that reviews a new browser extension each week
- a weekly tools newsletter mentioning a Chrome extension worth trying
- a beehiiv newsletter about productivity tools that includes browser extensions
- a "tool of the week" blog post featuring a Chrome extension
- an indie newsletter post titled "my favorite finds this month" with browser tools

## YouTube and video creators (description-box outreach)

- a YouTuber's blog post mirroring their "best chrome extensions" video
- a video creator's article reviewing browser extensions for content production
- a screencaster blog about Chrome extensions used in their tutorials

## International / non-English

- a German blog post titled "die besten Chrome Erweiterungen 2026"
- a French article listing "meilleures extensions Chrome" for productivity
- a Japanese blog post reviewing image-zoom Chrome extensions
- a Spanish blog post about "mejores extensiones de Chrome" for online shopping
- a Portuguese blog post recommending browser extensions for designers

## Marketers, social media, and ecommerce operators

- a digital marketer blog post about Chrome extensions for SEO and content research
- an article listing Chrome extensions for social media managers and community managers
- a Shopify or BigCommerce blog about browser extensions for ecommerce sellers
- an Amazon FBA seller's blog post about browser tools for product research
- an affiliate marketer blog post listing must-have Chrome extensions

## Lawyers, paralegals, and other office professionals

- a legaltech blog post about Chrome extensions for lawyers and paralegals
- an article listing browser extensions for accountants and bookkeepers
- a blog post about Chrome extensions for project managers and consultants

## Seasonal and gift-guide angles

- a 2026 holiday gift guide that includes browser extensions or productivity tools
- a back-to-school blog post listing Chrome extensions for students
- a "new year, new browser setup" article with extension recommendations

---

## Tips for editing this file

- If a section consistently returns junk, tighten the language — Exa rewards
  specificity. "A blog post that lists browser extensions specifically for
  coin collectors" beats "coin collector tools".
- Prefer *describing the shape* ("listicle", "personal blog post", "Substack
  newsletter") over topic alone — it filters out vendor pages and forums.
- Rotate year tokens ("2025", "2026") as time passes.
- If a lead from `find-similar` is especially high-quality, add a new query
  here that describes its shape so `search` mode can find more like it.
