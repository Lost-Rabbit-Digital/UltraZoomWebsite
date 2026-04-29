# Outreach pipeline — Sheets + WIF setup

One-time setup for the manual-Apollo-CSV → AI drafts → Sheets pipeline
(`outreach/run_ultrazoom.py`). After this is in place, dropping a CSV
in `outreach/inbox/<campaign>/` and pushing to `main` triggers a GitHub
Action that writes personalized Touch 1 + Touch 2 drafts to the
campaign's Google Sheet, ready for MailMeteor import.

This repo runs **two campaigns**:
- **Ultra Zoom Realtors** → its own Sheet, tabs `UZ_Realtors_T1` + `UZ_Realtors_T2`
- **Ultra Zoom Press** → its own Sheet, tabs `UZ_Press_T1` + `UZ_Press_T2`

The HailBytes campaigns (ASM, SAT) live in the sister repo
`hailbytes-static` and re-use the same service account configured below
— see that repo's `docs/outreach/sheets-setup.md` for the
extra-binding step.

Setup map:
- **Part A** — Create the two Google Sheets (~3 min each)
- **Part B** — One-time GCP project + service account + WIF provider (~10 min)
- **Part C** — Share each Sheet with the service-account email (~1 min each)
- **Part D** — GitHub Secrets and Variables (~2 min)
- **Part E** — First run / smoke test (~5 min)

---

## Part A — Create the Sheets

Do once per campaign. Run signed in as `boden@lostrabbitdigital.com`.

1. Open <https://sheets.new>.
2. For UZ Realtors, rename the file to **Ultra Zoom Realtors — Cold Outreach**.
   For UZ Press, repeat for a separate file named **Ultra Zoom Press —
   Cold Outreach**.
3. Rename the first tab from `Sheet1` to the **T1 tab name**:
   - UZ Realtors → `UZ_Realtors_T1`
   - UZ Press → `UZ_Press_T1`
4. Add a second tab with the **T2 tab name**:
   - UZ Realtors → `UZ_Realtors_T2`
   - UZ Press → `UZ_Press_T2`
5. Leave row 1 empty — the pipeline writes the header on first run.
6. Share with your cofounder (Editor).
7. Grab the **Sheet ID** from the URL (the long string between
   `/d/` and `/edit`). Save both Sheet IDs — they go in Part D.

The pipeline uses one Sheet per campaign instead of one Sheet with many
tabs because it makes sharing scopes simpler: a contractor working on
Press never needs Editor access to Realtors, and a domain-reputation
investigation only needs the affected campaign's Sheet.

---

## Part B — GCP project + service account + Workload Identity Federation

A **service account** is a robot Google identity the GitHub Action acts
as. The SA gets Editor access only to the Sheets in Part A, so blast
radius is limited to those files.

**Why Workload Identity Federation (WIF) instead of a JSON key?** JSON
service-account keys are long-lived passwords you have to store in
GitHub Secrets; if leaked, they're valid forever. WIF lets GitHub's
short-lived OIDC token stand in for the SA — no secret to rotate. It's
also what Google recommends, and newer GCP orgs (including
`lostrabbitdigital.com`) block SA key creation by org policy, so WIF is
the only option.

Almost all of Part B is done from Google Cloud Shell (click the
`>_` terminal icon top right of <https://console.cloud.google.com>
while signed in as `boden@`). Copy-paste the commands as-is.

### B.1. Pick a Google Cloud project

1. Go to <https://console.cloud.google.com>. Sign in as
   `boden@lostrabbitdigital.com`.
2. Top bar → project selector → **NEW PROJECT**. Name it
   `lrd-outreach`. Leave org / location defaults. Create.
3. Make sure that project is selected in the top bar before continuing.

### B.2. Enable the required APIs

In Cloud Shell:

```bash
gcloud config set project lrd-outreach

gcloud services enable \
  sheets.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com
```

### B.3. Create the service account

```bash
gcloud iam service-accounts create leads-writer \
  --display-name="Leads writer (GitHub Actions)"
```

The SA's email is now
`leads-writer@lrd-outreach.iam.gserviceaccount.com`. It needs no
project-level roles — we grant access to specific Sheets in Part C.

### B.4. Create the Workload Identity Pool and GitHub provider

```bash
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner in ['Lost-Rabbit-Digital', 'HailBytes']"
```

The `attribute-condition` is the trust boundary — it blocks any GitHub
repo outside the two listed orgs from using this provider. Including
`HailBytes` here lets the same pool be re-used by the
`hailbytes-static` repo for the HB campaigns; the actual repo-level
binding still has to be added in B.5 before that repo can act as the
SA.

### B.5. Let the GitHub repos impersonate the service account

Run **both** bindings — one for this repo (UZ campaigns) and one for
the HailBytes repo. The principal-set is repo-scoped, so each binding
only allows that one repo to mint tokens for the SA:

```bash
PROJECT_NUMBER=$(gcloud projects describe lrd-outreach --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding \
  leads-writer@lrd-outreach.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/Lost-Rabbit-Digital/UltraZoomWebsite"

gcloud iam service-accounts add-iam-policy-binding \
  leads-writer@lrd-outreach.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/HailBytes/hailbytes-static"
```

Then print the two strings you'll paste into GitHub in Part D:

```bash
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "GCP_SERVICE_ACCOUNT=leads-writer@lrd-outreach.iam.gserviceaccount.com"
```

Save both. The same two values get pasted into both repos' Variables.

---

## Part C — Share each Sheet with the SA

For **each** Sheet from Part A:

1. Open the Sheet → **Share** button top right.
2. Paste `leads-writer@lrd-outreach.iam.gserviceaccount.com`. Set role
   to **Editor**. Uncheck "Notify people" (service accounts have no
   mailbox so the notification would bounce).
3. **Share**.

The SA can now write to those Sheets and nothing else in your Drive.

---

## Part D — Wire secrets and variables into GitHub

Go to
<https://github.com/Lost-Rabbit-Digital/UltraZoomWebsite/settings/secrets/actions>.

### Secrets

Under **Repository secrets** → **New repository secret**:

- **`ANTHROPIC_API_KEY`** — your Anthropic console key. The pipeline
  uses this for Claude personalization. Pay-as-you-go; ~$0.01–0.05 per
  75-lead batch on Haiku with prompt caching.

### Variables

Under **Repository variables** → **New repository variable** add four:

- **`GCP_WORKLOAD_IDENTITY_PROVIDER`** — the
  `projects/.../providers/github-provider` string from B.5.
- **`GCP_SERVICE_ACCOUNT`** — `leads-writer@lrd-outreach.iam.gserviceaccount.com`.
- **`GOOGLE_SHEET_ID_UZ_REALTORS`** — the UZ Realtors Sheet ID from A.7.
- **`GOOGLE_SHEET_ID_UZ_PRESS`** — the UZ Press Sheet ID from A.7.

> **Why the WIF + Sheet IDs live in Variables, not Secrets:** none of
> these grants access on its own. Access is gated by the pool's
> `attribute-condition` plus the repo-scoped `workloadIdentityUser`
> bindings in B.5. Sheet IDs are URL-visible to anyone who can open
> the sheet. Keeping them as Variables makes them visible in workflow
> logs, which helps debugging.

---

## Part E — First run / smoke test

The runner has a `--dry-run` mode that exercises everything except the
Anthropic call and the Sheets write. Use it to confirm the workflow
plumbing is right before spending API credit.

1. Drop a tiny test CSV at
   `outreach/inbox/ultrazoom-realtors/<YYYY-MM-DD>.csv` on the
   `claude/google-sheets-email-campaigns-nMmDS` branch (or `main`,
   if you've merged). The user's pasted 2-row sample works for shape
   testing.
2. **Actions** tab → **Ultra Zoom outreach** → **Run workflow**.
   Pick:
   - Branch: the branch holding the test CSV
   - `campaign`: `realtors`
   - `dry_run`: `true`
3. Watch the run. Expect to see:
   ```
   ingest: <date>.csv → N candidates (skipped 0 unverified, 0 no-email)
   personalization done. t1=N t2=N drops={}
   [dry-run] would append N rows to sheet ... tab 'UZ_Realtors_T1'
   ```
4. Switch `dry_run` to `false` and re-run. The workflow now invokes
   Claude and writes rows to the Sheet. Open the Sheet — header row
   present, N data rows below it on each tab.

Repeat with `campaign: press` to verify the Press path.

### Troubleshooting

- **"missing env vars"** — secrets/variables aren't set or the name is
  misspelled. Names are case-sensitive.
- **"no Google credentials found"** — the
  `google-github-actions/auth` step didn't run or didn't receive the
  WIF inputs. Check that `GCP_WORKLOAD_IDENTITY_PROVIDER` and
  `GCP_SERVICE_ACCOUNT` are set as repo **variables** (not secrets)
  and that the workflow has `permissions: id-token: write`.
- **"Permission denied" from IAM Credentials / STS** — the repo isn't
  bound to the SA. Re-run the `add-iam-policy-binding` from B.5 and
  double-check the `principalSet://` string matches
  `attribute.repository/Lost-Rabbit-Digital/UltraZoomWebsite` exactly.
- **"sheets read header 403"** — the SA isn't shared on the Sheet
  (Part C) or the Sheets API isn't enabled (Part B.2).
- **Validation drops every lead** — check the campaign's required
  merge tags in `outreach/campaign_config.py`. The AI is instructed
  to embed them verbatim; if the model drifts, check
  `outreach/prompts/<campaign>_<touch>.md` for the reference template
  and tighten the rules.
- **Quota exceeded on Anthropic** — Haiku is rate-limited by tokens-
  per-minute. Spread out batches or pass `--limit 25` to cap the
  per-run lead count.

---

## Operating notes

- The pipeline appends only — never overwrites existing rows. Manual
  edits in MailMeteor-managed columns (Date sent, Opens, etc.) are
  preserved on every run.
- Sheet-side dedupe runs by lowercased `editor_email` before append:
  re-pushing the same Apollo CSV is safe but a no-op.
- To pause, just don't push CSVs. There's no cron.
- The same `leads-writer` SA powers the HailBytes outreach pipelines
  via the second binding in B.5 — no separate SA needed.
