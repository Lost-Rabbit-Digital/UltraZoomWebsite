# Apollo CSV inbox

Drop folder for raw Apollo people-export CSVs. Each campaign has its
own subdirectory; the pipeline picks up the newest `*.csv` in the
campaign's folder by default.

## Layout

```
inbox/
  ultrazoom-realtors/    Drop UZ Realtors batches here
  ultrazoom-press/       Drop UZ Press batches here
```

## Drop pattern

1. Run the campaign's saved Apollo people-search (filters documented in
   the campaign brief under `outreach/campaigns/`)
2. Export the result as **CSV → All columns**. Apollo emails the file
   when ready.
3. Save the file in the campaign's folder using `<YYYY-MM-DD>.csv` as
   the filename. Multiple files in the same folder are fine — the
   runner uses the newest by mtime unless you pass `--inbox-csv`.
4. Commit the file to the active branch and push. The
   `outreach-ultrazoom` GitHub Action triggers on push to
   `outreach/inbox/**` and produces the per-touch Sheet rows.

## What lives here

Only Apollo CSV exports. Nothing else — no notes, no hand-edited
prospect lists, no scratch files. The runner globs `*.csv` and any
other content gets ignored, but keeping the folder clean makes the
audit trail obvious.

## What does NOT live here

- Lead suppression / unsubscribe data — that's `outreach/suppression.csv`
- Per-row manual research like `specific_recent_topic` for the press
  campaign — that's added by Boden directly in the Sheet after the
  pipeline runs, not as a CSV pre-process step
- Generated email drafts — those go to the campaign's Google Sheet via
  the `outreach-ultrazoom` workflow
