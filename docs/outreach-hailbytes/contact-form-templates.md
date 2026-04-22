# Contact-Form Outreach Templates — HailBytes (PoC)

Short copy-paste messages for **contact forms** (not email) on pen-testing
firms', MSSPs', vCISO practices', and SAT-provider websites. Each template is
a starting point — humans retouch during triage.

Form hygiene (same as the UltraZoom lane):
- One URL max (just `https://hailbytes.com` — extras get spam-flagged)
- No markdown — forms render `**bold**` and bullets literally on many backends
- ~500-800 chars
- Single low-friction ask: try it free for 30 days in exchange for feedback

Sign-off (reuse across all templates):
```
— David McHale, HailBytes
https://hailbytes.com
```

The live, form-ready drafts live in `scripts/lib/template-picker-hailbytes.mjs`.
This doc is the human-readable reference so we can edit copy without diffing
JS. If you change a template here, mirror it in the picker (or vice-versa).

---

## Product cheat sheet

**HailBytes ASM** (attack surface management, Docker-based, Azure/AWS Marketplace):
- 30+ recon tools in one pipeline (subfinder, nmap, nuclei, httpx, ffuf, etc.)
- Seven automated scan phases, correlated in a shared PostgreSQL DB
- Continuous monitoring with Slack/Discord/Teams/Telegram alerts
- AI-powered triage (GPT-4 or air-gapped Ollama with NVIDIA/AMD GPU support)
- Multi-tenant project isolation, RBAC, TOTP 2FA, audit logging
- No per-asset fee — unlimited targets at every tier
- 30-day free trial (software fee waived, customer pays VM compute)
- `$0.24/vCPU/hour` via Azure Marketplace or AWS Marketplace

**HailBytes SAT** (security awareness training, VM-based, Azure/AWS Marketplace):
- Phishing simulation + landing-page capture + real-time click analytics
- AI-assisted phishing template generation (Claude / Copilot / Cursor via MCP)
- Entra ID native — OIDC/SAML SSO, SCIM provisioning
- 2-vCPU instance supports up to 5,000 users
- No per-user fee — unlimited users/campaigns/templates
- SIEM-ready webhooks, audit-logged for HIPAA / PCI-DSS 12.6 / SOC 2
- 30-day free trial (software fee waived, customer pays VM compute)
- `$0.24/vCPU/hour` via Azure Marketplace or AWS Marketplace

Picker logic (see `template-picker-hailbytes.mjs`):
- Firms with clear SAT-primary signals ("phishing simulation", "security
  awareness training provider", "human risk management") → **SAT** pitch.
- Pen-test / red-team firms → **ASM** pitch (pentest variant).
- MSSP / MDR / SOC-as-a-service firms → **ASM** pitch (MSSP variant).
- vCISO / GRC / compliance firms → **ASM** pitch (vCISO variant).
- Everything else → **ASM** generic fallback (offers either, asks which fits).

---

## `hb-asm-pentest` — pen-test / red-team / offensive-security firms

```
Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management
platform built for pen-testing and offensive-security firms. It orchestrates
30+ recon tools (subfinder, nmap, nuclei, httpx, ffuf, and more) into one
continuous pipeline, runs in your own Azure or AWS tenant, and has no
per-asset fee — so you can monitor every engagement's external surface
without per-target licensing.

Would you try it free for 30 days and share honest feedback? Happy to set up
a short demo.

— David McHale, HailBytes
https://hailbytes.com
```

**When to use:** homepage, services page, or contact page of a firm whose
lead offering is pen-testing, red team, adversary emulation, or offensive
security consulting.

---

## `hb-asm-mssp` — MSSPs / MDR / SOC-as-a-service

```
Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management
platform built for MSSPs that want to add continuous external recon to their
managed service catalog. It runs 7 automated scan phases across 30+ tools,
deploys in your own Azure or AWS tenant (so client data never leaves your
cloud), supports multi-tenant project isolation and RBAC, and has no
per-asset fee — unlimited targets at every tier.

Would you try it free for 30 days and share feedback from an MSSP's
perspective?

— David McHale, HailBytes
https://hailbytes.com
```

**When to use:** MSSPs, MDR providers, SOC-as-a-service, managed SIEM, 24/7
monitoring shops. Multi-tenant / RBAC angle is the hook.

---

## `hb-asm-vciso` — vCISO / fractional CISO / GRC / compliance

```
Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management
platform that fits naturally into a vCISO or GRC engagement. It gives your
clients continuous external-asset discovery and vulnerability monitoring from
a single deployment in their own cloud tenant, with audit-logged findings
that map to SOC 2, HIPAA, and PCI controls. No per-asset fee — unlimited
targets.

Would you try it free for 30 days and share feedback? Useful to hear whether
it fits the vCISO toolkit.

— David McHale, HailBytes
https://hailbytes.com
```

**When to use:** vCISO practices, fractional CISO firms, GRC consultancies,
SOC 2 / HIPAA / PCI / CMMC / NIST 800-171 / ISO 27001 readiness shops.
Compliance-mapping angle is the hook.

---

## `hb-sat-training` — security awareness training / phishing simulation

```
Hi there,

David McHale here — I'm launching HailBytes SAT, a security awareness
training and phishing simulation platform built for firms that deliver SAT to
their clients. It runs in your own Azure or AWS tenant (no client data in a
vendor cloud), is Entra ID native with SCIM, has AI-assisted template
generation, and — critically — has no per-user fee. Unlimited users on a
single VM.

Would you try it free for 30 days and share feedback? I'd love to hear from a
firm that actually runs awareness programs.

— David McHale, HailBytes
https://hailbytes.com
```

**When to use:** firms whose primary or marquee offering is phishing
simulation, security awareness training, human risk management, or managed
phishing testing. No-per-user-fee is the hook — it's the KnowBe4 pain point.

---

## `hb-asm-generic` — fallback when classification is unclear

```
Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management
platform built for cybersecurity firms that want to add continuous external
recon to their client offerings. It runs in your own cloud tenant, chains
30+ recon and vulnerability tools into one automated pipeline, has AI-powered
triage, and charges no per-asset fee — unlimited targets at every tier. We're
also launching HailBytes SAT (phishing simulation, no per-user fee) in the
same family, in case that's a closer fit.

Free 30-day trial of either in exchange for feedback. Which would be the
better fit for your team?

— David McHale, HailBytes
https://hailbytes.com
```

**When to use:** broad cybersecurity consultancies, managed IT/security
hybrids, anything we can't confidently bucket. Mentions both products and
lets the recipient self-select.

---

## Status values (used in the `status` column of the Sheet)

Same vocabulary as the UltraZoom lane, re-used for consistency:

| Value | Meaning |
|---|---|
| `new` | Just discovered by `find-leads-hailbytes.mjs`. Needs triage. |
| `kill` | Not a fit (e.g., Big 4, vendor, defunct). Leave for dedupe. |
| `triaged` | Reviewed, template confirmed, contact URL verified. |
| `submitted` | Message posted via form. Set `message_sent` to today. |
| `replied_positive` | Got a reply willing to try the trial. |
| `replied_negative` | Got a decline. |
| `trial_started` | Signed up for the 30-day trial. |
| `feedback_received` | Shared feedback during/after trial. |
| `no_reply` | 30+ days since submit, nothing heard. |
| `bounced` | Form failed (captcha, 500, etc). |
