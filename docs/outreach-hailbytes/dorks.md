# Outreach Search Dorks — HailBytes (PoC)

Brave / Google / Bing operators for finding pen-testing firms, MSSPs, vCISOs,
and security awareness training providers with a public contact form. Used by
`scripts/find-leads-hailbytes.mjs` (provider: brave).

We pitch one of two products depending on the firm's apparent service mix:
- **HailBytes ASM** — Attack Surface Management (pentest / MSSP / red team / vCISO).
- **HailBytes SAT** — Security Awareness Training (phishing simulation / human
  risk training shops).

The template-picker (`scripts/lib/template-picker-hailbytes.mjs`) makes the
ASM-vs-SAT call at write time.

---

## Legend

- `YEAR` — current year token, auto-substituted by the parser
- Quotes force exact match, minus signs exclude, `site:` scopes a domain,
  `inurl:` matches URL tokens, `intitle:` matches the `<title>`

---

## 1. Penetration testing firms

```
"penetration testing services" "contact us" -site:linkedin.com -site:indeed.com
"pen testing services" "request a quote" -site:linkedin.com
"penetration testing company" intitle:"contact" -site:linkedin.com
"offensive security services" "contact" -site:linkedin.com
"red team services" "get in touch" -site:linkedin.com
"web application penetration testing" "contact us" small business
"network penetration testing" inurl:contact -site:linkedin.com
"boutique penetration testing" -site:linkedin.com
"penetration testing firm" "free consultation" -site:linkedin.com
"pentest as a service" inurl:contact
```

## 2. MSSPs and managed security providers

```
"managed security services" "contact us" -site:linkedin.com -site:indeed.com
"managed security service provider" inurl:contact -site:linkedin.com
"MSSP" "request a demo" -site:linkedin.com -site:gartner.com
"managed detection and response" "contact us" -site:linkedin.com
"SOC as a service" "contact" small business -site:linkedin.com
"24/7 security monitoring" inurl:contact -site:linkedin.com
"managed SIEM" "request a quote" -site:linkedin.com
"managed XDR" "contact us" -site:linkedin.com
"managed cybersecurity" "schedule a call" -site:linkedin.com
```

## 3. vCISO / fractional CISO consultancies

```
"vCISO" "contact us" -site:linkedin.com
"virtual CISO" services inurl:contact -site:linkedin.com
"fractional CISO" "schedule a consultation" -site:linkedin.com
"CISO as a service" inurl:contact -site:linkedin.com
"cybersecurity advisory" "vCISO" -site:linkedin.com
"cybersecurity consulting" "virtual CISO" inurl:contact
```

## 4. Security awareness training providers

```
"security awareness training" "contact us" provider -site:linkedin.com
"phishing simulation" services "request a demo" -site:linkedin.com
"managed phishing testing" "contact" -site:linkedin.com
"security awareness program" provider inurl:contact -site:linkedin.com
"cybersecurity training for employees" "contact us" -site:linkedin.com
"human risk management" inurl:contact -site:linkedin.com
"phishing testing as a service" -site:linkedin.com
"security culture program" provider "contact" -site:linkedin.com
```

## 5. Compliance-led security firms (ASM upsell angle)

```
"SOC 2 readiness" consulting "contact us" -site:linkedin.com
"HIPAA compliance" cybersecurity firm inurl:contact -site:linkedin.com
"PCI DSS assessment" services "contact" -site:linkedin.com
"CMMC" assessment "contact us" -site:linkedin.com
"NIST 800-171" consulting "contact" -site:linkedin.com
"ISO 27001" implementation services inurl:contact -site:linkedin.com
"GRC consulting" cybersecurity "contact" -site:linkedin.com
```

## 6. Small / SMB-focused security consultancies

```
"cybersecurity for small business" services inurl:contact -site:linkedin.com
"cybersecurity firm" "for law firms" "contact" -site:linkedin.com
"cybersecurity for accounting firms" inurl:contact -site:linkedin.com
"cybersecurity for medical practices" inurl:contact -site:linkedin.com
"managed IT and security" "contact us" small business -site:linkedin.com
"SMB cybersecurity" services "contact" -site:linkedin.com
```

## 7. ASM-relevant: external attack surface, recon, exposure mgmt

```
"attack surface management" services "contact" -site:linkedin.com -site:gartner.com
"external attack surface" monitoring services "contact us" -site:linkedin.com
"continuous attack surface monitoring" "contact" -site:linkedin.com
"shadow IT discovery" services inurl:contact -site:linkedin.com
"asset discovery" cybersecurity firm "contact" -site:linkedin.com
"exposure management" services "contact us" -site:linkedin.com
```

## 8. Red team / adversary emulation

```
"adversary emulation" services "contact" -site:linkedin.com
"red team engagement" "request a quote" -site:linkedin.com
"purple team" services inurl:contact -site:linkedin.com
"social engineering assessment" services "contact" -site:linkedin.com
"physical penetration testing" services "contact" -site:linkedin.com
```

## 9. Regional / locality (US-focused)

```
"penetration testing" "Texas" inurl:contact -site:linkedin.com
"penetration testing" "Florida" inurl:contact -site:linkedin.com
"managed security services" "Chicago" inurl:contact -site:linkedin.com
"cybersecurity consulting" "Atlanta" inurl:contact -site:linkedin.com
"MSSP" "Northeast" inurl:contact -site:linkedin.com
"cybersecurity firm" "Pacific Northwest" inurl:contact -site:linkedin.com
```

## 10. Partner / reseller angle (warm leads for ASM/SAT resale)

```
"cybersecurity partners" program inurl:partners -site:linkedin.com
"MSSP partner program" "contact" -site:linkedin.com
"reseller program" cybersecurity "contact us" -site:linkedin.com
"channel partner" cybersecurity inurl:partners -site:linkedin.com
"technology partners" cybersecurity attack surface -site:linkedin.com
```

---

## Prospect categories we want coverage of

For the PoC phase the goal is breadth — get 100-300 distinct firms across
these buckets so triage can pick the strongest 20-50 to send first.

- Boutique pen-testing firms (3-50 employees)
- Regional MSSPs serving SMB / mid-market
- vCISO / fractional CISO consultancies
- Phishing simulation / security awareness training providers
- Compliance-led firms (SOC 2 / HIPAA / PCI / CMMC) that may bundle ASM
- IT MSPs that have added a security practice
- Red team / adversary emulation specialists

## Notes

- `linkedin.com` is excluded from most queries because LinkedIn pages don't
  give us a contact form. We want company websites.
- `gartner.com`, `indeed.com` are excluded because they show industry
  analysis / job postings rather than firms we can pitch.
- For each firm we'll auto-detect a contact URL (see `lib/contact-form.mjs`
  in the parent script). Firms with no detected form are still kept — humans
  can find a sales email during triage.
