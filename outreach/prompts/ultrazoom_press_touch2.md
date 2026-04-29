# Ultra Zoom Press — Touch 2 reference

5-day follow-up to a Touch 1 that got no reply. Threaded under the same
subject in Gmail. The follow-up doubles down on the free Pro license
offer — at this point we're optimizing for "they take the license and
write something later" more than "they reply this week."

## Reference subject

> Re: Pitch for {{publication}}

Mirrors Touch 1's subject with `Re: ` prepended. The runner enforces the
prefix automatically; the JSON ``subject`` field should contain the
``Re: ...`` form. ``{{publication}}`` literal merge tag stays in.

## Reference body

```
Hi {{first_name}},

Quick follow-up. Happy to make this easy. Free Pro license is
yours either way: {{license_signup_link}}

If a review or mention fits, let me know and I'll send a custom
reader discount code.

David
```

## Structure beats

1. Greeting: `Hi {{first_name}},`
2. One-line nudge framed as making it easy on them
3. License offer with the literal `{{license_signup_link}}` merge tag —
   this is the hook. The recipient gets value (a real Pro license) just
   for replying.
4. Coverage offer phrased as conditional — "if a review fits, custom
   reader discount code" — no pressure
5. Signoff: `David` on its own line. No company name on T2.

## Critical: the {{license_signup_link}} merge tag

The body MUST contain the literal string `{{license_signup_link}}`. The
runner doesn't substitute it — MailMeteor does, at send time, with the
prefilled-coupon Stripe checkout URL.

Validator rejects bodies missing this token.

## Personalization room

You may adjust:
- The phrasing of the "make it easy" line
- A small reference to T1's specific topic if it strengthens the nudge,
  but no inventions — refer back generically rather than guess

You may NOT:
- Reference `{{specific_recent_topic}}` again (T1 owned that beat;
  repeating it 5 days later reads as forced)
- Add a Calendly link (the license-signup CTA is enough — if they want
  a demo they'll ask)
- Re-pitch product features (T1 already did)
- Use em-dashes
- Exceed 80 words

## Tone

Generous and short. The follow-up should feel like a small extra effort
on David's part to give the journalist value with no strings.
