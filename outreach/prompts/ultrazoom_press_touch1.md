# Ultra Zoom Press — Touch 1 reference

This is the cold-open pitch to a tech journalist, blog operator, or
extension reviewer. Voice is founder-pitching-press: specific, concise,
respects the reader's time. The recipient sees pitches like this every
day; the only thing that earns a reply is being concrete about why this
is worth their two minutes.

## Reference subject

> Pitch for {{publication}}: hover-zoom built for pros

You may vary the subject as long as `{{publication}}` (literal merge
tag) stays in it. The runner fills `{{publication}}` from the row's
`company` column. Subject under 9 words.

## Reference body

```
Hi {{first_name}},

Saw your work on {{specific_recent_topic}}. Good stuff.

Quick pitch: I built Ultra Zoom, a hover-zoom Chrome extension
for people who review images professionally (real estate agents,
insurance adjusters, e-commerce buyers). Different from the free
hover-zoom extensions because it works on the sites where the
others fail, MLSs, claim platforms, marketplace dashboards.

Press kit + demo: {{press_kit_link}}

Happy to send a free Pro license for hands-on review, or set
up a 15-min demo. If a "best Chrome extensions for [profession]"
piece fits your editorial calendar, I can offer your readers a
custom discount code for tracking.

David
Founder, Ultra Zoom
```

## Critical: the {{specific_recent_topic}} merge tag

The body MUST contain the literal string `{{specific_recent_topic}}` —
not a paraphrase, not your guess at what they wrote about, not a
publication-name fill. The double-curly-brace tag stays in the body
verbatim.

This is non-negotiable. Boden manually fills the topic per row in the
Sheet before MailMeteor sends. If you invent a topic the recipient
didn't write about, the email reads as fabricated and the lead is
burned. Leave the merge tag in place.

The validator rejects bodies that don't contain `{{specific_recent_topic}}`.

## Structure beats

1. Greeting: `Hi {{first_name}},`
2. Acknowledgement of their recent work via the literal merge tag
   `{{specific_recent_topic}}` — exactly one sentence, not a flattering
   essay.
3. Pitch paragraph — name the product, who it's for, what's novel about
   it (works on sites the free hover-zooms fail on). Keep this concrete
   — list the verticals (real estate, insurance, e-commerce) and the
   site categories (MLSs, claim platforms, marketplace dashboards).
4. Press kit link line with literal `{{press_kit_link}}` merge tag
5. Two CTA options: free Pro license, or 15-min demo. Mention the
   custom discount code for readers as a partner-coverage hook.
6. Signoff: `David` then `Founder, Ultra Zoom`

## Personalization room

You may adjust:
- The framing of the pitch paragraph based on the publication's beat
  (productivity tools, browser extensions, real-estate tech, design
  tools — pick the closest fit and lead the verticals list with that)
- The CTA phrasing (e.g. for a YouTube reviewer, "happy to send a Pro
  license for a hands-on video review")
- The subject line within the constraint of `{{publication}}` appearing

You may NOT:
- Resolve `{{specific_recent_topic}}` to any actual topic
- Replace `{{press_kit_link}}` with a real URL
- Add a Calendly link directly in T1 (T2 has the demo offer)
- Use sycophancy: don't open with "I love your work" or "huge fan"
- Use em-dashes
- Exceed 180 words

## Tone

Specific over generic. Concrete over abstract. The recipient is busy
and skeptical; the only thing that earns the click is feeling that
David genuinely engages with their work.
