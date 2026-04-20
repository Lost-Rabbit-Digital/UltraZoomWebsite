# Outreach Search Dorks — Ultra Zoom

A reference of Google / Bing / DuckDuckGo search operators ("dorks") for building the outreach prospect list. Paste any of these into the search bar and swap in year, niche, or platform tokens as needed.

Used alongside `iteration-prompt.md` to feed the research loop.

---

## Legend

- `YEAR` — current year, rotate `2025`, `2026`, and "latest"
- `NICHE` — target audience (designers, students, photographers, genealogists, collectors, real-estate-agents, etc.)
- `BLOG_SPEAR` — which Ultra Zoom blog post you'd pitch with the lead
- Quotes force exact match, minus signs exclude terms, `site:` scopes a domain, `inurl:` matches URL tokens, `intitle:` matches the `<title>`

---

## 1. Listicle / roundup dorks (generic coverage)

```
"best chrome extensions" YEAR -site:google.com -site:chromewebstore.google.com
"best firefox add-ons" YEAR -site:mozilla.org -site:addons.mozilla.org
"must-have browser extensions" YEAR intitle:"best"
"top chrome extensions" YEAR "hover"
inurl:blog intitle:"best chrome extensions" YEAR
inurl:blog "chrome extensions" NICHE YEAR
"chrome extensions for" NICHE YEAR -site:chrome.google.com
"our favorite chrome extensions" YEAR
"extensions we use every day" YEAR
"chrome extensions you should be using" YEAR
```

## 2. Long-tail niche dorks (higher reply rate)

```
"chrome extensions for designers" YEAR
"chrome extensions for photographers" YEAR
"chrome extensions for genealogists" YEAR OR "for family history"
"chrome extensions for coin collectors" OR "for numismatists"
"chrome extensions for real estate agents" YEAR
"chrome extensions for online shopping" YEAR
"chrome extensions for students" YEAR
"chrome extensions for researchers" YEAR
"chrome extensions for ecommerce" YEAR
"chrome extensions for social media managers" YEAR
"chrome extensions for accessibility" OR "accessibility chrome extensions"
"chrome extensions for art history" OR "museum research"
"firefox extensions for" NICHE YEAR
```

## 3. Independent-blogger dorks (higher personal response rate)

```
site:medium.com "best chrome extensions" YEAR
site:dev.to "chrome extensions" NICHE YEAR
site:substack.com "browser extensions" NICHE
site:hashnode.com "chrome extensions" NICHE
site:wordpress.com "best chrome extensions" YEAR
intitle:"my favorite chrome extensions" YEAR
intitle:"extensions I use daily" YEAR
intitle:"chrome extensions I can't live without"
```

## 4. Use-case content (spear with our use-case blog posts)

For pitching the `collector-auction-photo-zoom`, `designer-moodboard-hover-zoom`, `genealogy-archive-photo-zoom`, `online-shopping-product-photo-zoom`, and `real-estate-listing-photo-zoom` posts.

```
"inspecting listing photos" OR "inspecting product photos"
"how to bid on eBay" OR "how to evaluate auction photos"
"Zillow photo tips" OR "Redfin photo tips" OR "real estate photo red flags"
"Ancestry tips" OR "FamilySearch tips" site:blog.* OR inurl:blog
"Pinterest moodboard" OR "Dribbble tools" OR "Behance workflow"
"condition grading" coin OR stamp OR card
"authentication guide" "online" collectibles
"buying vintage online" tips
```

## 5. Privacy / security pubs (spear with `hover-zoom-privacy-scandal` + `zero-knowledge-architecture`)

```
"privacy-friendly extensions" YEAR
"open source chrome extensions" YEAR
"no tracking" browser extension review
"hover zoom" "spyware" OR "malware" OR "tracking"
"extensions that sold user data" OR "browser extension scandal"
site:restoreprivacy.com OR site:privacyguides.org OR site:bleepingcomputer.com "extension"
```

## 6. Engineering / build-quality pubs (spear with `manifest-v3-trap`, `bundle-budget`, `preact-over-react`, `native-browser-image-zoom`)

```
"Manifest V3" migration OR "MV3 migration"
"preact vs react" bundle size extension
"browser extension bundle size" OR "extension performance"
site:smashingmagazine.com "chrome extension"
site:css-tricks.com "browser extension" OR "chrome extension"
site:web.dev "extension"
site:dev.to "manifest v3"
site:blog.logrocket.com "extension"
"why native browser zoom" OR "image zoom UX"
```

## 7. Accessibility pubs

```
site:a11yproject.com "extension" OR "tool"
"low vision" browser tools
"accessibility extensions" chrome OR firefox
"magnifier" browser extension
"screen magnification" browser
site:tpgi.com OR site:dequeuniversity.com OR site:webaim.org "extension"
```

## 8. YouTube & video (description-box links)

```
site:youtube.com "best chrome extensions" YEAR
site:youtube.com "chrome extensions for" NICHE
site:youtube.com "firefox extensions" YEAR
"chrome extensions review" inurl:watch
```

## 9. Newsletter / Substack finds

```
site:substack.com "chrome extensions"
site:substack.com "tools I use" extension
site:beehiiv.com "browser extensions"
"buttondown.email" "chrome extensions"
```

## 10. Journalist / reporter finds

```
site:techcrunch.com "chrome extension" YEAR
site:theverge.com "chrome extension" YEAR
site:arstechnica.com "chrome extension"
site:zdnet.com "chrome extension"
site:bleepingcomputer.com "chrome extension"
site:neowin.net "chrome extension"
```

## 11. Contact-info finding (after you have a lead)

```
"FIRSTNAME LASTNAME" "PUBLICATION" email
"FIRSTNAME LASTNAME" site:twitter.com OR site:x.com
"FIRSTNAME LASTNAME" site:linkedin.com/in
site:PUBLICATION.com "contact" OR "about" OR "pitch"
site:PUBLICATION.com "tips@" OR "editorial@" OR "press@"
"@PUBLICATION.com" FIRSTNAME
"I can be reached at" "PUBLICATION.com"
```

Common reliable patterns to try in order:
1. `firstname@domain.tld`
2. `firstname.lastname@domain.tld`
3. `tips@domain.tld`, `editor@domain.tld`, `editorial@domain.tld`
4. `press@domain.tld`, `pr@domain.tld`, `contact@domain.tld`
5. `hello@domain.tld`, `hey@domain.tld`

## 12. Backlink / mention tracking (post-launch)

```
"ultra zoom" extension chrome OR firefox -site:ultrazoom.app
"ultrazoom.app" -site:ultrazoom.app
"hover to zoom extension" YEAR -site:chromewebstore.google.com
link:ultrazoom.app  (deprecated, but try the Bing equivalent)
```

---

## Prospect categories we're still thin on

As of the last iteration, these categories have **< 5 leads** in `leads.json`. Bias new research toward these:

- Collector / auction blogs (coins, stamps, cards, vintage)
- Genealogy and family-history blogs
- Real estate / property blogs
- Photographers, photo-editing, stock-photo blogs
- Privacy / infosec publications
- Engineering / browser-extension-dev publications
- Art historians, museum-research blogs
- Accessibility publications (have 2, want 8+)
- Journalists covering browser news
- YouTube channels reviewing extensions

## Target: 300 prospects total

Running tally lives in `leads.json`. Each iteration should add 20-50 verified prospects until we hit 300 so the send cadence (10/day) covers a full month.
