# One-time Setup — Google Sheets + Exa + Brave + GitHub Action

Do this under **boden@lostrabbitdigital.com** once. After it's done, daily
lead discovery runs on cron and writes new rows to a shared Sheet that you
and your cofounder edit directly. No more CSVs in git.

Two search providers run on separate crons and append to the same Sheet:

- **Exa** (neural search) — `.github/workflows/find-leads.yml`, 13:00 UTC
- **Brave** (keyword + dorks) — `.github/workflows/find-leads-brave.yml`, 15:00 UTC

Dedup is global by URL, so a page found by both providers only appears once.

Total time: about 20 minutes (add ~2 min if you're also enabling Brave).

> **Want to smoke-test first?** Both workflows have a `csv: true` manual
> input that skips the Sheets checks entirely and uploads a CSV artifact
> instead. You only need the provider API key (Part C or Part F) for that
> path — handy for seeing what the rows look like before committing to
> Parts A/B/D. See `contact-form-prompt.md` → "Smoke-testing in CI".

---

## Part A — Create the Google Sheet (2 min)

1. Open https://sheets.new while signed in as boden@lostrabbitdigital.com.
2. Rename the file to **Ultra Zoom — Contact Form Leads**.
3. Rename the first tab (bottom left) from `Sheet1` to **Leads**. The script
   writes to this exact tab name; if you rename it later, update
   `SHEET_TAB` in `scripts/lib/sheets.mjs`.
4. Leave row 1 empty — the script writes the header on first run.
5. Share the sheet with your cofounder (Editor).
6. Grab the **Sheet ID** from the URL. In
   `https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit`
   the ID is `1AbCdEfGhIjKlMnOpQrStUvWxYz`. Save it — you'll paste it into
   GitHub in Part D.

---

## Part B — Create the Google service account + Workload Identity Federation (10 min)

A **service account** is a robot Google identity the GitHub Action acts as.
It's separate from your boden@ account. The SA gets Editor access only to
the sheet, so blast radius is limited to that one file.

**Why Workload Identity Federation (WIF) instead of a JSON key?** JSON
service-account keys are long-lived passwords you have to store in GitHub
Secrets; if leaked, they're valid forever. WIF lets GitHub's short-lived
OIDC token stand in for the SA — no secret to rotate. It's also what
Google recommends, and newer GCP orgs (including
`lostrabbitdigital.com`) block SA key creation by org policy, so WIF is
the only option.

Almost all of Part B is done from Google Cloud Shell (click the
`>_` terminal icon top right of https://console.cloud.google.com while
signed in as boden@). Copy-paste the commands as-is.

### B.1. Pick a Google Cloud project

1. Go to https://console.cloud.google.com. Sign in as
   boden@lostrabbitdigital.com.
2. Top bar → project selector → **NEW PROJECT**. Name it
   `ultrazoom-outreach`. Leave org / location defaults. Create.
3. Make sure that project is selected in the top bar before continuing.

### B.2. Enable the required APIs

In Cloud Shell:

```bash
gcloud config set project ultrazoom-outreach

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
`leads-writer@ultrazoom-outreach.iam.gserviceaccount.com`. It needs no
project-level roles — we grant access to one specific sheet in B.6.

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
  --attribute-condition="assertion.repository_owner=='Lost-Rabbit-Digital'"
```

The `attribute-condition` is the trust boundary — it blocks any GitHub
repo outside the `Lost-Rabbit-Digital` org from using this provider, even
if someone leaked the provider name. Don't skip it.

### B.5. Let the GitHub repo impersonate the service account

```bash
PROJECT_NUMBER=$(gcloud projects describe ultrazoom-outreach --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding \
  leads-writer@ultrazoom-outreach.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/Lost-Rabbit-Digital/UltraZoomWebsite"
```

Then print the two strings you'll paste into GitHub in Part D:

```bash
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
echo "GCP_SERVICE_ACCOUNT=leads-writer@ultrazoom-outreach.iam.gserviceaccount.com"
```

Save both.

### B.6. Share the sheet with the service account

1. Back in the Sheet (Part A) → **Share** button top right.
2. Paste `leads-writer@ultrazoom-outreach.iam.gserviceaccount.com`. Set
   role to **Editor**. Uncheck "Notify people" (it would bounce — service
   accounts have no mailbox).
3. **Share**.

The SA can now write to this sheet and nothing else in your Google account.

---

## Part C — Create the Exa API key (2 min)

1. Sign up at https://exa.ai with boden@lostrabbitdigital.com.
2. Dashboard → **API Keys** → create a new key. Name it `ultrazoom-gh-action`.
3. Copy the key. Exa's free tier currently covers our daily-cron volume —
   verify current pricing at https://exa.ai/pricing.

---

## Part D — Wire secrets and variables into GitHub (3 min)

1. Go to
   https://github.com/Lost-Rabbit-Digital/UltraZoomWebsite/settings/secrets/actions
2. Under **Repository secrets**, click **New repository secret** and add:
   - Name: `EXA_API_KEY`
     Value: the key from Part C.
3. Switch to the **Variables** tab (same page).
4. Click **New repository variable** and add all three:
   - Name: `LEADS_SHEET_ID`
     Value: the Sheet ID from Part A.6.
   - Name: `GCP_WORKLOAD_IDENTITY_PROVIDER`
     Value: the `projects/NUMBER/locations/global/.../providers/github-provider`
     string printed at the end of Part B.5.
   - Name: `GCP_SERVICE_ACCOUNT`
     Value: `leads-writer@ultrazoom-outreach.iam.gserviceaccount.com`.

> Why the WIF values live in Variables, not Secrets: neither the provider
> name nor the SA email grants any access on its own. Access is gated by
> the pool's `attribute-condition` (only `Lost-Rabbit-Digital/*` repos)
> plus the `workloadIdentityUser` binding scoped to this repo. Keeping
> them as Variables makes them visible in workflow logs, which helps when
> debugging.

---

## Part E — First run (3 min)

1. Go to the **Actions** tab → **Find leads (Exa)** workflow in the left
   sidebar.
2. Click **Run workflow** (top right). Pick `mode: both` and `limit: 5` for
   a tiny smoke test.
3. Watch the run. If auth is set up right, you'll see a line like
   `existing URLs in sheet: 0` followed by `appended N new rows.`
4. Open the Sheet. The header row should be there plus some data rows.
5. Once the smoke test works, the daily cron takes over. You can also
   keep using **Run workflow** for ad-hoc batches.

### Troubleshooting

- **"missing env vars"** — secrets/variables aren't set or the name is
  misspelled. They are case-sensitive.
- **"no Google credentials found"** — the `google-github-actions/auth`
  step didn't run or didn't receive the WIF inputs. Check that
  `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT` are set as
  repo **variables** (not secrets) and that the workflow has
  `permissions: id-token: write`.
- **"Permission denied" from IAM Credentials / STS** — the repo isn't
  bound to the SA. Re-run the `add-iam-policy-binding` from Part B.5 and
  double-check the `principalSet://` string matches
  `attribute.repository/Lost-Rabbit-Digital/UltraZoomWebsite` exactly.
- **"sheets read header 403"** — the service account isn't shared on the
  sheet (Part B.6) or the Sheets API isn't enabled (Part B.2).
- **"Exa /search 401"** — API key is wrong or expired.
- **Action completes but sheet stays empty** — you may be hitting dedup
  against the existing `leads.json` URLs that were already seen. That's
  working as intended; try `--mode search` or edit `exa-queries.md` to
  widen the net.

---

## Part F — (Optional) Add the Brave Search provider (2 min)

Brave gives us a second, independent lead stream using keyword dorks from
`docs/outreach/dorks.md`. It's free-tier friendly (1 request/sec) and covers
queries Exa's neural search misses, like exact-match site: or intitle:
operators. Both providers write to the same Sheet; dedup runs globally on
the URL column.

1. Sign up at https://api-dashboard.search.brave.com with
   boden@lostrabbitdigital.com. Pick the **Free** plan (requires a card on
   file but won't charge at our volume — verify at
   https://brave.com/search/api).
2. Dashboard → **API Keys** → **Add API Key**. Name it
   `ultrazoom-gh-action`. Copy the key.
3. Go to
   https://github.com/Lost-Rabbit-Digital/UltraZoomWebsite/settings/secrets/actions
4. Add a new repository secret:
   - Name: `BRAVE_SEARCH_KEY`
     Value: the key from step 2.
5. Go to **Actions** tab → **Find leads (Brave)** → **Run workflow**. Use
   `limit: 5` for the smoke test. You should see a Step Summary reporting
   queries run and rows appended.
6. Once the smoke test works, the daily cron picks up automatically at
   15:00 UTC (06:00 PT — 2 hours after the Exa run).

The Brave workflow only needs `BRAVE_SEARCH_KEY` in addition to the shared
`LEADS_SHEET_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, and
`GCP_SERVICE_ACCOUNT` variables.

---

## Operating notes for daily use

- Both you and your cofounder edit status, `assigned_to`, etc. directly in
  the Sheet. The script only appends new rows, never edits existing ones.
- Set `assigned_to` before working a row so you don't double-pitch.
- See `contact-form-templates.md` for the message library and
  `contact-form-prompt.md` for the end-to-end workflow.
- To pause the daily cron, disable the workflow from the Actions tab; the
  manual dispatch button still works.
