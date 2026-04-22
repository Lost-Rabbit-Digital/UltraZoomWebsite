// Pick a contact-form template + draft a short message for the HailBytes
// outreach lane (PoC).
//
// Canonical human-readable templates live in
// docs/outreach-hailbytes/contact-form-templates.md. The drafts below mirror
// them as short, form-safe variants (no markdown, one URL, ~500-800 chars)
// so the `message_draft` column is copy-paste-ready.
//
// Classification priority (first match wins):
//   1. SAT-primary signals (phishing simulation / security awareness
//      training / human risk) → HailBytes SAT pitch.
//   2. Pen-test / red-team signals                → HailBytes ASM (pentest).
//   3. MSSP / MDR / SOC-as-a-service signals      → HailBytes ASM (MSSP).
//   4. vCISO / GRC / compliance signals           → HailBytes ASM (vCISO).
//   5. Fallback                                   → HailBytes ASM (generic),
//      which mentions both products and lets the recipient self-select.
//
// Rotation: two variants per bucket, selected deterministically from a hash
// of the URL so re-runs produce the same draft for the same lead.

const SIGN_OFF = "— David McHale, HailBytes\nhttps://hailbytes.com";

// Order matters: SAT first, then pentest, MSSP, vCISO, then fallback.
const BUCKETS = [
  {
    id: "hb-sat-training",
    pattern:
      /\b(phishing\s+simulation|security\s+awareness\s+training|awareness\s+training|human\s+risk|phishing\s+testing|phishing\s+training|security\s+culture|user\s+training|employee\s+training|knowbe4)\b/i,
  },
  {
    id: "hb-asm-pentest",
    pattern:
      /\b(penetration\s+testing|pen[-\s]?test(?:ing)?|pentest(?:er|ing)?|offensive\s+security|red\s+team|adversary\s+emulation|purple\s+team|social\s+engineering\s+assessment|ethical\s+hacking)\b/i,
  },
  {
    id: "hb-asm-mssp",
    pattern:
      /\b(mssp|managed\s+security\s+service|managed\s+detection|mdr\b|xdr\b|managed\s+siem|soc[-\s]?as[-\s]?a[-\s]?service|soc\s+as\s+a\s+service|24\/7\s+monitoring|managed\s+cybersecurity|security\s+operations\s+center)\b/i,
  },
  {
    id: "hb-asm-vciso",
    pattern:
      /\b(vciso|virtual\s+ciso|fractional\s+ciso|ciso[-\s]?as[-\s]?a[-\s]?service|grc\s+consult|compliance\s+consult|soc\s*2|hipaa|pci[-\s]?dss|cmmc|nist\s*800|iso\s*27001|risk\s+advisory|cybersecurity\s+advisory)\b/i,
  },
];

const TEMPLATES = {
  "hb-asm-pentest": [
    () =>
`Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management platform built for pen-testing and offensive-security firms. It orchestrates 30+ recon tools (subfinder, nmap, nuclei, httpx, ffuf, and more) into one continuous pipeline, runs in your own Azure or AWS tenant, and has no per-asset fee — so you can monitor every engagement's external surface without per-target licensing.

Would you try it free for 30 days and share honest feedback? Happy to set up a short demo.

${SIGN_OFF}`,
    () =>
`Hi,

David McHale from HailBytes here. We're launching HailBytes ASM — an attack surface management platform aimed at pentest firms that want continuous external recon across all their engagements without per-target licensing. It chains 30+ tools (subfinder, nmap, nuclei, httpx, ffuf, etc.) into one pipeline, runs in your own cloud tenant, correlates findings in Postgres, and adds AI-assisted triage.

I'd love to get it in front of working pentesters. Free 30-day trial in exchange for feedback — interested?

${SIGN_OFF}`,
  ],
  "hb-asm-mssp": [
    () =>
`Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management platform built for MSSPs that want to add continuous external recon to their managed service catalog. It runs 7 automated scan phases across 30+ tools, deploys in your own Azure or AWS tenant (so client data never leaves your cloud), supports multi-tenant project isolation and RBAC, and has no per-asset fee — unlimited targets at every tier.

Would you try it free for 30 days and share feedback from an MSSP's perspective?

${SIGN_OFF}`,
    () =>
`Hi,

David McHale from HailBytes here. We're launching HailBytes ASM — an attack surface management platform designed for MSSPs and MDR providers. It gives you continuous external recon across all your clients from a single deployment in your own tenant, with multi-tenant project isolation, RBAC, and unlimited targets (no per-asset fee). AI-powered triage generates executive reports automatically.

Free 30-day trial — I'd love your feedback on whether it fits into an MSSP workflow. Happy to set up a demo.

${SIGN_OFF}`,
  ],
  "hb-asm-vciso": [
    () =>
`Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management platform that fits naturally into a vCISO or GRC engagement. It gives your clients continuous external-asset discovery and vulnerability monitoring from a single deployment in their own cloud tenant, with audit-logged findings that map to SOC 2, HIPAA, and PCI controls. No per-asset fee — unlimited targets.

Would you try it free for 30 days and share feedback? Useful to hear whether it fits the vCISO toolkit.

${SIGN_OFF}`,
    () =>
`Hi,

David McHale from HailBytes here. We're launching HailBytes ASM — an attack surface management platform that's been getting interest from vCISO and compliance-led practices. Deploys into a client's own Azure or AWS tenant, correlates 30+ tools into one scan pipeline, produces executive-ready risk reports via AI, and has full audit logging for SOC 2, HIPAA, and PCI programs. No per-asset fee at any tier.

Free 30-day trial in exchange for honest feedback. Interested?

${SIGN_OFF}`,
  ],
  "hb-sat-training": [
    () =>
`Hi there,

David McHale here — I'm launching HailBytes SAT, a security awareness training and phishing simulation platform built for firms that deliver SAT to their clients. It runs in your own Azure or AWS tenant (no client data in a vendor cloud), is Entra ID native with SCIM, has AI-assisted template generation, and — critically — has no per-user fee. Unlimited users on a single VM.

Would you try it free for 30 days and share feedback? I'd love to hear from a firm that actually runs awareness programs.

${SIGN_OFF}`,
    () =>
`Hi,

David McHale from HailBytes here. We're launching HailBytes SAT — a phishing simulation and security awareness training platform for MSSPs, consultancies, and training providers that deliver SAT as a service. One VM in your (or your client's) cloud tenant supports up to 5,000 users with no per-user licensing. AI-assisted template generation, Entra ID SSO, and webhook-driven SIEM integration are built in.

Free 30-day trial — would you try it and share feedback? Happy to set up a demo.

${SIGN_OFF}`,
  ],
  "hb-asm-generic": [
    () =>
`Hi there,

David McHale here — I'm launching HailBytes ASM, an attack surface management platform built for cybersecurity firms that want to add continuous external recon to their client offerings. It runs in your own cloud tenant, chains 30+ recon and vulnerability tools into one automated pipeline, has AI-powered triage, and charges no per-asset fee — unlimited targets at every tier. We're also launching HailBytes SAT (phishing simulation, no per-user fee) in the same family, in case that's a closer fit.

Free 30-day trial of either in exchange for feedback. Which would be the better fit for your team?

${SIGN_OFF}`,
    () =>
`Hi,

David McHale from HailBytes here. We're launching two platforms aimed at cybersecurity firms: HailBytes ASM (attack surface management, 30+ tools, unlimited targets, no per-asset fee) and HailBytes SAT (phishing simulation and awareness training, unlimited users, no per-user fee). Both deploy into your own Azure or AWS tenant, so client data stays in your cloud.

We're offering a free 30-day trial of either in exchange for honest feedback. Would one fit your current service mix better than the other?

${SIGN_OFF}`,
  ],
};

function hash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function pickTemplate(result) {
  const blob = `${result.title || ""} ${result.summary || ""} ${result.domain || ""}`;
  const bucket = BUCKETS.find((b) => b.pattern.test(blob));
  const id = bucket ? bucket.id : "hb-asm-generic";
  const variants = TEMPLATES[id];
  const idx = hash(result.url || "") % variants.length;
  const draft = variants[idx]({
    title: result.title || "",
    domain: result.domain || "",
  });
  return { templateId: id, draft };
}
