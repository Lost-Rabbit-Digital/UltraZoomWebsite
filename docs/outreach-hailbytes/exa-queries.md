# Exa Queries — HailBytes lead discovery (PoC)

Natural-language queries used by `scripts/find-leads-hailbytes.mjs` (search
mode) to find penetration-testing firms, MSSPs, vCISO practices, and security
awareness training shops with a public contact form. We pitch them on a free
30-day trial of either:

- **HailBytes ASM** — Attack Surface Management (offered to firms doing
  pentesting / red team / MSSP / vCISO work where external recon matters).
- **HailBytes SAT** — Security Awareness Training (offered to firms whose
  service catalog emphasizes phishing simulation, employee training, or human
  risk management).

The template-picker (`scripts/lib/template-picker-hailbytes.mjs`) chooses ASM
vs SAT per lead based on keywords in the title/summary/domain.

**Parsing rules for `find-leads-hailbytes.mjs`:**
- `## Heading` defines a section (used by `--sections` regex filter).
- Each `-` bullet is one query. Wrapping quotes are stripped.
- Blockquotes (`>`) are notes/context, ignored by the parser.

Exa is semantic, not keyword. Describe the *shape* of the page you want to
find — a homepage, a services page, a contact page — not just a topic.

---

## Pen testing firms (small / boutique)

- the homepage of a small US-based penetration testing firm offering managed services to SMBs
- a boutique penetration testing company website with a contact form
- the services page of a small offensive security consultancy
- a red team services provider's website with a "request a quote" form
- a small cybersecurity firm offering penetration testing and vulnerability assessments to mid-market clients
- the website of an independent pentest consultancy with three to twenty employees

## MSSPs and managed security service providers

- the homepage of a small managed security service provider (MSSP) with a contact form
- a managed detection and response (MDR) firm's services page
- a SOC-as-a-service provider serving small and medium businesses
- an MSSP that offers vulnerability management and continuous monitoring to clients
- a managed security firm's contact page with a web form
- a regional MSSP focused on healthcare or financial-services compliance

## vCISO and GRC consulting

- a virtual CISO services firm with a "contact us" page
- a fractional CISO consultancy serving small businesses
- a cybersecurity GRC consulting firm offering compliance and risk advisory
- a SOC 2 readiness consulting firm with a contact form
- a HIPAA compliance consultancy for healthcare practices
- a small cybersecurity advisory firm offering CISO-as-a-service

## Security awareness training providers

- the website of a small firm that delivers security awareness training to client companies
- a phishing simulation provider's services page with a contact form
- a security training and human risk management firm's homepage
- a managed phishing testing provider for SMBs
- a cyber awareness training consultancy serving regulated industries
- a firm offering employee cybersecurity training programs to small businesses

## Attack surface management resellers and partners

- a cybersecurity firm with a partners or reseller page mentioning attack surface management
- the services page of a firm offering external attack surface monitoring to clients
- a consultancy that resells or recommends ASM tooling to its customer base
- a managed security firm offering continuous external exposure monitoring
- a firm offering shadow IT discovery and asset inventory services

## Offensive security and red team consultancies

- a red team consultancy website with a contact form
- a small adversary emulation services firm
- an offensive security boutique offering social engineering assessments
- a firm offering purple team engagements to mid-market clients
- a niche pentest shop that publishes a public services menu and contact page

## SMB-focused cybersecurity consultancies

- a small business cybersecurity consultancy with a "get started" or contact form
- a cybersecurity firm tailored to law firms, accounting firms, or medical practices
- an IT MSP that has expanded into managed security services
- a managed IT and security provider for small businesses with a contact page

## Compliance-led security firms

- a cybersecurity consultancy specializing in PCI DSS assessments
- a CMMC compliance consulting firm for defense contractors
- a NIST 800-171 readiness consultancy
- a cybersecurity firm offering ISO 27001 implementation services

---

## Tips for editing this file

- Bias toward "homepage", "services page", "contact page" framings — these
  shapes win for finding firms (vs. blog posts that *talk about* pentesting).
- For US-targeting, mention "US-based", "regional", or specific verticals
  (healthcare, fintech, defense). Exa picks up on locality cues.
- If a section returns junk, tighten with size cues ("boutique", "small",
  "three to twenty employees", "mid-market") — keeps Big 4 and vendor noise
  out of results.
- Avoid mentioning HailBytes or specific products in queries — we're looking
  for *prospects*, not articles about us.
