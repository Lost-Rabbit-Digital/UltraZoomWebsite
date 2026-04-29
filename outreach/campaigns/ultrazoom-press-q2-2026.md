# Ultra Zoom Press Outreach Campaign

**Status:** Pre-launch
**Target launch:** This week (after realtor track is sending cleanly)
**Owner:** David (strategy, pitch personalization, press relationships) / Boden (sending, replies)
**Last updated:** April 2026
**Sister campaign:** [`ultrazoom-realtors-q2-2026.md`](./ultrazoom-realtors-q2-2026.md) — runs from the same `boden@lostrabbitdigital.com` mailbox on alternating send days.

---

## TL;DR

60-day cold-email campaign to journalists, niche-blog operators, YouTube reviewers, and "best Chrome extensions for X" listicle operators, sending **up to 15 emails/day total** from `boden@lostrabbitdigital.com` on press send days (default T/Th). Goal: free Pro licenses for hands-on review and custom partner discount codes for revenue-share coverage. Drives traffic to the `/press` press kit. Net new monthly cost: $0 (shares MailMeteor seat with the Realtors campaign).

**Realistic volume:** press is hand-curated and quality-gated. Expect ~5–10 actual sends per press day, not 15. The 15/day cap is the safety ceiling for the mailbox; press will rarely approach it.

**Total prospect volume over 60 days:**
- ~80–120 unique press contacts (Touch 1 sends)
- ~160–240 total emails (with Touch 2 follow-ups for each)
- Active press send days: ~17 (assumes T/Th press cadence; adjust to Boden's calendar)

---

## Pre-Launch Checklist

Must complete before first press send. Some items overlap with the Realtors brief — the mailbox, DNS, Postmaster, and suppression list are shared. Don't duplicate that work.

- [ ] **Realtors campaign launched first** — let the mailbox prove out at 15/day on a single track before adding press alternation
- [ ] **`/press` press kit page** live (see Section 1)
- [ ] **Stripe coupon codes** `PRESS-FREE-12` and the `READER-{outlet}-30` template created (see Section 4)
- [ ] **Press contact email decided** — `press@ultrazoom.com` vs `david@ultrazoom.com` — and added to the press kit page
- [ ] **Founder bio + headshot** ready for the press kit
- [ ] **Boilerplate paragraph** written (different from the lede pitch, see Section 1)
- [ ] **First press batch hand-curated** — 10–15 contacts (see Section 6)
- [ ] **Google Sheet** for UZ Press created and shared (Editor) with the leads-writer service-principal email
- [ ] **`GOOGLE_SHEET_ID_UZ_PRESS` repo secret** added to UltraZoomWebsite
- [ ] **`outreach-ultrazoom` GitHub Action** updated to trigger on `outreach/inbox/ultrazoom-press/**` (delivered in Phase 6 of the rebuild)
- [ ] **Send-day rotation agreed with Boden** (default M/W/F realtor, T/Th press)

---

## 1. `/press` Press Kit Page

**Purpose:** Make journalists' jobs easy. Provide everything they need to write about Ultra Zoom without back-and-forth.

**URL:** `ultrazoom.com/press`

### Page structure

#### One-paragraph pitch (lede-ready)

TODO: Write 3-4 sentences a journalist can copy-paste verbatim. Must include:
- What Ultra Zoom is (Chrome extension, hover-zoom)
- Who it's for (real estate agents, insurance adjusters, e-commerce buyers, designers)
- What's novel vs. free hover-zoom extensions (works on sites where free ones fail — MLSs, claim platforms, marketplace seller dashboards)
- Built by (Lost Rabbit Digital)

#### Boilerplate paragraph

TODO: 2-3 sentences for "About Ultra Zoom" sections in articles. Different from lede pitch — this is the "About" footer copy.

#### Founder bio + headshot

- TODO: David McHale bio, 2-3 sentences, focused on relevant background
- TODO: High-res headshot

#### Product screenshots

- TODO: 4-6 high-res PNGs (1920x1080+)
- **Must use:** generic e-commerce sites, stock-licensed imagery, or your own properties
- **Must NOT use:** Disney/Marvel content, real estate listings without permission, anything copyrighted
- Show: hover state, settings panel, on different site types

#### Demo video

- TODO: 30-60 second YouTube embed
- Show core hover-zoom interaction on multiple site types
- Same video as `/realtors` page is fine

#### Key stats

TODO: Only include if flattering. Skip the entire section if numbers are still small.
- Active users / install count
- Notable customer types
- Growth metrics

#### Past coverage

TODO: Only include if exists. Product Hunt rankings, existing press mentions.

#### Partner with us section

> **Want to feature Ultra Zoom?**
>
> We offer custom discount codes for publications and creators who want to share Ultra Zoom with their readers. Each code is trackable, gives your audience a meaningful discount, and we can structure revenue share on a case-by-case basis.
>
> Email [press@ultrazoom.com or david@ultrazoom.com] to set up a partner code.

TODO: Decide on press contact email and add to copy.

#### Press contact

- TODO: Real human email — yours, not press@
- Response SLA: "We reply within 24 hours"

#### Asset downloads

- TODO: Logo PNG + SVG, light + dark variants
- TODO: Brand color hex codes
- TODO: Screenshot ZIP

---

## 2. Email Sequence

2-touch sequence, hand-personalized. Press has a higher quality bar than realtor, so the AI's job is to draft a skeleton; **Boden does final personalization research** before MailMeteor send.

**Send window:** press send days (default T/Th), 8am–6pm recipient local time
**Daily volume on a press day:** ≤15 cap (mailbox-level, shared with Realtors). Realistic press volume is 5–10/day given hand-research requirement.
**Mailbox sharing:** boden@lostrabbitdigital.com runs the Realtors campaign on non-press send days. Never run both campaigns on the same calendar day.

### Per-lead AI-drafted fields (per touch)

For each lead, the pipeline writes these fields to the row:

| Field | Length | Notes |
| --- | --- | --- |
| `personalized_subject` | ≤9 words | Includes publication name when available |
| `personalized_body` | 100–180 words | 5–7 sentences, ends with terminal punctuation |
| `specific_recent_topic` | (manual) | **Empty when AI stages the row.** Boden fills this column before MailMeteor send by reading 1–2 recent pieces by the recipient. Defaults to the publication's beat if Boden runs out of time. |
| `press_kit_link` | (resolved) | UTM-tagged `/press` URL |

The AI is given the lead's first name, title, publication, and any beat/topic signal from the Apollo CSV, plus the campaign brief's voice guidelines and the reference templates below. The body is written so it reads naturally whether `{{specific_recent_topic}}` is filled with a specific piece or a publication-beat fallback.

### Touch 1 — Day 0 (reference template)

**Subject (reference):** Pitch for {{publication}}: hover-zoom built for pros

**Body (reference):**

```
Hi {{first_name}},

Saw your work on {{specific_recent_topic}}. Good stuff.

Quick pitch: I built Ultra Zoom, a hover-zoom Chrome extension
for people who review images professionally (real estate agents,
insurance adjusters, e-commerce buyers). Different from the free
hover-zoom extensions because it works on the sites where the
others fail — MLSs, claim platforms, marketplace dashboards.

Press kit + demo: {{press_kit_link}}

Happy to send a free Pro license for hands-on review, or set
up a 15-min demo. If a "best Chrome extensions for [profession]"
piece fits your editorial calendar, I can offer your readers a
custom discount code for tracking.

David
Founder, Ultra Zoom
```

**Variables (resolved by the pipeline before staging):**
- `{{first_name}}` — Apollo `First Name`
- `{{publication}}` — Apollo `Company Name`
- `{{specific_recent_topic}}` — manually filled by Boden in the Sheet before MailMeteor send. **AI leaves the literal merge tag in place.**
- `{{press_kit_link}}` — `https://ultrazoom.com/press?utm_source=email&utm_campaign=press_w[N]&utm_content=touch1`

### Touch 2 — Day 5 (reference template)

**Subject (reference):** Re: Pitch for {{publication}}

**Body (reference):**

```
Hi {{first_name}},

Quick follow-up. Happy to make this easy. Free Pro license is
yours either way: {{license_signup_link}}

If a review or mention fits, let me know and I'll send a custom
reader discount code.

David
```

**Variables:**
- `{{license_signup_link}}` — Stripe checkout URL with `PRESS-FREE-12` coupon prefilled

### What the AI personalizes (and what it doesn't)

**Personalizes:**
- Opening line tied to the publication's beat (extensions, productivity, real-estate tech, browser tools)
- Phrasing of the value prop given the publication's audience (devs vs. realtors vs. designers)
- Subject line variant

**Does NOT personalize:**
- The literal `{{specific_recent_topic}}` merge tag — left for Boden to fill
- Coupon (`PRESS-FREE-12` for Touch 2)
- Press kit link template
- Signoff (`David / Founder, Ultra Zoom`)
- Voice constraints (no em-dashes, no sycophancy, ≤180 words)

### Boden's manual research checklist (per Touch 1 send)

Before importing Touch 1 to MailMeteor:

1. Open the lead's `linkedin_url` or publication URL
2. Find a piece they wrote in the last 60 days
3. Write 3–6 words describing the piece in the `specific_recent_topic` column (e.g. "your roundup of Chrome PDF tools")
4. If no recent piece in 5 minutes of searching, fall back to publication-level beat (e.g. "the productivity tooling work at Lifehacker")
5. Spot-check the AI's draft for accuracy before send

---

## 3. Stripe Coupon Setup

**Purpose:** Track campaign attribution, give press contacts a no-cost path to try the product, and enable revenue-share for partner coverage.

| Code | Discount | Audience | Duration | Redemption Limit |
|---|---|---|---|---|
| `PRESS-FREE-12` | 100% off Pro | Press hands-on review licenses | 12 months | 50 |
| `READER-{outlet}-30` | 30% off | Custom partner codes for publications | First 12 months | 100 per code |

### Setup steps (PRESS-FREE-12)

1. Stripe Dashboard → Products → Coupons → Create
2. Discount: 100% off Pro tier, recurring for 12 months
3. Redemption limit: 50
4. Expiration: campaign end date + 60 days
5. Generate a hosted Stripe checkout URL with the coupon prefilled — that becomes `{{license_signup_link}}` in the press Touch 2 template

### Custom partner codes (READER-{outlet}-30)

Create per-partner codes lazily — one when a partnership is agreed, not in advance. Each code follows the pattern `READER-{OUTLET}-30` (e.g. `READER-LIFEHACKER-30`, `READER-CHROMEUNBOXED-30`).

### Partner payout process (manual, no tooling)

When a press contact agrees to a partnership:

1. Create the custom code in Stripe Dashboard
2. Track in `outreach/partners.csv` (or the UZ Press Sheet's `Partners` tab): code, partner name, contact email, agreed revenue share %, payout method
3. Monthly: review Stripe → Coupons → individual code → Redemptions tab
4. Calculate revenue share (recommended: 30% of first-year revenue)
5. Pay via PayPal, Stripe Connect, or wire transfer
6. Email partner monthly report

### When this approach breaks

Around 20+ active partner codes, manual reconciliation gets painful. At that point, evaluate Rewardful ($49/mo) — by then you'll have data justifying the cost.

---

## 4. Sending Infrastructure

Same MailMeteor + `boden@lostrabbitdigital.com` setup as the [Realtors brief, Section 5](./ultrazoom-realtors-q2-2026.md#5-sending-infrastructure). The 15/day cap, Postmaster Tools monitoring, pause triggers, suppression-list discipline, and DNS records are all shared. **Don't duplicate that work — read the Realtors brief.**

The only press-specific note: press has a higher per-send research cost (Boden's manual `specific_recent_topic`), so realistic press volume is 5–10/day on press send days, not 15. The cap is a ceiling, not a target.

---

## 5. Apollo Manual Export

The pipeline no longer calls Apollo's API. Instead, run a saved Apollo People search in the UI for press contacts, hand-curate the export, and drop into the inbox folder.

### Saved search: `Ultra Zoom — Press — Q2 2026`

Press has weaker filter coverage in Apollo than realtor (Apollo's strength is B2B SaaS sellers, not journalists), so expect to **manually trim** the export.

**Sub-categories to source from:**
- Tech journalists at outlets that review extensions: Lifehacker, MakeUseOf, AddictiveTips, How-To Geek, TechRadar, Chrome Unboxed, OMG Chrome, The Next Web, Beebom, Ghacks
- Niche blog/newsletter operators in productivity, real-estate tech, browser tools
- YouTube reviewers in productivity/extension/reseller niches (Apollo is poor for this — supplement manually)
- Affiliate site / listicle operators ("Best Chrome Extensions for X" content creators)

**Apollo filter combination:**
- Job titles (Include): Editor, Senior Editor, Managing Editor, Staff Writer, Contributing Writer, Contributor, Tech Writer, Reviewer, Founder (for niche blogs/newsletters)
- Industries: Online Media, Publishing, Internet, Computer Software (for reviewer-adjacent staff)
- Company size: 1–500 (skip enterprises — niche blogs and individual reviewers are the right fit)
- Geography: United States, United Kingdom, Canada, Australia (English-language reviewers)
- Email status: Verified only

**Volume target:** export 30–50 raw rows per week. Manually trim to 10–15 hand-picked before dropping in the inbox folder. Quality drops fast past the top 50 in any Apollo press search.

### Export workflow

1. Run the saved Apollo search
2. Apollo will return more rows than you should send — that's expected
3. **Manually filter** in Apollo's UI or the exported CSV: drop anyone whose recent work is unrelated to extensions/productivity/the verticals UZ cares about, drop anyone at a paywalled outlet you don't read, drop generic "social media manager" type roles that slipped through
4. Save the trimmed file to `outreach/inbox/ultrazoom-press/<YYYY-MM-DD>.csv` on the active branch
5. Commit + push the branch. The `outreach-ultrazoom` GitHub Action triggers on push to `outreach/inbox/ultrazoom-press/**`
6. The Action populates two tabs in the UZ Press Sheet: `UZ_Press_T1` and `UZ_Press_T2`, with AI-drafted subject/body containing the literal `{{specific_recent_topic}}` merge tag for each row
7. **Boden fills the `specific_recent_topic` column** in `UZ_Press_T1` (5 minutes per row, see Section 2's research checklist), then imports to MailMeteor
8. Five send-days later, run a second MailMeteor import against `UZ_Press_T2`

### Apollo CSV column mapping

Identical to the Realtors brief mapping plus one extra:

| Apollo column | Internal field | Used in |
| --- | --- | --- |
| Company Name | `publication` (alias of `company`) | merge tag, AI prompt |

The pipeline writes both `company` and `publication` columns to the press tab so the MailMeteor template can use whichever reads better.

### YouTube reviewer supplement

Apollo doesn't index YouTubers well. Sourcing approach:
1. Search YouTube for "best Chrome extensions for [niche]" videos with 5k+ views in the last 12 months
2. Note the channel + creator name + business email from the channel's "About" tab
3. Add directly to the CSV before drop, with `source = manual-youtube` so the AI prompt adapts the angle (review-format pitch instead of article pitch)

### Dedupe behaviour

Same as Realtors: pipeline drops rows whose `editor_email` already appears in either tab of the UZ Press Sheet. The HailBytes excluded-contacts list and the Realtors campaign's contact list are also applied so no recipient appears across multiple Lost Rabbit Digital campaigns.

---

## 6. Reply Handling — Boden's Playbook

**Owner:** Boden, with David as escalation for any partnership conversation.

**CRM rule:** same as Realtors. Cold press contacts do **not** go into Pipedrive. Only after a press contact replies — to anything other than an unsubscribe — does Boden manually create a Pipedrive deal.

### Common press replies and responses

**"Send me a license"**
- Reply with the Stripe checkout URL with `PRESS-FREE-12` coupon prefilled
- Move the lead to "Pro license sent" stage in Pipedrive (post-reply)

**"Can we set up a demo?"**
- Reply with David's Calendly link
- Escalate to David — David takes the call

**"What are your install numbers?"**
- Reply with current numbers if flattering, or stick to qualitative ("strong early traction with the real-estate vertical")

**"What's your affiliate program?"**
- "We offer custom discount codes per publication with case-by-case revenue share — typically 30% of first-year revenue. Want me to set one up for [outlet]?"
- Escalate to David for the partnership conversation

**"Not interested / unsubscribe / remove me"**
- Reply: "No problem, removed."
- Add to suppression list within 24h. No exceptions.

**Anything about coverage scheduling, partnership terms, or interview requests → escalate to David.**

### Pipedrive stages (post-reply only)

When Boden manually adds a replied press contact:

1. Replied — interested
2. Pro license sent
3. Coverage scheduled
4. Coverage published
5. Custom code issued
6. Closed lost

### Custom fields on the deal

- Source UTM
- Send batch / week number
- Sequence touch that triggered reply (1 or 2)
- Outlet / publication name
- Custom code issued (if any)
- Estimated reach (for tracking high-value coverage)

---

## 7. Weekly Review (every Monday, 10 min)

Owner: David. Press is a slow-burn channel — tracked weekly with the Realtors review (see Realtors brief Section 8).

Press-specific items:

- [ ] New `PRESS-FREE-12` redemptions in Stripe → confirm a piece of coverage was promised
- [ ] Pipedrive: any press contacts moved into "Coverage published" — note the outlet and post the link in the team channel
- [ ] Active partner codes: any spike in `READER-{outlet}-30` redemptions (a piece dropped — follow up to thank the partner)
- [ ] Next week's press batch hand-curated and dropped in `outreach/inbox/ultrazoom-press/`

### Performance benchmarks

Press has very different benchmarks from realtor — the floor is lower because press contacts are busy and decisions are slow.

After 4 weeks (~30–40 press T1 sends):

- **Reply rate <5%** → angle isn't landing. Test a different lede pitch and Touch 1 hook.
- **Reply rate 5–15%** → on track for cold press outreach.
- **Reply rate >15%** → great list quality. Scale within the 15/day cap.
- **Coverage rate (replies that turned into a piece) >10%** → exceptional. Most of the time, "free Pro license sent" is the journey end.

After 60 days, decide:
- Continue at the same scale
- Add YouTube reviewer batch as its own slice
- Wind down and put the press budget into another track

---

## 8. Open TODOs Before Launch

- [ ] Press contact email decided (`press@ultrazoom.com` vs `david@ultrazoom.com`)
- [ ] Founder bio + headshot finalized
- [ ] Boilerplate paragraph written
- [ ] First press batch hand-curated (10–15 contacts)
- [ ] `/press` page live with all assets
- [ ] `PRESS-FREE-12` Stripe coupon created and Stripe checkout URL captured
- [ ] First `READER-{outlet}-30` template documented (the actual codes are created on-demand per partner)
- [ ] Calendly link finalized for David
- [ ] Google Sheet for UZ Press created, tabs `UZ_Press_T1` and `UZ_Press_T2` created, shared with the leads-writer service-principal email
- [ ] `GOOGLE_SHEET_ID_UZ_PRESS` repo secret added to UltraZoomWebsite
- [ ] First Boden research session scoped — block 30 min on the calendar, fill in `specific_recent_topic` for the first batch

---

## 9. Cost Summary

**Monthly recurring (net new):**
- $0 — shares MailMeteor seat, Apollo subscription, Anthropic API, Stripe, Pipedrive, Google Workspace, and the `ultrazoom.com` domain with the Realtors campaign

**One-time:**
- Press kit assets (logo variants, screenshots, founder headshot): $0–300 depending on whether you self-produce or hire

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Boden runs out of time for `specific_recent_topic` research → sends with the literal merge tag visible | Low | High (looks unprofessional, kills the lead) | MailMeteor pre-send check rejects rows where `specific_recent_topic` is empty or contains `{{` |
| Press contact replies "I'm not the right person, ask {{}}" type | Medium | Low | Standard handoff reply, log who they pointed to, add to next batch if relevant |
| AI drafts hallucinate a recent piece the recipient didn't write | Low (mitigated — the AI leaves the merge tag for Boden) | High | The AI is explicitly instructed to leave `{{specific_recent_topic}}` as a literal merge tag, not invent content. Validation rejects bodies that don't contain the literal tag. |
| Domain reputation hit on `lostrabbitdigital.com` (shared with Realtors and other Lost Rabbit Digital comms) | Medium | High | Postmaster Tools weekly, hard 15/day cap shared across campaigns, immediate pause triggers — see Realtors brief Section 5 |
| Custom partner code fraud / abuse | Low | Low | Per-code redemption limit (100), monthly review of redemptions vs. agreed coverage |

---

## 11. References & Links

- Apollo saved search: `Ultra Zoom — Press — Q2 2026`
- MailMeteor account: [link]
- Press kit: `https://ultrazoom.com/press`
- Postmaster Tools: see [Realtors brief Section 5](./ultrazoom-realtors-q2-2026.md#5-sending-infrastructure)
- Pipedrive: [link to UZ Press pipeline]
- Stripe coupons: [link to dashboard]
- UZ Press Google Sheet: [link once created]
- Partner tracking: `outreach/partners.csv` in this repo (or a `Partners` tab on the UZ Press Sheet)
- Suppression list: `outreach/suppression.csv` in this repo (shared with Realtors)
- Brand assets: `/public/press/` in this repo
- Sister campaign: [`ultrazoom-realtors-q2-2026.md`](./ultrazoom-realtors-q2-2026.md)
