"""Single-file Flask review UI for triaging candidate comment opportunities.

Run:
    python review_ui.py                          # open ./candidates.db
    python review_ui.py --db ~/Downloads/candidates.db
    python review_ui.py --port 5050 --host 0.0.0.0

Then open the printed URL.

Workflow:
  - Tabs filter by status; default view is `new` sorted by relevance score.
  - Each card shows the article preview, header image, suggested comment
    from Claude (editable), model + cost, and zoom-signal categories.
  - Action buttons: Save edits (moves to reviewed), Mark posted, Archive,
    Skip.
  - Search box filters by domain, title, or excerpt.
  - Keyboard shortcuts (press `?` for the cheat sheet):
      j / k    next / previous card
      enter    open article in new tab
      p        mark posted
      a        archive
      s        skip
      e        focus the draft textarea
      /        focus the search box
"""
from __future__ import annotations

import argparse
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask, flash, get_flashed_messages, jsonify, redirect,
    render_template_string, request, url_for,
)

import db as db_module

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


def connect():
    """Open a connection to the configured DB path, with row factory."""
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def wants_json() -> bool:
    return (
        request.headers.get("X-Requested-With") == "fetch"
        or "application/json" in (request.headers.get("Accept") or "")
    )


STATUSES = ["new", "reviewed", "posted", "archived", "skipped"]

SORTS = {
    "relevance": "COALESCE(relevance_score,0) DESC, fetched_at DESC",
    "recent":    "fetched_at DESC",
    "oldest":    "fetched_at ASC",
    "domain":    "site_title ASC, COALESCE(relevance_score,0) DESC",
}

SORT_LABELS = [
    ("relevance", "Score ↓"),
    ("recent",    "Recent ↓"),
    ("oldest",    "Recent ↑"),
    ("domain",    "Domain"),
]

SCORE_OPTIONS = [
    ("",    "Any score"),
    ("0.5", "≥ 0.50"),
    ("0.7", "≥ 0.70"),
    ("0.9", "≥ 0.90"),
]

TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ultra Zoom // outreach review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Stardos+Stencil:wght@400;700&family=Saira+Condensed:wght@500;600;700&family=Share+Tech+Mono&display=swap" rel="stylesheet">
<style>
  :root {
    /* MILINT / SCIF palette: deep olive-black, khaki, OD green, oxblood */
    --bg: #10130c;            /* near-black with olive cast */
    --panel: #181c12;
    --panel-2: #1f2417;
    --ink: #d8dac1;            /* parchment / sand */
    --ink-dim: #8a9070;
    --ink-faint: #5b6044;
    --accent: #c3b27a;          /* khaki / brass */
    --accent-2: #7a8b3a;        /* olive drab */
    --accent-3: #4b5320;        /* deep OD green */
    --danger: #8b3a3a;          /* oxblood */
    --classified: #a83232;      /* classification red */
    --rule: #2a2f1f;
    --rule-strong: #3a4128;
    --shadow: 0 1px 0 rgba(195,178,122,0.04), 0 4px 14px rgba(0,0,0,0.55);
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; padding: 0;
    font-family: "Share Tech Mono", "JetBrains Mono", ui-monospace, monospace;
    background: var(--bg);
    color: var(--ink);
    font-size: 13px;
    line-height: 1.5;
    /* faint diagonal stencil grid */
    background-image:
      repeating-linear-gradient(0deg, rgba(195,178,122,0.015) 0 1px, transparent 1px 60px),
      repeating-linear-gradient(90deg, rgba(195,178,122,0.015) 0 1px, transparent 1px 60px);
  }
  a { color: var(--accent); }
  a:hover { color: var(--ink); }

  header {
    border-bottom: 1px solid var(--rule-strong);
    padding: 14px 28px 0 28px;
    background:
      linear-gradient(180deg, #1a1f12 0%, var(--bg) 100%);
    position: sticky; top: 0; z-index: 10;
  }
  header::before {
    /* classified-bar: thin top stripe in oxblood */
    content: "";
    display: block;
    height: 3px;
    margin: -14px -28px 12px -28px;
    background: repeating-linear-gradient(
      90deg,
      var(--classified) 0 18px,
      #2a0e0e 18px 22px
    );
  }
  .header-row {
    display: flex; align-items: baseline; gap: 24px; flex-wrap: wrap;
  }
  h1 {
    margin: 0;
    font-family: "Stardos Stencil", "Saira Condensed", Impact, sans-serif;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    white-space: nowrap;
    color: var(--ink);
  }
  h1 .accent {
    color: var(--accent);
    font-family: "Saira Condensed", Impact, sans-serif;
    font-weight: 600;
    font-size: 18px;
    letter-spacing: 0.12em;
  }
  .stats {
    margin-left: auto;
    color: var(--ink-dim);
    font-size: 11px;
    text-align: right;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .stats .db-path {
    color: var(--ink-faint);
    font-size: 10px;
    margin-top: 3px;
    word-break: break-all;
    text-transform: none;
    letter-spacing: 0;
  }

  nav {
    display: flex; gap: 0; flex-wrap: wrap;
    margin-top: 14px;
    border-bottom: 1px solid var(--rule-strong);
    margin-bottom: -1px;
  }
  nav a {
    color: var(--ink-dim);
    text-decoration: none;
    padding: 9px 16px;
    border: 1px solid transparent;
    border-bottom: none;
    font-family: "Saira Condensed", Impact, sans-serif;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 12px;
    letter-spacing: 0.14em;
    display: flex; align-items: baseline; gap: 8px;
    position: relative;
  }
  nav a .count {
    color: var(--ink-faint);
    font-size: 11px;
    font-family: "Share Tech Mono", monospace;
    letter-spacing: 0;
  }
  nav a.active {
    color: var(--accent);
    border-color: var(--rule-strong);
    background: var(--panel);
  }
  nav a.active::after {
    content: "";
    position: absolute;
    inset: -1px 0 auto 0;
    height: 2px;
    background: var(--accent);
  }
  nav a.active .count { color: var(--accent); }
  nav a:hover { color: var(--ink); }

  .toolbar {
    display: flex; gap: 12px; align-items: center;
    padding: 12px 28px;
    background: var(--panel);
    border-bottom: 1px solid var(--rule-strong);
  }
  .toolbar input[type=search] {
    flex: 1; max-width: 520px;
    background: var(--bg);
    border: 1px solid var(--rule-strong);
    color: var(--ink);
    font-family: inherit;
    font-size: 13px;
    padding: 7px 12px;
    letter-spacing: 0.04em;
  }
  .toolbar input[type=search]::placeholder { color: var(--ink-faint); }
  .toolbar input[type=search]:focus {
    outline: none; border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .toolbar .help {
    color: var(--ink-faint);
    font-family: "Saira Condensed", sans-serif;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-left: auto;
    cursor: help;
  }
  .toolbar .help:hover { color: var(--accent); }

  select.select {
    background: var(--bg);
    border: 1px solid var(--rule-strong);
    color: var(--ink);
    font-family: "Saira Condensed", sans-serif;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 7px 10px;
    cursor: pointer;
    appearance: none;
    -webkit-appearance: none;
    background-image: linear-gradient(45deg, transparent 50%, var(--ink-dim) 50%),
                      linear-gradient(135deg, var(--ink-dim) 50%, transparent 50%);
    background-position: calc(100% - 14px) 50%, calc(100% - 9px) 50%;
    background-size: 5px 5px, 5px 5px;
    background-repeat: no-repeat;
    padding-right: 26px;
  }
  select.select:focus {
    outline: none; border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }

  .chips-row {
    display: flex; flex-wrap: wrap; gap: 6px;
    align-items: center;
    padding: 10px 28px;
    border-bottom: 1px solid var(--rule-strong);
    background: var(--bg);
  }
  .chip-label {
    color: var(--ink-faint);
    font-family: "Saira Condensed", sans-serif;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-right: 2px;
  }
  .chip-label + .chip { margin-right: 0; }
  .chip-label:not(:first-child) { margin-left: 14px; }
  .chip {
    display: inline-flex; gap: 6px; align-items: baseline;
    color: var(--ink-dim);
    background: transparent;
    border: 1px solid var(--rule-strong);
    padding: 3px 9px;
    font-family: "Saira Condensed", sans-serif;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    text-decoration: none;
    cursor: pointer;
    transition: border-color 80ms ease, color 80ms ease, background 80ms ease;
  }
  .chip:hover { color: var(--ink); border-color: var(--ink-dim); }
  .chip.active {
    color: var(--bg);
    background: var(--accent);
    border-color: var(--accent);
  }
  .chip-n {
    font-family: "Share Tech Mono", monospace;
    letter-spacing: 0;
    color: inherit;
    opacity: 0.7;
    font-size: 10px;
  }

  .flash .undo {
    margin-left: 10px;
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 2px 8px;
    font-family: "Saira Condensed", sans-serif;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.16em;
    cursor: pointer;
  }
  .flash .undo:hover { background: var(--accent); color: var(--bg); }
  .flash.danger .undo { border-color: var(--ink); color: var(--ink); }
  .flash.danger .undo:hover { background: var(--ink); color: var(--bg); }
  .flash.is-pinned { animation: none; opacity: 1; }

  .card.leaving {
    opacity: 0;
    transform: translateY(-6px);
    transition: opacity 200ms ease, transform 200ms ease;
    pointer-events: none;
  }
  .card.flashed {
    border-color: var(--accent-2) !important;
    box-shadow: 0 0 0 1px var(--accent-2), var(--shadow);
    transition: border-color 600ms ease, box-shadow 600ms ease;
  }

  .flash-stack {
    position: fixed; top: 12px; right: 16px; z-index: 50;
    display: flex; flex-direction: column; gap: 6px;
    max-width: 380px;
  }
  @keyframes fade-out {
    0%, 70% { opacity: 1; transform: translateX(0); }
    100% { opacity: 0; transform: translateX(8px); }
  }

  main { padding: 24px 28px 80px 28px; max-width: 1800px; margin: 0 auto; }

  .cards-grid {
    display: grid;
    gap: 18px;
    grid-template-columns: repeat(auto-fill, minmax(560px, 1fr));
  }

  .card {
    background: var(--panel);
    border: 1px solid var(--rule-strong);
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: 0;
    box-shadow: var(--shadow);
    scroll-margin-top: 160px;
    position: relative;
  }
  .card::before {
    /* faint corner crosshair tick — top-left */
    content: "";
    position: absolute;
    top: -1px; left: -1px;
    width: 10px; height: 10px;
    border-top: 1px solid var(--accent);
    border-left: 1px solid var(--accent);
    opacity: 0.35;
    pointer-events: none;
  }
  .card::after {
    content: "";
    position: absolute;
    bottom: -1px; right: -1px;
    width: 10px; height: 10px;
    border-bottom: 1px solid var(--accent);
    border-right: 1px solid var(--accent);
    opacity: 0.35;
    pointer-events: none;
  }
  .card.is-active {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent), var(--shadow);
  }
  .card.is-active::before, .card.is-active::after { opacity: 1; }
  @media (max-width: 820px) {
    .card { grid-template-columns: 1fr; }
    .thumb { min-height: 160px; border-right: none; border-bottom: 1px solid var(--rule-strong); }
  }

  .thumb {
    background: var(--panel-2) center/cover no-repeat;
    border-right: 1px solid var(--rule-strong);
    min-height: 200px;
    position: relative;
  }
  .thumb.no-image {
    display: flex; align-items: center; justify-content: center;
    color: var(--ink-faint);
    font-family: "Saira Condensed", sans-serif;
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }
  .thumb .badge {
    position: absolute;
    background: rgba(8,10,5,0.85);
    backdrop-filter: blur(2px);
    padding: 4px 8px;
    font-family: "Saira Condensed", sans-serif;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .thumb .score {
    top: 8px; left: 8px;
    color: var(--accent);
    border: 1px solid var(--accent);
    font-family: "Share Tech Mono", monospace;
    font-size: 12px;
    letter-spacing: 0;
  }
  .thumb .system {
    bottom: 8px; left: 8px;
    color: var(--ink-dim);
    border: 1px solid var(--rule-strong);
  }
  .thumb .status-pill {
    top: 8px; right: 8px;
    color: var(--ink-dim);
    border: 1px solid var(--rule-strong);
  }
  .thumb .status-pill.posted { color: var(--accent-2); border-color: var(--accent-2); }
  .thumb .status-pill.archived { color: var(--ink-faint); }
  .thumb .status-pill.skipped { color: var(--danger); border-color: var(--danger); }
  .thumb .status-pill.reviewed { color: var(--accent); border-color: var(--accent); }

  .body { padding: 16px 20px; min-width: 0; }

  .title {
    font-family: "Saira Condensed", Impact, sans-serif;
    font-size: 19px;
    font-weight: 700;
    margin: 0 0 6px 0;
    color: var(--ink);
    line-height: 1.25;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .title a { color: inherit; text-decoration: none; }
  .title a:hover { color: var(--accent); }
  .meta {
    color: var(--ink-dim);
    font-size: 11px;
    margin-bottom: 10px;
    display: flex; gap: 12px; flex-wrap: wrap;
    letter-spacing: 0.04em;
  }
  .meta .signal {
    color: var(--accent-2);
    background: rgba(122,139,58,0.1);
    border: 1px solid var(--accent-3);
    padding: 1px 6px;
    font-family: "Saira Condensed", sans-serif;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }
  .meta .domain {
    color: var(--accent);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .caption {
    font-style: italic;
    color: var(--ink-dim);
    border-left: 2px solid var(--accent-3);
    padding: 4px 10px;
    margin: 8px 0;
    font-size: 12px;
  }
  .excerpt {
    color: var(--ink-dim);
    margin: 8px 0 12px 0;
    font-size: 12px;
    max-height: 4.8em;
    overflow: hidden;
    position: relative;
  }
  .excerpt::after {
    content: "";
    position: absolute;
    inset: auto 0 0 0;
    height: 1.6em;
    background: linear-gradient(180deg, rgba(24,28,18,0) 0%, var(--panel) 100%);
    pointer-events: none;
  }

  .draft-wrap {
    position: relative;
    background: var(--panel-2);
    border: 1px solid var(--rule-strong);
    margin: 18px 0 8px 0;
  }
  .draft-wrap.skip { opacity: 0.7; }
  .draft-label {
    position: absolute;
    top: -9px; left: 12px;
    background: var(--bg);
    color: var(--accent);
    font-family: "Saira Condensed", sans-serif;
    font-weight: 700;
    font-size: 10px;
    padding: 0 8px;
    letter-spacing: 0.22em;
    border: 1px solid var(--accent);
    border-radius: 0;
  }
  .draft-wrap.skip .draft-label {
    color: var(--danger);
    border-color: var(--danger);
  }
  textarea {
    width: 100%;
    background: transparent;
    border: 0;
    color: var(--ink);
    font-family: "Share Tech Mono", "JetBrains Mono", monospace;
    font-size: 13px;
    line-height: 1.6;
    padding: 14px 14px 10px 14px;
    min-height: 80px;
    resize: vertical;
    display: block;
  }
  textarea:focus { outline: none; }
  .draft-wrap:focus-within { border-color: var(--accent); }
  .draft-foot {
    display: flex; gap: 12px; align-items: center;
    padding: 6px 14px;
    border-top: 1px solid var(--rule-strong);
    color: var(--ink-faint);
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .draft-foot .right { margin-left: auto; }
  .copy-btn {
    background: transparent;
    color: var(--ink-faint);
    border: 1px solid var(--rule-strong);
    padding: 2px 8px;
    font-size: 10px;
    font-family: "Saira Condensed", sans-serif;
    font-weight: 600;
    letter-spacing: 0.16em;
    cursor: pointer;
  }
  .copy-btn:hover { color: var(--accent); border-color: var(--accent); }
  .skip-note {
    padding: 14px;
    color: var(--ink-dim);
    font-style: italic;
    font-size: 12px;
  }

  .actions {
    display: flex; gap: 8px; flex-wrap: wrap;
    margin-top: 14px;
    align-items: center;
  }
  .actions form { display: contents; }
  button, .btn {
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--rule-strong);
    padding: 7px 14px;
    font-family: "Saira Condensed", Impact, sans-serif;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
    transition: border-color 80ms ease, color 80ms ease, background 80ms ease;
  }
  button:hover, .btn:hover { border-color: var(--ink); color: var(--ink); }
  button:focus-visible, .btn:focus-visible {
    outline: 1px solid var(--accent); outline-offset: 1px;
  }
  button.primary { color: var(--accent); border-color: var(--accent); }
  button.primary:hover { background: var(--accent); color: var(--bg); }
  button.danger { color: var(--danger); border-color: var(--danger); }
  button.danger:hover { background: var(--danger); color: var(--ink); }
  .ext {
    color: var(--ink-dim);
    margin-left: auto;
    font-family: "Saira Condensed", sans-serif;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    text-decoration: none;
  }
  .ext:hover { color: var(--accent); }

  .empty {
    text-align: center;
    color: var(--ink-dim);
    padding: 80px 20px;
    font-family: "Saira Condensed", sans-serif;
    font-size: 14px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    grid-column: 1 / -1;
  }
  .empty em { font-style: normal; color: var(--accent); }
  .empty code {
    font-family: "Share Tech Mono", monospace;
    background: var(--panel);
    border: 1px solid var(--rule-strong);
    padding: 2px 6px;
    color: var(--accent);
    text-transform: none;
    letter-spacing: 0;
  }

  /* Help dialog */
  dialog#shortcuts {
    background: var(--panel);
    color: var(--ink);
    border: 1px solid var(--accent);
    padding: 20px 24px;
    box-shadow: var(--shadow);
    font-family: inherit;
    font-size: 13px;
    max-width: 380px;
  }
  dialog#shortcuts::backdrop { background: rgba(0,0,0,0.7); }
  dialog#shortcuts h2 {
    margin: 0 0 14px 0;
    font-family: "Stardos Stencil", Impact, sans-serif;
    font-size: 16px;
    color: var(--accent);
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }
  dialog#shortcuts table { border-collapse: collapse; width: 100%; }
  dialog#shortcuts td { padding: 4px 8px; }
  dialog#shortcuts td:first-child {
    color: var(--accent);
    font-weight: 700;
    width: 80px;
    text-align: right;
    font-family: "Share Tech Mono", monospace;
  }
  dialog#shortcuts .close { margin-top: 14px; }

  .flash {
    background: var(--panel-2);
    border: 1px solid var(--accent);
    color: var(--ink);
    padding: 10px 14px;
    box-shadow: var(--shadow);
    font-family: "Saira Condensed", sans-serif;
    font-size: 13px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    animation: fade-out 4s forwards;
  }
  .flash.danger { border-color: var(--danger); }
</style>
</head>
<body>
<header>
  <div class="header-row">
    <h1>Ultra Zoom <span class="accent">// outreach review</span></h1>
    <div class="stats">
      <div>
        <span data-stat="new">{{ counts.new }}</span> new ·
        <span data-stat="reviewed">{{ counts.reviewed }}</span> reviewed ·
        <span data-stat="posted">{{ counts.posted }}</span> posted ·
        <span data-stat="archived">{{ counts.archived }}</span> archived ·
        <span data-stat="skipped">{{ counts.skipped }}</span> skipped
      </div>
      <div>${{ '%.4f'|format(counts.cost or 0) }} spent on Claude</div>
      <div class="db-path">{{ db_path }}</div>
    </div>
  </div>
  <nav>
    {% for s in tabs %}
      <a href="{{ url_for('index', status=s, q=filters.q or none, sort=filters.sort if filters.sort != 'relevance' else none, score_min=filters.score_min or none, signal=filters.signal or none, domain=filters.domain or none) }}"
         data-status="{{ s }}"
         class="{{ 'active' if status==s else '' }}">
        {{ s }}<span class="count">{{ counts[s] if s != 'all' else counts.total }}</span>
      </a>
    {% endfor %}
  </nav>
</header>

<form class="toolbar" method="get" action="{{ url_for('index') }}" id="filter-form">
  <input type="hidden" name="status" value="{{ status }}">
  {% if filters.signal %}<input type="hidden" name="signal" value="{{ filters.signal }}">{% endif %}
  {% if filters.domain %}<input type="hidden" name="domain" value="{{ filters.domain }}">{% endif %}
  <input type="search" name="q" id="search" value="{{ query or '' }}"
         placeholder="Search title, domain, excerpt…" autocomplete="off">
  <select class="select" name="sort" aria-label="Sort">
    {% for v, label in sort_options %}
      <option value="{{ v }}" {{ 'selected' if v == filters.sort else '' }}>{{ label }}</option>
    {% endfor %}
  </select>
  <select class="select" name="score_min" aria-label="Minimum score">
    {% for v, label in score_options %}
      <option value="{{ v }}" {{ 'selected' if v == filters.score_min else '' }}>{{ label }}</option>
    {% endfor %}
  </select>
  <noscript><button type="submit">Apply</button></noscript>
  {% if has_filters %}
    <a href="{{ url_for('index', status=status) }}" class="btn">Clear</a>
  {% endif %}
  <span class="help" onclick="document.getElementById('shortcuts').showModal()" tabindex="0">? shortcuts</span>
</form>

{% if domain_chips or signal_chips %}
<div class="chips-row">
  {% if signal_chips %}
    <span class="chip-label">Signal</span>
    {% for c in signal_chips %}
      {% set active = (filters.signal == c.label) %}
      <a class="chip{{ ' active' if active }}"
         href="{{ url_for('index', status=status, q=filters.q or none, sort=filters.sort if filters.sort != 'relevance' else none, score_min=filters.score_min or none, domain=filters.domain or none, signal=(none if active else c.label)) }}">
        {{ c.label }}<span class="chip-n">{{ c.n }}</span>
      </a>
    {% endfor %}
  {% endif %}
  {% if domain_chips %}
    <span class="chip-label">Source</span>
    {% for c in domain_chips %}
      {% set active = (filters.domain == c.label) %}
      <a class="chip{{ ' active' if active }}"
         href="{{ url_for('index', status=status, q=filters.q or none, sort=filters.sort if filters.sort != 'relevance' else none, score_min=filters.score_min or none, signal=filters.signal or none, domain=(none if active else c.label)) }}">
        {{ c.label or '—' }}<span class="chip-n">{{ c.n }}</span>
      </a>
    {% endfor %}
  {% endif %}
</div>
{% endif %}

{% set msgs = get_flashed_messages(with_categories=true) %}
{% if msgs %}
  <div class="flash-stack">
    {% for cat, msg in msgs %}
      <div class="flash {{ cat }}">{{ msg }}</div>
    {% endfor %}
  </div>
{% endif %}

<main>
<div class="cards-grid">
{% if not rows %}
  <div class="empty">
    {% if query %}
      No matches for <em>"{{ query }}"</em> in <em>{{ status }}</em>.
    {% elif status == 'new' %}
      No new candidates. Run <code>python pipeline.py --verbose</code> to discover more,
      or download a <code>candidates-db-*</code> artifact from the
      <em>Comments discovery</em> workflow and reopen with
      <code>python review_ui.py --db /path/to/candidates.db</code>.
    {% else %}
      Nothing in <em>{{ status }}</em>.
    {% endif %}
  </div>
{% endif %}

{% for r in rows %}
  <article class="card" data-id="{{ r.id }}" data-url="{{ r.url }}" tabindex="-1">
    <div class="thumb {% if not r.header_image_url %}no-image{% endif %}"
         {% if r.header_image_url %}style="background-image: url('{{ r.header_image_url }}')"{% endif %}>
      {% if not r.header_image_url %}<span>no image</span>{% endif %}
      <span class="badge score">{{ '%.2f'|format(r.relevance_score or 0) }}</span>
      {% if r.comment_system %}
        <span class="badge system">{{ r.comment_system }}{% if r.comment_count %} · {{ r.comment_count }}{% endif %}</span>
      {% endif %}
      {% if status == 'all' and r.status %}
        <span class="badge status-pill {{ r.status }}">{{ r.status }}</span>
      {% endif %}
    </div>
    <div class="body">
      <h2 class="title">
        <a href="{{ r.url }}" target="_blank" rel="noopener">{{ r.article_title or r.url }}</a>
      </h2>
      <div class="meta">
        <span class="domain">{{ r.site_title }}</span>
        {% if r.published_at %}<span>{{ r.published_at[:10] }}</span>{% endif %}
        {% if r.word_count %}<span>{{ r.word_count }} words</span>{% endif %}
        {% if r.image_count %}<span>{{ r.image_count }} imgs</span>{% endif %}
        {% if r.zoom_signal %}<span class="signal">{{ r.zoom_signal }}</span>{% endif %}
      </div>

      {% if r.header_image_caption %}
        <div class="caption">{{ r.header_image_caption }}</div>
      {% endif %}
      {% if r.excerpt %}
        <div class="excerpt">{{ r.excerpt }}</div>
      {% endif %}

      {% if r.suggested_comment %}
        <form method="post" action="{{ url_for('update', cid=r.id) }}">
          <div class="draft-wrap">
            <span class="draft-label">DRAFT</span>
            <textarea name="suggested_comment" rows="3">{{ r.suggested_comment }}</textarea>
            <div class="draft-foot">
              <span>{{ r.suggestion_model or '—' }}</span>
              {% if r.suggestion_cost_usd is not none %}
                <span>${{ '%.5f'|format(r.suggestion_cost_usd) }}</span>
              {% endif %}
              <button type="button" class="copy-btn right"
                onclick="navigator.clipboard.writeText(this.closest('.draft-wrap').querySelector('textarea').value); this.textContent='COPIED'; setTimeout(()=>this.textContent='COPY',1200);">COPY</button>
            </div>
          </div>
          <div class="actions">
            <button type="submit" name="action" value="save">Save edits</button>
            <button type="submit" name="action" value="posted" class="primary" data-shortcut="p">Mark posted</button>
            <button type="submit" name="action" value="archived" data-shortcut="a">Archive</button>
            <button type="submit" name="action" value="skipped" class="danger" data-shortcut="s">Skip</button>
            <a class="ext" href="{{ r.url }}" target="_blank" rel="noopener">open ↗</a>
          </div>
        </form>
      {% else %}
        <div class="draft-wrap skip">
          <span class="draft-label">AI SAID SKIP</span>
          <div class="skip-note">No comment drafted — Claude judged this article isn't a fit for a zoom-and-enhance contribution.</div>
        </div>
        <form method="post" action="{{ url_for('update', cid=r.id) }}">
          <div class="actions">
            <button type="submit" name="action" value="archived" data-shortcut="a">Archive</button>
            <a class="ext" href="{{ r.url }}" target="_blank" rel="noopener">open ↗</a>
          </div>
        </form>
      {% endif %}
    </div>
  </article>
{% endfor %}
</div>
</main>

<dialog id="shortcuts">
  <h2>Keyboard shortcuts</h2>
  <table>
    <tr><td>j / ↓</td><td>next card</td></tr>
    <tr><td>k / ↑</td><td>previous card</td></tr>
    <tr><td>enter</td><td>open article</td></tr>
    <tr><td>e</td><td>edit draft</td></tr>
    <tr><td>p</td><td>mark posted</td></tr>
    <tr><td>a</td><td>archive</td></tr>
    <tr><td>s</td><td>skip</td></tr>
    <tr><td>u</td><td>undo last</td></tr>
    <tr><td>/</td><td>focus search</td></tr>
    <tr><td>?</td><td>this dialog</td></tr>
    <tr><td>esc</td><td>blur / close</td></tr>
  </table>
  <form method="dialog" class="close"><button>close</button></form>
</dialog>

<script>
(() => {
  const currentStatus = {{ status|tojson }};
  let cards = Array.from(document.querySelectorAll('.card'));
  let active = -1;

  // ---------- card focus / keyboard nav ----------
  function refreshCards() {
    cards = Array.from(document.querySelectorAll('.card'));
    if (active >= cards.length) active = cards.length - 1;
    if (active < 0 && cards.length > 0) setActive(0, false);
  }

  function setActive(i, scroll = true) {
    if (i < 0 || i >= cards.length) return;
    cards.forEach(c => c.classList.remove('is-active'));
    cards[i].classList.add('is-active');
    if (scroll) cards[i].scrollIntoView({ block: 'center', behavior: 'smooth' });
    active = i;
  }

  function clickShortcut(card, key) {
    const btn = card.querySelector(`button[data-shortcut="${key}"]`);
    if (btn) btn.click();
  }

  // ---------- toast / undo ----------
  function ensureFlashStack() {
    let stack = document.querySelector('.flash-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'flash-stack';
      document.body.appendChild(stack);
    }
    return stack;
  }

  function showToast(msg, cat, undoData) {
    const stack = ensureFlashStack();
    const flash = document.createElement('div');
    flash.className = 'flash' + (cat === 'danger' ? ' danger' : '');
    const text = document.createElement('span');
    text.textContent = msg;
    flash.appendChild(text);

    if (undoData) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'undo';
      btn.textContent = 'UNDO';
      btn.addEventListener('click', () => {
        btn.disabled = true;
        doUndo(undoData);
      });
      flash.appendChild(btn);
      flash.classList.add('is-pinned');
      // pin for 6s, then start fade
      setTimeout(() => {
        flash.classList.remove('is-pinned');
      }, 6000);
      setTimeout(() => flash.remove(), 10000);
    } else {
      setTimeout(() => flash.remove(), 4000);
    }
    return flash;
  }

  // ---------- count updates ----------
  function adjustCount(status, delta) {
    const navCount = document.querySelector(`nav a[data-status="${status}"] .count`);
    if (navCount) {
      navCount.textContent = Math.max(0, parseInt(navCount.textContent || '0', 10) + delta);
    }
    const stat = document.querySelector(`[data-stat="${status}"]`);
    if (stat) {
      stat.textContent = Math.max(0, parseInt(stat.textContent || '0', 10) + delta);
    }
  }

  function moveBetween(prevStatus, newStatus) {
    if (prevStatus === newStatus) return;
    adjustCount(prevStatus, -1);
    adjustCount(newStatus, +1);
  }

  // ---------- AJAX action submit ----------
  async function submitAction(form) {
    const fd = new FormData(form);
    const action = fd.get('action') || 'save';
    const card = form.closest('.card');
    if (!card) return;

    // Disable buttons during the request to prevent double-fires.
    const buttons = form.querySelectorAll('button[type="submit"]');
    buttons.forEach(b => b.disabled = true);

    let data;
    try {
      const r = await fetch(form.action, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
      });
      if (!r.ok) throw new Error('http ' + r.status);
      data = await r.json();
    } catch (e) {
      buttons.forEach(b => b.disabled = false);
      showToast('Action failed — check the server logs.', 'danger');
      return;
    }

    moveBetween(data.prev_status, data.status);

    const stillInView = (currentStatus === 'all') || (data.status === currentStatus);
    if (stillInView) {
      // 'save' on the current tab — flash highlight, leave card in place.
      buttons.forEach(b => b.disabled = false);
      card.classList.add('flashed');
      setTimeout(() => card.classList.remove('flashed'), 800);
    } else {
      const wasActive = card.classList.contains('is-active');
      card.classList.add('leaving');
      setTimeout(() => {
        const idx = cards.indexOf(card);
        card.remove();
        refreshCards();
        if (wasActive && cards.length > 0) {
          setActive(Math.min(idx, cards.length - 1), false);
        }
        if (cards.length === 0) {
          // server-rendered empty state isn't there — drop in a stand-in.
          const grid = document.querySelector('.cards-grid');
          if (grid && !grid.querySelector('.empty')) {
            const empty = document.createElement('div');
            empty.className = 'empty';
            empty.textContent = 'Queue clear. Reload to fetch more.';
            grid.appendChild(empty);
          }
        }
      }, 200);
    }

    showToast(data.msg, data.cat, {
      cid: data.cid,
      prev_status: data.prev_status,
      prev_text: data.prev_text,
      prev_reviewed_at: data.prev_reviewed_at,
      prev_posted_at: data.prev_posted_at,
    });
  }

  async function doUndo(d) {
    const fd = new FormData();
    fd.append('prev_status', d.prev_status || 'new');
    if (d.prev_text != null) fd.append('prev_text', d.prev_text);
    if (d.prev_reviewed_at) fd.append('prev_reviewed_at', d.prev_reviewed_at);
    if (d.prev_posted_at) fd.append('prev_posted_at', d.prev_posted_at);
    try {
      const r = await fetch(`/c/${d.cid}/undo`, {
        method: 'POST',
        body: fd,
        headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
      });
      if (!r.ok) throw new Error('http ' + r.status);
    } catch (e) {
      showToast('Undo failed.', 'danger');
      return;
    }
    // Reload so the restored card reappears in the right tab and counts re-sync.
    window.location.reload();
  }

  // Hook every card form for AJAX submit.
  document.querySelectorAll('.card form[action^="/c/"]').forEach(form => {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      submitAction(form);
    });
  });

  // ---------- live search + auto-submit selects ----------
  const filterForm = document.getElementById('filter-form');
  const searchInput = document.getElementById('search');
  if (filterForm) {
    filterForm.querySelectorAll('select.select').forEach(sel => {
      sel.addEventListener('change', () => filterForm.submit());
    });
  }
  if (searchInput && filterForm) {
    let t;
    searchInput.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => filterForm.submit(), 300);
    });
    // Resume typing flow after the page reloads on a live-search submit.
    if (searchInput.value) {
      searchInput.focus();
      const len = searchInput.value.length;
      try { searchInput.setSelectionRange(len, len); } catch (_) {}
    }
  }

  // ---------- keyboard shortcuts ----------
  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    const inField = tag === 'input' || tag === 'textarea' || tag === 'select';
    if (e.key === 'Escape') {
      if (e.target.blur) e.target.blur();
      const d = document.getElementById('shortcuts');
      if (d.open) d.close();
      return;
    }
    if (inField) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
      e.preventDefault();
      document.getElementById('shortcuts').showModal();
      return;
    }
    if (e.key === '/') {
      e.preventDefault();
      searchInput && searchInput.focus();
      return;
    }
    if (e.key === 'j' || e.key === 'ArrowDown') {
      e.preventDefault();
      setActive(Math.min(active + 1, cards.length - 1));
      return;
    }
    if (e.key === 'k' || e.key === 'ArrowUp') {
      e.preventDefault();
      setActive(Math.max(active - 1, 0));
      return;
    }
    if (active < 0) return;
    const card = cards[active];
    if (e.key === 'Enter') {
      e.preventDefault();
      window.open(card.dataset.url, '_blank', 'noopener');
    } else if (e.key === 'e') {
      e.preventDefault();
      const ta = card.querySelector('textarea');
      if (ta) ta.focus();
    } else if (['p', 'a', 's'].includes(e.key)) {
      e.preventDefault();
      clickShortcut(card, e.key);
    } else if (e.key === 'u') {
      // Undo the most recent action's toast, if it has an undo button.
      e.preventDefault();
      const btn = document.querySelector('.flash .undo:not([disabled])');
      if (btn) btn.click();
    }
  });

  if (cards.length > 0) setActive(0, false);
})();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    status = request.args.get("status", "new")
    query = (request.args.get("q") or "").strip()
    if status not in STATUSES + ["all"]:
        status = "new"

    sort = request.args.get("sort", "relevance")
    if sort not in SORTS:
        sort = "relevance"

    signal_f = (request.args.get("signal") or "").strip()
    domain_f = (request.args.get("domain") or "").strip()
    score_min_raw = (request.args.get("score_min") or "").strip()
    score_min: float | None = None
    if score_min_raw:
        try:
            score_min = float(score_min_raw)
        except ValueError:
            score_min_raw = ""

    where_clauses: list[str] = []
    params: list = []
    if status != "all":
        where_clauses.append("status = ?")
        params.append(status)
    if query:
        where_clauses.append(
            "(LOWER(COALESCE(article_title,'')) LIKE ? "
            " OR LOWER(COALESCE(site_title,'')) LIKE ? "
            " OR LOWER(COALESCE(url,'')) LIKE ? "
            " OR LOWER(COALESCE(excerpt,'')) LIKE ?)"
        )
        like = f"%{query.lower()}%"
        params.extend([like, like, like, like])
    if signal_f:
        where_clauses.append("zoom_signal = ?")
        params.append(signal_f)
    if domain_f:
        where_clauses.append("site_title = ?")
        params.append(domain_f)
    if score_min is not None:
        where_clauses.append("COALESCE(relevance_score, 0) >= ?")
        params.append(score_min)

    sql = "SELECT * FROM candidates"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY " + SORTS[sort]

    # Chip aggregates respect status only, so toggling a chip never hides itself.
    chip_clauses: list[str] = []
    chip_params: list = []
    if status != "all":
        chip_clauses.append("status = ?")
        chip_params.append(status)

    domain_where = (" WHERE " + " AND ".join(chip_clauses)) if chip_clauses else ""
    signal_where_clauses = chip_clauses + ["zoom_signal IS NOT NULL", "zoom_signal != ''"]
    signal_where = " WHERE " + " AND ".join(signal_where_clauses)

    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        counts = {s: conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE status=?", (s,)
        ).fetchone()[0] for s in STATUSES}
        counts["total"] = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        counts["cost"] = conn.execute(
            "SELECT COALESCE(SUM(suggestion_cost_usd),0) FROM candidates"
        ).fetchone()[0]
        domain_chips = conn.execute(
            "SELECT site_title AS label, COUNT(*) AS n FROM candidates"
            f"{domain_where}"
            " GROUP BY site_title ORDER BY n DESC, site_title ASC LIMIT 12",
            chip_params,
        ).fetchall()
        signal_chips = conn.execute(
            "SELECT zoom_signal AS label, COUNT(*) AS n FROM candidates"
            f"{signal_where}"
            " GROUP BY zoom_signal ORDER BY n DESC, zoom_signal ASC LIMIT 8",
            chip_params,
        ).fetchall()
    finally:
        conn.close()

    filters = {
        "q": query,
        "sort": sort,
        "signal": signal_f,
        "domain": domain_f,
        "score_min": score_min_raw,
    }
    has_filters = bool(query or signal_f or domain_f or score_min is not None or sort != "relevance")

    return render_template_string(
        TEMPLATE,
        rows=rows,
        status=status,
        query=query,
        counts=counts,
        tabs=STATUSES + ["all"],
        db_path=str(app.config["DB_PATH"]),
        filters=filters,
        has_filters=has_filters,
        domain_chips=domain_chips,
        signal_chips=signal_chips,
        sort_options=SORT_LABELS,
        score_options=SCORE_OPTIONS,
    )


ACTION_TO_STATUS = {
    "save": "reviewed",
    "posted": "posted",
    "archived": "archived",
    "skipped": "skipped",
}

ACTION_FLASH = {
    "save": ("Saved edits — moved to Reviewed.", "info"),
    "posted": ("Marked posted ✓", "info"),
    "archived": ("Archived.", "info"),
    "skipped": ("Skipped.", "danger"),
}


@app.route("/c/<int:cid>", methods=["POST"])
def update(cid: int):
    action = request.form.get("action") or "save"
    edited = request.form.get("suggested_comment")
    now = datetime.now(timezone.utc).isoformat()
    new_status = ACTION_TO_STATUS.get(action, "reviewed")

    conn = connect()
    try:
        prev = conn.execute(
            "SELECT status, suggested_comment, reviewed_at, posted_at "
            "FROM candidates WHERE id=?",
            (cid,),
        ).fetchone()
        if not prev:
            if wants_json():
                return jsonify({"ok": False, "error": "not found"}), 404
            flash("Candidate not found.", "danger")
            return redirect(request.referrer or url_for("index"))

        if action == "posted":
            conn.execute(
                "UPDATE candidates SET status=?, suggested_comment=?, "
                "posted_at=?, reviewed_at=? WHERE id=?",
                (new_status, edited, now, now, cid),
            )
        else:
            conn.execute(
                "UPDATE candidates SET status=?, "
                "suggested_comment=COALESCE(?, suggested_comment), "
                "reviewed_at=? WHERE id=?",
                (new_status, edited, now, cid),
            )
        conn.commit()
    finally:
        conn.close()

    msg, cat = ACTION_FLASH.get(action, ("Saved.", "info"))
    if wants_json():
        return jsonify({
            "ok": True,
            "cid": cid,
            "action": action,
            "status": new_status,
            "prev_status": prev["status"],
            "prev_text": prev["suggested_comment"],
            "prev_reviewed_at": prev["reviewed_at"],
            "prev_posted_at": prev["posted_at"],
            "msg": msg,
            "cat": cat,
        })
    flash(msg, cat)
    return redirect(request.referrer or url_for("index"))


@app.route("/c/<int:cid>/undo", methods=["POST"])
def undo(cid: int):
    prev_status = (request.form.get("prev_status") or "new").strip()
    if prev_status not in STATUSES:
        prev_status = "new"
    prev_text = request.form.get("prev_text")
    if prev_text == "":
        prev_text = None
    prev_reviewed = request.form.get("prev_reviewed_at") or None
    prev_posted = request.form.get("prev_posted_at") or None

    conn = connect()
    try:
        conn.execute(
            "UPDATE candidates SET status=?, "
            "suggested_comment=COALESCE(?, suggested_comment), "
            "reviewed_at=?, posted_at=? WHERE id=?",
            (prev_status, prev_text, prev_reviewed, prev_posted, cid),
        )
        conn.commit()
    finally:
        conn.close()

    if wants_json():
        return jsonify({
            "ok": True, "cid": cid, "status": prev_status,
            "msg": "Undone.", "cat": "info",
        })
    flash("Undone.", "info")
    return redirect(request.referrer or url_for("index"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Triage UI for the comments-discovery pipeline.")
    p.add_argument(
        "--db", type=Path, default=db_module.DB_PATH,
        help=f"Path to candidates.db (default: {db_module.DB_PATH})",
    )
    p.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p.add_argument(
        "--port", type=int, default=5050,
        help="Bind port (default: 5050; macOS reserves 5000 for AirPlay)",
    )
    p.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db.expanduser().resolve()
    if not db_path.exists():
        # Initialize an empty DB at this path so the UI can still load.
        db_module.init_db(db_path)
        print(f"Initialized empty candidates DB at {db_path}")
    app.config["DB_PATH"] = db_path
    print(f"Reviewing {db_path}")
    print(f"Open http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
