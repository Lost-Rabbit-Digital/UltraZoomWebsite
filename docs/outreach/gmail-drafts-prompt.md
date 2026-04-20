# Gmail MCP Drafting Prompt — Ultra Zoom

Prompts for getting outreach drafts into the `boden@lostrabbitdigital.com` Gmail mailbox using the Gmail MCP server, and for updating `leads.json` to reflect what's scheduled.

There are **two** versions:

1. **Interactive** — paste into a Claude Code session where you're watching. Claude will ask before sending and walk through each lead.
2. **Routines-compatible** — self-contained, non-interactive, designed to be scheduled via Claude Routines. Runs end-to-end, commits changes, and opens a PR.

Both assume:
- The Gmail MCP server is configured with access to `boden@lostrabbitdigital.com`
- The repo is `lost-rabbit-digital/ultrazoomwebsite` with leads in `docs/outreach/leads.json` and drafts in `docs/outreach/drafts/`

---

## Schema update: lead status field

Add / maintain these status values on each lead in `leads.json`:

| Status | Meaning |
|---|---|
| `research_pending` | Prospect in list but no contact verified yet |
| `draft_ready` | Draft file exists, email not in Gmail yet |
| `draft_scheduled` | Gmail draft created, awaiting human review + send |
| `sent` | Human sent the draft from Gmail |
| `replied_positive` | Got a reply expressing interest / willingness to list |
| `replied_negative` | Declined or not interested |
| `no_reply` | Sent >14 days ago, no response |
| `followup_scheduled` | Follow-up draft in Gmail |
| `linked` | Ultra Zoom mentioned / linked in their content |
| `dead` | Bounced, invalid, or opted out |

When the drafting workflow creates a Gmail draft, it **must** set:
- `status: "draft_scheduled"`
- `gmail_draft_id: <draft id returned by MCP>`
- `scheduled_date: <ISO date>`

---

## Interactive prompt (watching-the-loop)

Paste into a Claude Code session with Gmail MCP and GitHub MCP available:

```
I want you to convert pending outreach drafts into personalized Gmail drafts in
boden@lostrabbitdigital.com, then update the lead file to reflect what was scheduled.

Workflow:
1. Read docs/outreach/leads.json. Build a list of leads where status is
   "draft_ready" and a draft file exists at the path in draft_file.
2. For each lead (stop and ask me before moving past 5 at a time):
   a. Read the draft markdown file.
   b. Extract the To, Subject, and body (everything after the "---" separator).
   c. Light personalization pass: look at the article URL and pitch_angle, and
      tighten the first paragraph to reference a specific detail. DO NOT
      rewrite from scratch. Keep my voice.
   d. Create a Gmail draft via the Gmail MCP (create_draft) with:
        - To: contact_email
        - Subject: from the draft file
        - Body: the personalized plain-text body + sign-off
        - Label the draft with "UltraZoom/Outreach" (create the label if missing)
   e. Capture the returned draft id.
   f. Update the lead in leads.json:
        status → "draft_scheduled"
        gmail_draft_id → <id>
        scheduled_date → today's ISO date
   g. Show me a preview of the draft before it goes in Gmail and ask for
      approval. Apply my feedback before creating the draft.
3. After the batch, commit the leads.json change on the current branch with
   message "outreach: schedule N drafts in Gmail".

Safety:
- NEVER send; only create drafts.
- NEVER touch drafts already labeled "UltraZoom/Outreach" (idempotent).
- If contact_email is missing, "needs_verification", or status is not
  "draft_ready", skip the lead and print why.
- Cap at 10 drafts per run so we don't flood the inbox.
- If the Gmail MCP returns an error for a lead, mark it
  status: "draft_error" with an error_note, and move on.

Start by reading leads.json and printing the list of leads you plan to
process, sorted by id. Wait for my "go" before creating any Gmail drafts.
```

---

## Routines-compatible prompt (autonomous, PR-at-end)

For scheduling via **Claude Routines**. The routine should have access to:
- Gmail MCP (for `boden@lostrabbitdigital.com`)
- GitHub MCP (scoped to `lost-rabbit-digital/ultrazoomwebsite`)

Paste the block below as the routine body:

```
ROUTINE: schedule-outreach-drafts
SCHEDULE: weekly, Mondays 8am PT (or manual)
REPO: lost-rabbit-digital/ultrazoomwebsite
BRANCH: create a new branch off main named `claude/schedule-drafts-YYYY-MM-DD`

GOAL
Pull up to 10 ready outreach drafts, create personalized Gmail drafts in
boden@lostrabbitdigital.com, update leads.json, and open a PR for review.
Never send. Never dedupe against already-scheduled drafts.

STEPS

1. Checkout main, pull latest. Create the branch above.

2. Read docs/outreach/leads.json. Filter leads where:
   - status == "draft_ready"
   - contact_email exists and does not contain "needs_verification"
   - draft_file exists on disk
   - lead not already in docs/outreach/scheduled-log.json (see step 6)
   Sort by id ascending. Take the first 10.

3. For each lead:
   a. Read drafts/<draft_file>.
   b. Parse: To, Subject, Send window, and the body (after the first "---").
   c. Personalize paragraph 1 only: reference a concrete detail from the
      article (author name, specific subsection, date). Keep the rest as-is.
      If you can't fetch the article, skip personalization — do not fabricate.
   d. Via Gmail MCP:
        - Ensure label "UltraZoom/Outreach" exists. Create if missing.
        - create_draft with To, Subject, plain-text body + sign-off block.
        - Apply the label to the draft.
   e. Record the returned draft id.

4. Update leads.json entry for each processed lead:
     status          → "draft_scheduled"
     gmail_draft_id  → <id>
     scheduled_date  → today ISO (YYYY-MM-DD)
     scheduled_by    → "claude-routine"

5. If any lead errored: do NOT mutate leads.json for that lead; log it in the
   PR body under "## Errors".

6. Append an entry per processed lead to docs/outreach/scheduled-log.json:
     { "id": <lead_id>, "gmail_draft_id": <id>, "date": <iso> }
   (create the file if missing; initialize as { "scheduled": [] })

7. Commit on the branch:
     git add docs/outreach/leads.json docs/outreach/scheduled-log.json
     git commit -m "outreach: schedule N Gmail drafts (routine YYYY-MM-DD)"
   Push to origin.

8. Open a PR against main titled:
     "Outreach: N drafts scheduled in Gmail (YYYY-MM-DD)"
   PR body (markdown):
     ## Summary
     Scheduled N Ultra Zoom outreach drafts in Gmail (label UltraZoom/Outreach).
     All drafts await manual review and send in the mailbox — nothing was sent.

     ## Drafts scheduled
     | Lead id | Publication | Subject | Gmail draft id |
     | --- | --- | --- | --- |
     | ...table of processed leads... |

     ## Errors
     ...per-lead error notes if any, else "None"...

     ## Next steps
     - Review each draft in Gmail (search: `label:UltraZoom/Outreach is:draft`).
     - Send in small batches (3–5/day, Tue–Thu window).
     - Merge this PR to record what was scheduled.

GUARDRAILS
- Never call Gmail send / send_draft. Only create drafts.
- Never modify files outside docs/outreach/leads.json, docs/outreach/scheduled-log.json.
- Never dedupe by scanning Gmail — use the scheduled-log file as source of truth.
- If fewer than 10 leads are eligible, process what's available and note
  in the PR body.
- If zero eligible leads, do not open an empty PR. Exit with a short
  summary message.
- Cap at 10 drafts per run. Hard stop.

EXIT CRITERIA
- PR open with label `outreach` and (if configured) reviewer = @boden.
- Or: clean no-op message if nothing eligible.
```

---

## Manual verification checklist (after the routine runs)

Run these spot-checks before sending any draft:

- [ ] Open Gmail → search `label:UltraZoom/Outreach is:draft`
- [ ] Spot-check 3 drafts: subject, greeting name, article reference
- [ ] Verify `leads.json` diff in the PR matches the draft list
- [ ] Send 3–5 drafts/day Tue–Thu, adjusting per author timezone
- [ ] After sending, flip status to `sent` manually or via follow-up routine

---

## Companion routine: follow-up sweeper (future)

Once drafts start having `status: sent`, schedule a second routine that:
- Finds leads with `status: sent` and `sent_date` older than 7 days
- Creates a short follow-up Gmail draft per the template in `templates.md`
- Updates `status: followup_scheduled`

Same guardrails: never send, open a PR, cap at 10 per run.
