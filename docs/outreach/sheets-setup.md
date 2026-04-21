# One-time Setup — Google Sheets + Exa + Brave + GitHub Action

Do this under **boden@lostrabbitdigital.com** once. After it's done, daily
lead discovery runs on cron and writes new rows to a shared Sheet that you
and your cofounder edit directly. No more CSVs in git.

Two search providers run on separate crons and append to the same Sheet:

- **Exa** (neural search) — `.github/workflows/find-leads.yml`, 13:00 UTC
- **Brave** (keyword + dorks) — `.github/workflows/find-leads-brave.yml`, 15:00 UTC

Dedup is global by URL, so a page found by both providers only appears once.

Total time: about 20 minutes (add ~2 min if you're also enabling Brave).

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

## Part B — Create the Google service account (10 min)

A **service account** is a robot Google identity the GitHub Action signs in
as. It's separate from your boden@ account. The SA gets Editor access only
to the sheet, so blast radius is limited to that one file.

### B.1. Pick a Google Cloud project

1. Go to https://console.cloud.google.com. Sign in as
   boden@lostrabbitdigital.com.
2. Top bar → project selector → **NEW PROJECT**. Name it
   `ultrazoom-outreach`. Leave org / location defaults. Create.
3. Make sure that project is selected in the top bar before continuing.

### B.2. Enable the Sheets API

1. Left nav → **APIs & Services → Library**.
2. Search "Google Sheets API". Click it. Click **Enable**.

### B.3. Create the service account

1. Left nav → **IAM & Admin → Service Accounts**.
2. Click **+ CREATE SERVICE ACCOUNT** at the top.
3. Name it `leads-writer`. Service account ID auto-fills; leave it.
4. Click **CREATE AND CONTINUE**.
5. "Grant this service account access to project" → **Skip** (no project
   roles needed — we only grant access to one specific sheet).
6. "Grant users access to this service account" → **Skip**.
7. Click **DONE**.

### B.4. Generate its JSON key

1. In the Service Accounts list, click the `leads-writer` row.
2. Top tabs → **KEYS**.
3. **ADD KEY → Create new key → JSON → CREATE**.
4. A file named something like `ultrazoom-outreach-xxxx.json` downloads.
   **Keep this safe** — it's a password. Don't commit it to git.
5. Open the JSON file in a text editor. Copy the value of `client_email` —
   it looks like
   `leads-writer@ultrazoom-outreach-xxxx.iam.gserviceaccount.com`.

### B.5. Share the sheet with the service account

1. Back in the Sheet (Part A) → **Share** button top right.
2. Paste the `client_email` from step B.4. Set role to **Editor**. Uncheck
   "Notify people" (it would bounce — service accounts have no mailbox).
3. **Share**.

The SA can now write to this sheet and nothing else in your Google account.

---

## Part C — Create the Exa API key (2 min)

1. Sign up at https://exa.ai with boden@lostrabbitdigital.com.
2. Dashboard → **API Keys** → create a new key. Name it `ultrazoom-gh-action`.
3. Copy the key. Exa's free tier currently covers our daily-cron volume —
   verify current pricing at https://exa.ai/pricing.

---

## Part D — Wire secrets into GitHub (3 min)

1. Go to
   https://github.com/Lost-Rabbit-Digital/UltraZoomWebsite/settings/secrets/actions
2. Under **Repository secrets**, click **New repository secret** and add:
   - Name: `EXA_API_KEY`
     Value: the key from Part C.
   - Name: `GOOGLE_SHEETS_SA_KEY`
     Value: **the entire contents of the JSON file from Part B.4**, as-is.
     Open the file, select all, paste. Do not reformat or strip newlines.
3. Switch to the **Variables** tab (same page).
4. Click **New repository variable** and add:
   - Name: `LEADS_SHEET_ID`
     Value: the Sheet ID from Part A.6.

> Why one goes in Secrets and one in Variables: the sheet ID isn't sensitive
> (the SA is the only thing that can write to it). Keeping it as a Variable
> makes it visible in workflow logs, which helps when debugging.

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
- **"sheets read header 403"** — the service account isn't shared on the
  sheet (Part B.5) or the Sheets API isn't enabled (Part B.2).
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
`GOOGLE_SHEETS_SA_KEY` secret and `LEADS_SHEET_ID` variable.

---

## Operating notes for daily use

- Both you and your cofounder edit status, `assigned_to`, etc. directly in
  the Sheet. The script only appends new rows, never edits existing ones.
- Set `assigned_to` before working a row so you don't double-pitch.
- See `contact-form-templates.md` for the message library and
  `contact-form-prompt.md` for the end-to-end workflow.
- To pause the daily cron, disable the workflow from the Actions tab; the
  manual dispatch button still works.
