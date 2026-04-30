# Ultra Zoom Realtors Outreach Campaign

**Status:** Pre-launch
**Target launch:** This week
**Owner:** David (strategy, escalations) / Boden (sending, replies)
**Last updated:** April 2026
**Companion press strategy:** [`docs/press/ultrazoom-launch-press-release.md`](../../docs/press/ultrazoom-launch-press-release.md) — $75-tier syndicated release replaces the cold-press cold-email motion that earlier drafts of this brief paired with the realtor track.

---

## TL;DR

60-day cold-email campaign to U.S. real estate agents at small (1–50 employee) brokerages, sending **up to 15 emails/day total** (mix of new Touch 1 sends and queued Touch 2 follow-ups) from `boden@lostrabbitdigital.com` via MailMeteor. Drives traffic to `/realtors`. Attribution via Stripe coupon `REALTOR30`. Net new monthly cost: ~$30.

**Steady-state pattern (week 2 onward):** ~8 new Touch 1 sends + ~7 Touch 2 follow-ups per active send day.

**Total prospect volume over 60 days:**
- ~300 unique realtors contacted (Touch 1 sends)
- ~600 total emails (with Touch 2 follow-ups for each)
- Active send days: ~40 (assumes weekday cadence with modest vacation/conference allowance)

---

## Pre-Launch Checklist

Must complete before first send. Ordered by criticality.

- [ ] **Compatibility testing** on Zillow, Redfin, [Realtor.com](http://Realtor.com) (priority 1) and 2+ major MLSs. Cannot launch realtor track without this.
- [ ] **Gmail Postmaster Tools** set up at [postmaster.google.com](http://postmaster.google.com) for `lostrabbitdigital.com`. DNS verification record added.
- [ ] **Stripe coupon code** `REALTOR30` created (see Section 4)
- [ ] **`/realtors` landing page** live with UTM-aware checkout link and coupon prefill
- [ ] **MailMeteor account** connected to `boden@lostrabbitdigital.com` with daily cap set to 15
- [ ] **Boden sync** — 30-min walkthrough of reply scenarios and escalation path
- [ ] **Apollo realtor list exported** for week 1 — see Section 6
- [ ] **Suppression list** seeded with HailBytes existing-contact exclusions and competitor list
- [ ] **Google Sheet** for UZ Realtors created and shared (Editor) with the leads-writer service-principal email
- [ ] **`GOOGLE_SHEET_ID_UZ_REALTORS` repo secret** added to UltraZoomWebsite
- [ ] **`outreach-ultrazoom` GitHub Action** updated to trigger on `outreach/inbox/ultrazoom-realtors/**` (delivered in Phase 6 of the rebuild)

---

## 1. `/realtors` Landing Page

**Purpose:** Convert cold-email traffic into trial signups and paid licenses.

**URL:** `ultrazoom.com/realtors`

**Tracking requirements:**
- Coupon prefill: if `?coupon=REALTOR30` in URL, forward it to the checkout API so Stripe applies the discount automatically
- Attribution is read from Stripe (count of `REALTOR30` redemptions) and Cloudflare's built-in request analytics (visits to `/realtors`). No client-side analytics SDK is added for this campaign.

### Page structure

#### Hero

- **Headline:** TODO — recommend "See every detail in MLS photos. Instantly."
- **Subhead:** TODO — recommend "Hover-zoom built for real estate agents who review hundreds of listings a day."
- **Demo video:** TODO — 20-30 sec Loom or self-hosted, hover-zoom on a real Zillow listing. Do not use MLS-branded screenshots — use Zillow/Redfin/[Realtor.com](http://Realtor.com) only for the demo asset.
- **Primary CTA button:** "Install free trial" → Chrome Web Store link
- **Trust line under CTA:** TODO — "Works on Zillow, Redfin, [Realtor.com](http://Realtor.com), and major MLSs" (only after compatibility testing confirms this)

#### Use Cases (3-4 cards)

- TODO: Inspect listing photo quality before showings
- TODO: Spot wear, damage, or staging issues for buyer clients
- TODO: Compare comp photos at full detail
- TODO: Review inspection photos without download/zoom workflow

Each card needs a 1-line description and ideally a small visual.

#### Social Proof

- TODO: Source 2-3 short realtor testimonials before launch
- **Sourcing strategy:** offer free lifetime accounts to first 5 realtors who provide a 30-second video testimonial. Post in r/realtors or use existing personal network.
- TODO: Chrome Web Store rating + install count if flattering. Skip the section entirely if numbers are still small.

#### Pricing

- TODO: Single agent tier — $X/mo or $Y/yr
- TODO: Team tier (3-10 agents) — $X/agent/mo
- TODO: "Brokerage licensing — contact us" tier — captures bulk-license interest
- All prices should match what's currently listed on main `/pricing` page; do not create pricing inconsistency between pages

#### FAQ

- **Does this work with my MLS?** TODO — link to compatibility list
- **Is my client data safe?** TODO — privacy posture, no data collection language
- **Will this slow down my browser?** TODO
- **Can I install on multiple devices?** TODO
- **Tax-deductible business expense?** TODO — yes for self-employed agents, but include "consult your CPA" disclaimer

#### Final CTA

- Repeat install button
- Secondary CTA: "Talk to us about brokerage licensing" → mailto or contact form

---

## 2. Compatibility Testing Plan

**Status:** Pre-launch dependency. Realtor track cannot launch until consumer sites pass.

### Sites to test

**Tier 1 (must pass before launch):**
- Zillow
- Redfin
- [Realtor.com](http://Realtor.com)

**Tier 2 (test 2+ for "works with major MLSs" claim):**
- Bright MLS (DC/MD/VA/PA/NJ/DE — largest US MLS)
- CRMLS (California)
- Stellar MLS (Florida)
- MRED (Chicago/Midwest)
- Northwest MLS (Pacific Northwest)

### Test script per site

For each site, verify:
1. Hover triggers zoom on listing thumbnails — pass/fail
2. Hover triggers zoom in full photo gallery — pass/fail
3. Hover-zoom works in fullscreen photo modal — pass/fail
4. No conflict with site's native zoom/lightbox — pass/fail
5. No perceptible page slowdown — pass/fail
6. No console errors during normal browsing — pass/fail

### MLS access strategy

MLS sites require active agent credentials. Options ranked by speed:

1. **Find a realtor friend** — 30-min screen share, free, fastest if available
2. **Hire on Upwork** — 1-2 realtors at $50-100 each for 1-hour paid sessions
3. **Post in r/realtors** — offer free lifetime license for compatibility testing

### Acceptance criteria

- Tier 1: all 3 sites must pass before realtor sends start
- Tier 2: at least 2 of 5 must pass before claiming "Works with major MLSs" in copy
- Document failures: either fix selectors before launch, or omit that geography from targeting

### Upwork job description template

> **Looking for licensed real estate agent for 1-hour paid software compatibility test ($75)**
>
> We're launching a Chrome extension for real estate professionals and need to verify it works correctly on major MLS systems. You'll need active agent credentials for [Bright MLS / CRMLS / etc.]. Test takes 45-60 minutes via screen share.
>
> Looking for someone available this week. Will provide test script and detailed instructions.

---

## 3. Email Sequence

2-touch sequence. Both touches have their subject and body drafted per-lead by Claude in the GitHub Action, then staged into separate sheet tabs that MailMeteor imports as two campaigns (Touch 1 first; Touch 2 imported five send-days later). The reference templates below define the **voice, structure, and required elements** the AI prompt enforces — they are not literal MailMeteor templates.

**Send window:** weekdays, 8am–6pm recipient local time, randomized
**Daily volume:** ≤15 total per send day, mixing new Touch 1 sends with Touch 2 follow-ups from leads sent five send-days prior. Steady-state mix ~8 T1 + ~7 T2.

### Per-lead AI-drafted fields (per touch)

For each lead, the pipeline writes four fields to the row:

| Field | Length | Notes |
| --- | --- | --- |
| `personalized_subject` | ≤8 words | No clickbait, no all-caps, no question marks unless natural |
| `personalized_body` | 80–150 words | 4–6 sentences, ends with terminal punctuation |
| (validation) | — | No em-dashes, no sycophantic openers, no banned words (`stumbled`, `amazing`), required tokens present |
| `required_tokens` | — | T1 body must include `{{landing_page_link}}` and the literal string `REALTOR30`. T2 body must reference REALTOR30 and not include a new link. |

The AI is given the lead's first name, title, company, city/state, industry, and any company-description signal from the Apollo CSV, plus the campaign brief's voice guidelines and the reference templates below.

### Touch 1 — Day 0 (reference template)

**Subject (reference):** How long does it take you to spot a hairline crack on Zillow?

**Body (reference):**

```
Hey {{first_name}},

Quick one. How often do you click into MLS or Zillow photos
just to check if that's a crack, water stain, or shadow?

Built Ultra Zoom for this. Hover over any listing photo and
it expands to full detail without clicking through. Works on
Zillow, Redfin, Realtor.com, and major MLSs.

20-second demo: {{landing_page_link}}

If it's worth a look, REALTOR30 gets you 30% off your first year.

David
Ultra Zoom
```

**Variables (resolved by the pipeline before staging):**
- `{{first_name}}` — from the Apollo CSV `First Name` column
- `{{landing_page_link}}` — `https://ultrazoom.com/realtors?coupon=REALTOR30`

### Touch 2 — Day 5 (reference template)

Same subject as Touch 1 with `Re:` prefix so MailMeteor keeps it threaded in Gmail.

**Subject (reference):** Re: How long does it take you to spot a hairline crack on Zillow?

**Body (reference):**

```
Hey {{first_name}},

Closing the loop on this. Should I leave Ultra Zoom on your
radar or move on?

Either's fine. If you do want to try it, REALTOR30 still works.

David
```

Touch 2 deliberately does not repeat the demo link — recipients who care saw it on Touch 1.

### What the AI personalizes (and what it doesn't)

**Personalizes:**
- Opening line tied to a specific signal in the Apollo row (city, brokerage type, role, niche)
- Phrasing of the value prop in the lead's voice (luxury vs. starter homes, urban vs. rural, etc.)
- Subject line variant

**Does NOT personalize:**
- Coupon code (always `REALTOR30`)
- Landing-page link template (always the UTM pattern above)
- Signoff (`David / Ultra Zoom`)
- Voice constraints (no em-dashes, no sycophancy, ≤150 words)

---

## 4. Stripe Coupon Setup

**Purpose:** Track campaign attribution and offer a launch incentive. The realtor track only needs one coupon.

| Code | Discount | Audience | Duration | Redemption Limit |
|---|---|---|---|---|
| `REALTOR30` | 30% off | Realtor cold email | First 12 months | 200 |

### Setup steps

1. Stripe Dashboard → Products → Coupons → Create
2. Set discount type and amount (30% off, recurring for 12 months)
3. Set redemption limit to 200 (caps abuse, makes it scarce)
4. Set expiration: campaign end date + 30 days
5. Update `/realtors` checkout flow to read `?coupon=REALTOR30` from URL and prefill the Stripe checkout coupon field
6. End-to-end test: email link → landing page → checkout with coupon prefilled → success page

---

## 5. Sending Infrastructure

### Stack

- **Sender:** `boden@lostrabbitdigital.com`
- **Sending tool:** MailMeteor (Pro tier, ~$30/mo)
- **Daily cap in MailMeteor:** 15 hard limit
- **Send schedule:** weekdays, randomized between 8am-6pm recipient local time

### Why this setup

- Lost Rabbit Digital is an established business sender with built-in reputation
- 15/day total mixed with normal mail stays well within Gmail Workspace safe limits
- $0 new infrastructure beyond MailMeteor itself
- MailMeteor sends through actual Gmail, no separate auth or DNS work

### Risk mitigations (mandatory)

**Gmail Postmaster Tools setup:**
1. Sign in at [postmaster.google.com](http://postmaster.google.com) with a Lost Rabbit Workspace admin account
2. Add `lostrabbitdigital.com`
3. Verify via DNS TXT record (Cloudflare DNS console)
4. Wait 24-48 hours for first reputation data

**Weekly monitoring (every Monday morning, 5 min):**
- Domain reputation: must stay "High" or "Medium" — if drops to "Low" or "Bad," **pause both campaigns immediately**
- Spam rate: must stay under 0.1% — if exceeds, pause and audit list quality
- Authentication: SPF/DKIM/DMARC must show >99% pass

**Pause triggers (non-negotiable):**
- Domain reputation drops to "Low" or "Bad" → pause both UZ campaigns, investigate, resume only after recovery
- Spam complaint rate >0.1% → pause, audit list, retrain copy
- Bounce rate >5% → pause, verify Apollo email validation settings
- Any "this is spam" reply from a recipient → suppress immediately, no exceptions

**Suppression list management:**
- Any reply containing "remove," "unsubscribe," "stop," "take me off" → suppress within 24h
- Add to MailMeteor unsubscribe list AND maintain a master CSV in repo (`outreach/suppression.csv`)
- Re-import suppression list before every new Apollo CSV ingest

### DNS records to verify on `lostrabbitdigital.com`

- **SPF** — must include Google's servers: `v=spf1 include:_spf.google.com ~all`
- **DKIM** — enabled in Google Workspace admin, public key published in DNS
- **DMARC** — recommended `v=DMARC1; p=quarantine; rua=mailto:dmarc@lostrabbitdigital.com`

If any of these aren't already in place, set up before launch.

---

## 6. Apollo Manual Export

The pipeline no longer calls Apollo's API. Instead, run a saved Apollo People search in the UI, export the result as CSV, and drop it into the inbox folder. The GitHub Action picks it up and produces personalized drafts.

### Saved search: `Ultra Zoom — Realtors — Q2 2026`

Build this once in Apollo, save it, re-run weekly.

**Job titles (Include):**
- Realtor
- Real Estate Agent
- Real Estate Broker
- Associate Broker
- Principal Broker
- Listing Agent
- Buyer's Agent

**Title settings:**
- Include similar titles: ON
- Exclude titles: Assistant, Coordinator, Marketing, Transaction Coordinator

**Industries:** Real Estate

**Company size:** 1–50 employees

**Geography:** United States only — start narrow (e.g. one state for week 1) then widen as the realtor track proves itself

**Email status:** Verified only

**Seniority:** Owner, Founder, Partner, Senior, Manager

**Exclude companies:**
- Keller Williams (corporate)
- RE/MAX Holdings
- Compass Inc
- Coldwell Banker corporate
- eXp Realty corporate

**Volume target:** ~75 prospects per export, which covers ~8 Touch 1 sends/day × 5 realtor send days + buffer for bounces and dedupe drops.

### Export workflow

1. Run the saved Apollo search
2. Confirm the match count is in the 75–150 range. If wider, tighten geography first (one state at a time).
3. Select up to ~75 contacts. Apollo top-sorts by recent activity by default — keep that.
4. Click **Export → CSV → All columns**. Apollo emails the file when ready (a few minutes for 75 rows).
5. Save the file to `outreach/inbox/ultrazoom-realtors/<YYYY-MM-DD>.csv` on the active branch.
6. Commit + push the branch. The `outreach-ultrazoom` GitHub Action triggers on push to `outreach/inbox/ultrazoom-realtors/**`.
7. The Action populates two tabs in the UZ Realtors Sheet: `UZ_Realtors_T1` and `UZ_Realtors_T2`, each with the AI-drafted subject/body for that touch and the merge fields MailMeteor expects.
8. In MailMeteor, point the realtor template at `UZ_Realtors_T1` and schedule the send. After 5 send-days, run a second MailMeteor import against `UZ_Realtors_T2`.

### Apollo CSV column mapping

The pipeline normalizes these Apollo columns to internal candidate fields. Other columns are kept on the row but unused by the personalization prompt.

| Apollo column | Internal field | Used in |
| --- | --- | --- |
| First Name | `first_name` | merge tag, AI prompt |
| Last Name | `last_name` | merge tag |
| Email | `editor_email` | MailMeteor `To:` |
| Title | `editor_title` | AI prompt |
| Company Name | `company` | AI prompt |
| Website | `domain` (parsed) | dedupe, AI prompt |
| Person Linkedin Url | `linkedin_url` | reference, debugging |
| City | `city` | AI prompt (geographic hook) |
| State | `state` | AI prompt |
| Industry | `industry` | filter sanity-check |
| Keywords | `keywords` | AI prompt (signal mining) |
| # Employees | `company_size` | filter sanity-check |
| Apollo Contact Id | `apollo_contact_id` | hard dedupe key |

### Dedupe behaviour

Before staging, the pipeline drops rows whose `editor_email` already appears in either tab of the UZ Realtors Sheet. Apollo Contact Id is the secondary key for the same purpose. The HailBytes excluded-contacts list is also applied so no recipient appears across both companies' campaigns.

---

## 7. Reply Handling — Boden's Playbook

**Owner:** Boden, with David as escalation.

**CRM rule:** cold prospects do **not** go into Pipedrive. Only after a lead replies — to anything other than an unsubscribe — Boden manually creates a Pipedrive deal in the appropriate stage. This keeps Pipedrive clean and avoids the "5,000 stale leads" problem.

### Common realtor replies and responses

**"Does this work with [my MLS]?"**
- If on tested list → "Yes, confirmed working on [MLS name]. Here's a 20-sec demo: [link]"
- If not tested → "We haven't formally tested [MLS name] yet, but the extension works on most MLS image viewers. Free trial — try it and let me know if you hit any issues."

**"How much for a team / brokerage?"**
- 3–10 agents: quote team tier from pricing page
- 10+ agents: "Happy to set up a 15-min call to scope it — what's your team size and timeline?" → escalate to David

**"Is this safe / does it collect data?"**
- "No data collection. The extension runs locally in your browser. Privacy policy: [link]"

**"Can I expense this?"**
- "Most agents do. It's a business tool deductible like any other software subscription. Consult your CPA for specifics."

**"Not interested / unsubscribe / remove me"**
- Reply: "No problem, removed."
- Add to suppression list within 24h. No exceptions.

**Anything technical, complex, or about brokerage licensing → escalate to David.**

### Pipedrive stages (post-reply only)

When Boden manually adds a replied lead:

1. Replied — interested
2. Replied — objection (track which: pricing, MLS support, IT policy, other)
3. Trial started
4. Trial converted
5. Brokerage opportunity (>10 seats) — escalate to David for a call
6. Closed lost

### Custom fields on the deal

- Source UTM
- Send batch / week number
- Sequence touch that triggered reply (1 or 2)
- Coupon code redeemed
- Estimated value (for brokerage opportunities)

---

## 8. Weekly Review (every Monday, 15 min)

Owner: David

- [ ] Postmaster Tools: domain rep, spam rate, auth pass rates
- [ ] MailMeteor: bounce rate, reply rate, unsubscribes
- [ ] Pipedrive: any new replies promoted in, stage progression, brokerage opps
- [ ] Stripe: `REALTOR30` redemptions, new revenue
- [ ] Suppression list updated and re-imported into MailMeteor
- [ ] Next week's Apollo CSV exported and dropped in `outreach/inbox/ultrazoom-realtors/`

### Performance benchmarks

After 2 weeks (~100 realtor T1 sends):

- **Reply rate <2%** → copy isn't landing. Test new subject line and Touch 1 angle.
- **Reply rate 2–5%** → on track for cold realtor outreach.
- **Reply rate >5%** → either copy is great or list is unusually warm. Scale carefully.
- **Bounce rate >5%** → Apollo data quality issue. Tighten filters or change email verification settings.
- **Spam complaint >0.1%** → pause immediately. List or copy problem.

After 60 days, decide:
- Continue with same playbook
- Expand to insurance buyer track (separate plan)
- Wind down and reallocate effort

---

## 9. Open TODOs Before Launch

Tactical items not covered above. Knock these out this week.

- [ ] Compatibility test scheduled / scheduled with realtor
- [ ] Realtor testimonials sourced (target: 2 by launch, 5 within 30 days)
- [ ] Demo video recorded (20-30 sec, hover-zoom on Zillow)
- [ ] Boden 30-min sync booked
- [ ] Apollo realtor batch 1 exported and dedup'd vs. HailBytes existing-contact list
- [ ] Postmaster Tools verified
- [ ] `REALTOR30` Stripe coupon created and tested end-to-end
- [ ] Landing page UTM + coupon prefill tested end-to-end
- [ ] Suppression list seeded with HailBytes exclusions and competitor list
- [ ] Google Sheet for UZ Realtors created, tabs `UZ_Realtors_T1` and `UZ_Realtors_T2` created (header rows can be left empty; the pipeline writes them on first append), shared with the leads-writer service-principal email
- [ ] `GOOGLE_SHEET_ID_UZ_REALTORS` repo secret added to UltraZoomWebsite

---

## 10. Cost Summary

**Monthly recurring (net new):**
- MailMeteor Pro: ~$30/mo
- **Total: ~$30/mo**

**Already paid for:**
- Apollo (existing subscription)
- Stripe (existing)
- Pipedrive (existing)
- Anthropic API (existing — pay-per-use, ~$0.01–0.05 per 75-lead batch on Haiku)
- Google Workspace for `lostrabbitdigital.com` (existing)
- `ultrazoom.com` domain (existing)

**One-time:**
- Compatibility testing: $0–200 (depending on Upwork hires)
- Demo video production: $0 (self-recorded) or ~$100–300 (Fiverr)

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Domain reputation hit on `lostrabbitdigital.com` affects other Lost Rabbit Digital comms (client work, internal mail) | Medium | High | Postmaster Tools weekly, hard 15/day cap, immediate pause triggers |
| Ultra Zoom breaks on a major MLS, causing refund requests | Medium | High | Compatibility testing pre-launch, Tier 1 sites must pass |
| Boden overwhelmed by reply volume | Low (at 15/day) | Medium | Reply playbook + escalation path documented |
| Cold email considered SPAM by recipient → complaint | Low-Medium | Medium-High | List hygiene, suppression list discipline, AI validation of copy quality |
| Apollo data quality (wrong emails, role changes) | Medium | Low | Email verification ON in Apollo at export time, tolerance of 5% bounce |
| Brokerage inquiries arrive without enterprise sales process | Medium | Low (good problem) | Calendly link + David handles escalation |
| AI personalization drifts off-brand (sycophancy, em-dashes, made-up facts) | Medium | Medium | `enrich_personalize.py` validation + spot-check first 10 rows of every batch before MailMeteor import |

---

## 12. References & Links

- Apollo saved search: `Ultra Zoom — Realtors — Q2 2026`
- MailMeteor account: [link]
- Postmaster Tools: [postmaster.google.com](http://postmaster.google.com)
- Pipedrive: [link to UZ pipeline]
- Stripe coupons: [link to dashboard]
- UZ Realtors Google Sheet: [link once created]
- Suppression list: `outreach/suppression.csv` in this repo
- Brand assets: `/public/press/` in this repo
- Companion press strategy: [`docs/press/ultrazoom-launch-press-release.md`](../../docs/press/ultrazoom-launch-press-release.md)
