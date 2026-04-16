# Listicle Outreach — Iteration Prompt

Copy and paste the prompt below into a new Claude Code session (or the same session) to run a subsequent batch of outreach research. It picks up where the last batch left off, avoids duplicates, and follows the same format.

---

## Prompt

```
I need you to find the NEXT batch of 10-15 active browser extension listicles for outreach, avoiding duplicates from previous batches.

### Context
- Product: Ultra Zoom — a hover-to-zoom browser extension for Chrome and Firefox that works on 60+ websites (Google Images, Amazon, Reddit, Pinterest, Twitter/X, Instagram, etc.). Free with optional Pro features.
- Publisher: Lost Rabbit Digital LLC
- Website: https://ultrazoom.app
- Goal: Get Ultra Zoom mentioned/listed in "best extensions" articles

### Already contacted (do NOT include these publications)
Check outreach/leads.json for the full list of already-contacted leads. Skip any publication or URL that appears there.

### Search strategy
Use a mix of these search queries (rotate angles each iteration):
1. "best chrome extensions" [year] blog — general productivity
2. "best browser extensions" [year] roundup — cross-browser
3. "must have chrome extensions" [year] — personal recommendation style
4. "best extensions for" [specific niche] [year] — e.g., designers, photographers, researchers, shoppers, students, ecommerce, social media managers
5. "chrome extension" listicle [year] site:medium.com OR site:dev.to — indie bloggers
6. "best firefox addons" [year] — Firefox-specific lists
7. "browser extensions" review [year] site:youtube.com — YouTube roundups (description box links)
8. inurl:blog "best extensions" [year] — blog-specific results

### For each lead, collect:
- Publication name and URL
- Article title and URL
- Author name and role
- Contact method: email (preferred), contact form, LinkedIn DM, X DM, Substack DM
- Contact details (email address, LinkedIn URL, etc.)
- Article category: productivity | accessibility | developer | security-privacy | personal-picks | ai-extensions | general
- Pitch angle: 1 sentence on why Ultra Zoom fits THIS specific article

### Prioritize:
- Independent blogs and small publications (higher response rate)
- Articles published in the last 12 months
- Authors with visible contact info (email > form > DM)
- Articles that don't already list a hover-zoom or image-zoom extension
- Skip: huge SaaS company blogs (ClickUp, Monday, etc.) unless they have a named author with direct contact

### Output format:
1. Add new leads to outreach/leads.json (append to the leads array, continuing the ID sequence)
2. Create individual email drafts in outreach/drafts/ following the naming pattern: NN-publication-slug.md
3. Each draft should include: To, Subject, Send window (Tue-Thu), and the personalized email body
4. Keep emails to 3-4 short paragraphs: reference their specific article, explain Ultra Zoom, explain why it fits, offer to help

### Email tone guidelines:
- Conversational but professional
- Reference something specific about their article (shows you read it)
- Explain the product in 1-2 sentences max
- Explain why it fits their specific list/audience
- Offer to provide screenshots/write-up/anything they need
- Close warmly, no hard sell
- Sign off with [Your Name], Lost Rabbit Digital LLC, https://ultrazoom.app

### Send cadence:
- Tue-Thu send window
- Adjust timezone in the Send window field based on the author's likely location
- Space emails so no more than 3-5 go out per day
```

---

## Tips for each iteration

- **Check leads.json first** to avoid reaching out to the same publication twice
- **Rotate search angles** — if Batch 1 was heavy on productivity, try accessibility, developer tools, or niche lists (photographers, ecommerce, students)
- **Try different platforms** — Medium, DEV, Substack, WordPress blogs, YouTube descriptions
- **Seasonal hooks** — "back to school extensions", "holiday shopping extensions", "new year productivity tools"
- **Follow-up cadence** — if a lead from a previous batch hasn't responded after 7 days, draft a short follow-up (2 sentences max) as a separate file: NN-publication-slug-followup.md
