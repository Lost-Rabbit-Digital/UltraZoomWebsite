# HailBytes opener prompt

You are writing the first 1–2 sentences of a cold email from David McHale (Principal at HailBytes) to a decision-maker at a security services company. The email pitches one of two products as a free / reduced-rate trial:

- **HailBytes SAT** (https://hailbytes.com/sat) — phishing simulation + security awareness training they can resell or run for clients.
- **HailBytes ASM** (https://hailbytes.com/asm) — reNgine Cloud, an attack-surface-management platform they can self-host on AWS to automate recon before pen test engagements.

You will be told which product to anchor in the second sentence. The product URL is the human's call-to-action; do not put the URL in your output, but write the second sentence so a single follow-up sentence ("here's the page: <URL>") lands naturally.

The recipient works at:

- **Company:** {company}
- **Domain:** {domain}
- **What they do:** {description}
- **Recipient title:** {title}
- **Anchor product:** {product}
- **Anchor product URL (for the human's follow-up — do NOT include in output):** {product_url}

Write **exactly two sentences**, plain text, no markdown:

1. **First sentence**: a concrete, specific observation about what the company does. Reference their actual service mix, vertical, or stack from the description above. No flattery, no "I noticed", no "I came across".
2. **Second sentence**: the implication — what the work in sentence 1 means for their day-to-day (e.g. tight pen-test timelines, client recon overhead, awareness-training programs they have to deliver, compliance pressure from regulated clients). This sentence sets up the product pitch that the human will write next.

Hard constraints:

- **Two sentences total. 50 words maximum across both.**
- No em dashes (`—` or `–`). Use hyphens, commas, or periods.
- Do not name the product, do not include any URL, do not pitch, do not introduce yourself.
- Do not begin with "I", "Hi", "Hello", "Hope", "Just". Start with the company's name or a noun describing them.
- No marketing words: leverage, synergy, solutions, transform, empower, robust, cutting-edge, world-class.
- Do not put quotes around the output.
- Output **only** the two sentences. No preamble, no explanation, no signature.
