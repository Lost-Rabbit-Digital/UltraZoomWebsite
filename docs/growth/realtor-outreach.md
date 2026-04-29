# Ultra Zoom — Realtor Outreach Plan

## Summary

Ultra Zoom has strong product-market fit signals for real estate professionals. The current pricing ($4/mo, $30/yr, $60 lifetime) sits below the personal-expense threshold where realtors stop deliberating, making this a bottom-up viral-loop play rather than a sales-led motion. Privacy and on-device processing are differentiators worth elevating in positioning.

## Market sizing

- Total US realtor TAM: ~1.45M NAR members (mid-2025), trending toward 1.4M for full-year 2025
- Add ~50-100K non-NAR licensees post-settlement opt-outs and ~5-7K commercial brokers (CCIM, SIOR)
- Total addressable: ~1.5M working professionals
- Realistic high-intent universe: ~500-700K active buyer-side and dual-side agents who do heavy listing review (the long tail of NAR membership includes many part-time and inactive licensees who would not adopt)

## Why realtors fit Ultra Zoom

- Listing photos are notoriously low resolution, making Lanczos upscaling immediately useful
- Buyer's agents screen dozens of listings daily and are trying to disqualify fast (water damage, foundation issues, deferred maintenance, neighborhood red flags)
- Listing agents audit competitor and pre-list inspection photos to find selling points and fixable issues
- Commercial brokers reviewing CoStar/LoopNet listings have even higher detail-per-photo dependence
- Current workflow is inefficient: open listing tab, then click photo, then open larger image - Ultra Zoom collapses this into a hover

## Two distinct buyer personas

### Buyer's agents (lead persona)
- Larger audience, more painful workflow
- Job to be done: screen listings fast, disqualify before scheduling showings
- Speed matters more than depth
- Values: time savings, client trust, fewer wasted showings

### Listing agents (secondary persona)
- Smaller audience, higher intent
- Job to be done: audit own listings for quality, audit competitor listings for positioning, review pre-list inspection photos
- Depth matters more than speed
- Values: deal closure, listing quality, competitive intelligence

## Positioning recommendations

### Add realtors to pricing page
Current "Why upgrade to Pro" section calls out power shoppers, collectors, designers, genealogists. Add realtors as the lead bullet:

> **Realtors and buyers' agents** use Pro to screen MLS and Zillow listings without opening every photo - spot deferred maintenance, water damage, and underappreciated details before scheduling showings.

### Lead with on-device privacy as a secondary pillar
Even at the prosumer price point, "images and browsing data never leave your device" is a meaningful trust signal for professionals reviewing client-related listings. Worth elevating on the marketing site.

### Build a realtor-specific landing page
Separate landing page at ultrazoom.app/realtors with:
- Buyer's agent demo video (60-90 seconds, real Zillow/Redfin/MLS examples)
- On-device privacy callout
- Lanczos upscaling explained in plain English
- Free tier prominent, lifetime offer as the close
- Single testimonial slot (fill once we have one)

## Pre-launch checklist

- [ ] Confirm Chrome Web Store listing is optimized for realtor-adjacent search terms
- [ ] Record buyer's agent demo video using real listing examples
- [ ] Ship realtors landing page
- [ ] Update pricing page "Why upgrade to Pro" section with realtor bullet
- [ ] Confirm free tier limits are generous enough for an agent to habituate (avoid trial-expiry churn)
- [ ] Set up basic attribution so we can tell which channel converts

## Outreach channels (sequenced)

### Phase 1: Paid Reddit + selective community participation (start immediately)

**Reddit Ads → realtor landing page (primary Phase 1 channel)**

Real estate subreddits (r/realtors, r/realestate, r/realtors_advice) are openly hostile to "I built a tool" posts, even high-effort ones. Mods remove them and the community downvotes self-promotion regardless of utility, so organic posting is not a viable channel here.

Instead, run a paid Reddit Ads campaign targeting the same audiences that pushes directly to the realtors landing page:
- Subreddit targeting: r/realtors, r/realestate, r/realestateinvesting, r/realtors_advice, r/CommercialRealEstate
- Interest targeting: real estate, home buying, real estate investing
- Creative: short looped video clip of the hover-zoom on a Zillow listing, with caption "Spot deferred maintenance before you book the showing"
- Landing page: `/realtors` with the buyer's agent demo and free-install CTA above the fold
- Budget: start at $20-40/day to validate CTR and install rate before scaling
- Attribution: UTM params on every ad creative; pair with the `uz_src` cookie script so we can tie installs back to Reddit

**Facebook groups (organic, lower priority)**

Facebook realtor groups are more permissive than Reddit but still vary by group rules. Limit to:
- Lab Coat Agents Facebook group (150K+ members) — check tool-share rules first
- BiggerPockets agent communities
- Regional Realtor Facebook groups where there's a personal connection

Approach: Participate genuinely for 2-3 weeks before posting. Then a single high-effort thread showing the tool with real listing examples. Goal is feedback velocity and language discovery (how realtors actually describe the problem), not direct conversion. Free tier removes friction.

### Phase 2: Mid-cost, scalable (after demo video and landing page ship)

**YouTube creator partnerships**
Target mid-tier channels (50K-500K subs) where $500-1,500 sponsorships or free pro accounts are in budget:
- The Real Estate Trainer
- Bryan Casella
- Loida Velasquez
- Newer agent-focused channels (search "real estate agent tools 2026" for current tier)

Skip the big names initially - audiences are noisier and they quote $5K+ without conviction. ROI signal: comments and signups within 48 hours of video posting.

**Industry podcast guest spots**
- Real Estate Rockstars
- The Tom Ferry Podcast
- Massive Agent Podcast
- Agent Rise

Pitch angle: "I built a tool to help agents spot issues in listing photos faster - here's what we learned about how the best agents review listings."

### Phase 3: Higher-cost, higher-conversion (after testimonials and traction)

**Local Realtor association lunch-and-learns**
NAR has 1,600 local boards. Many run monthly tech showcases and CE-credit courses.
- Start with one mid-size board where there's a personal connection or member champion
- Target Denver Metro, Houston, Phoenix as larger receptive markets
- Offer 30-minute "spotting issues in listing photos" session
- Implicit board credibility dramatically improves conversion

**State association tech showcases**
Larger commitment but higher visibility. Pursue only after local board validation.

## Pricing observations

Current structure is well-tuned for this audience:
- $4/mo is below the deliberation threshold for realtors
- $30/yr saves enough to feel like a deal without being suspicious
- $60 lifetime is the standout offer for power users and converts trial users who hate recurring billing

Consider testing:
- Annual price anchored at $39 with $30 as a "realtor discount" via promo code distributed through partnerships
- Team/brokerage pricing tier (5+ seats) once we have brokerage-level interest signals
- Affiliate program for realtor influencers (10-20% recurring) once attribution infrastructure exists

## Metrics to track

- Free → paid conversion rate (overall and by channel)
- Time-to-paid from install
- Lifetime vs monthly vs annual mix (lifetime % is a power-user signal)
- Channel CAC for the three phases above
- Realtor self-identification rate at signup (add optional "what do you do?" field)

## Open questions for follow-up

- What's the current Chrome Web Store install count and review profile?
- What's free → paid conversion looking like today across all users?
- Is there a referral mechanism in the extension itself? Realtors recommending tools to other realtors is the highest-trust acquisition channel
- Do we want to build any realtor-specific features (MLS detection, side-by-side listing comparison, save-and-annotate for client review) or stay horizontal?

## Next steps

1. Ship realtor landing page and pricing page update
2. Record buyer's agent demo video (also doubles as Reddit Ads creative)
3. Stand up Reddit Ads campaign → `/realtors`, with UTM + `uz_src` attribution wired up before launch
4. Vet a small set of permissive Facebook groups for organic Phase 1 posts
5. Build YouTube creator outreach list with channel names and contact paths
6. Identify one local Realtor board for Phase 3 pilot
