"""Stage 3: side-by-side review UI for the image-gallery pipeline.

Run:
    python review_ui.py                          # open ./gallery.db
    python review_ui.py --db ~/Downloads/gallery.db
    python review_ui.py --port 5051

Workflow:
  - Tabs filter by status. Default view is `enhanced` — items waiting on
    your verdict.
  - Each card shows the original next to the enhanced version, with the
    source title pre-filled and tag/title fields editable.
  - Approve writes the queue row with a scheduled time picked by the
    scheduler. Reject moves the candidate to status='rejected'.
  - Keyboard shortcuts (press `?` for the cheat sheet):
      j / k    next / previous card
      v        approve & schedule
      x        reject
      e        focus the title field
      /        focus search
"""
from __future__ import annotations

import argparse
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask, abort, flash, get_flashed_messages, redirect,
    render_template_string, request, send_from_directory, url_for,
)

import db as db_module
from config import CANDIDATES_DIR, ENHANCED_DIR
from scheduler import next_free_slot

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


def connect():
    conn = sqlite3.connect(app.config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Status surfaced in tabs. Note `enhanced` is the default review view —
# Stage 1 inserts as `new`, Stage 2 promotes to `enhanced`, and the human
# moves it to `approved`/`rejected` from this UI.
STATUSES = ["enhanced", "approved", "queued", "posted", "rejected", "new", "all"]
DEFAULT_STATUS = "enhanced"

TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ultra Zoom · gallery review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  /* Theme-matched to Imgur's dark UI: muted slate panels, that signature
     Imgur green for primary actions, Open Sans throughout. */
  :root {
    --bg:        #2c2f34;     /* Imgur app background */
    --panel:     #353a40;     /* card / panel */
    --panel-2:   #3f444a;     /* nested input wells */
    --ink:       #dfe3e6;     /* primary text */
    --ink-dim:   #a5abb0;     /* secondary */
    --ink-faint: #6f767c;
    --accent:    #1bb76e;     /* Imgur green */
    --accent-2:  #1bb76e;
    --accent-hover: #16a060;
    --danger:    #e0245e;
    --rule:      #404449;
    --rule-soft: #4a4f55;
    --shadow:    0 1px 0 rgba(255,255,255,0.03), 0 6px 20px rgba(0,0,0,0.40);
    --radius:    4px;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0; padding: 0;
    font-family: "Open Sans", -apple-system, BlinkMacSystemFont, "Segoe UI",
                 Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--ink);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { color: var(--accent-hover); text-decoration: underline; }

  header {
    border-bottom: 1px solid var(--rule);
    padding: 16px 28px 0 28px;
    background: var(--panel);
    position: sticky; top: 0; z-index: 10;
    box-shadow: 0 2px 0 rgba(0,0,0,0.10);
  }
  .header-row { display: flex; align-items: baseline; gap: 24px; flex-wrap: wrap; }
  h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0;
    white-space: nowrap;
  }
  h1 .accent { color: var(--accent); }
  .stats {
    margin-left: auto;
    color: var(--ink-dim);
    font-size: 12px;
    text-align: right;
  }
  .stats .db-path { color: var(--ink-faint); font-size: 10px; margin-top: 3px; word-break: break-all; }

  nav { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 14px; border-bottom: 1px solid var(--rule); margin-bottom: -1px; }
  nav a {
    color: var(--ink-dim); text-decoration: none;
    padding: 9px 16px;
    border: 1px solid transparent; border-bottom: none;
    border-radius: var(--radius) var(--radius) 0 0;
    font-size: 12px; font-weight: 600;
    display: flex; align-items: baseline; gap: 6px;
    text-transform: capitalize;
  }
  nav a .count { color: var(--ink-faint); font-size: 11px; font-weight: 400; }
  nav a.active {
    color: var(--accent);
    border-color: var(--rule);
    background: var(--bg);
    border-bottom: 1px solid var(--bg);
  }
  nav a.active .count { color: var(--accent); }
  nav a:hover { color: var(--ink); text-decoration: none; }

  .toolbar {
    display: flex; gap: 12px; align-items: center;
    padding: 14px 28px;
    background: var(--panel);
    border-bottom: 1px solid var(--rule);
  }
  .toolbar input[type=search] {
    flex: 1; max-width: 520px;
    background: var(--panel-2); border: 1px solid var(--rule); color: var(--ink);
    font-family: inherit; font-size: 13px; padding: 8px 12px;
    border-radius: var(--radius);
  }
  .toolbar input[type=search]::placeholder { color: var(--ink-faint); }
  .toolbar input[type=search]:focus { outline: none; border-color: var(--accent); background: var(--bg); }
  .toolbar .help { color: var(--ink-faint); font-size: 12px; margin-left: auto; cursor: help; }
  .toolbar .help:hover { color: var(--accent); }

  .flash-stack { position: fixed; top: 16px; right: 20px; z-index: 50; display: flex; flex-direction: column; gap: 8px; max-width: 380px; }
  .flash {
    background: var(--panel); border-left: 3px solid var(--accent);
    color: var(--ink); padding: 10px 16px; box-shadow: var(--shadow);
    font-size: 13px; border-radius: var(--radius);
    animation: fade-out 4s forwards;
  }
  .flash.danger { border-left-color: var(--danger); }
  @keyframes fade-out { 0%,70% { opacity: 1; } 100% { opacity: 0; transform: translateX(8px); } }

  main { padding: 24px 28px 80px 28px; max-width: 1400px; }

  .card {
    background: var(--panel);
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    margin-bottom: 22px;
    box-shadow: var(--shadow);
    scroll-margin-top: 180px;
    overflow: hidden;
  }
  .card.is-active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent), var(--shadow); }

  .compare {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
    background: #000;
  }
  @media (max-width: 900px) { .compare { grid-template-columns: 1fr; } }
  .compare figure {
    margin: 0; padding: 0;
    position: relative;
    background: #000;
    min-height: 220px;
    display: flex; align-items: center; justify-content: center;
  }
  .compare img { max-width: 100%; max-height: 520px; display: block; }
  .compare figure + figure { border-left: 1px solid var(--rule); }
  @media (max-width: 900px) { .compare figure + figure { border-left: none; border-top: 1px solid var(--rule); } }
  .compare .label {
    position: absolute; top: 10px; left: 10px;
    background: rgba(0,0,0,0.72); color: var(--ink);
    padding: 4px 10px; font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
    border-radius: var(--radius);
  }
  .compare .label.before { color: var(--ink-dim); }
  .compare .label.after { color: #fff; background: var(--accent); }
  .compare .dim {
    position: absolute; bottom: 10px; right: 10px;
    background: rgba(0,0,0,0.72); color: var(--ink-dim);
    padding: 3px 8px; font-size: 11px; border-radius: var(--radius);
  }

  .body { padding: 18px 22px; }
  .meta {
    color: var(--ink-dim); font-size: 12px; margin-bottom: 12px;
    display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
  }
  .meta .source {
    color: #fff; padding: 2px 8px; border-radius: var(--radius);
    font-weight: 700; font-size: 10px; letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .meta .source.reddit  { background: #ff4500; }
  .meta .source.commons { background: #4f95dd; }   /* Wikimedia blue */
  .meta .source.nasa    { background: #0b3d91; }   /* NASA blue */
  .meta .source.exa     { background: #6f4ec7; }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin: 14px 0;
  }
  @media (max-width: 700px) { .form-grid { grid-template-columns: 1fr; } }
  label.field { display: flex; flex-direction: column; gap: 6px; font-size: 11px; color: var(--ink-dim); font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
  label.field input {
    background: var(--panel-2); border: 1px solid var(--rule); color: var(--ink);
    font-family: inherit; font-size: 14px; font-weight: 400; padding: 9px 12px;
    border-radius: var(--radius);
  }
  label.field input:focus { outline: none; border-color: var(--accent); background: var(--bg); }

  .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; align-items: center; }
  button, .btn {
    background: var(--panel-2); color: var(--ink);
    border: 1px solid var(--rule); padding: 8px 18px;
    font-family: inherit; font-size: 13px; font-weight: 600;
    cursor: pointer; text-decoration: none; display: inline-block;
    border-radius: var(--radius);
    transition: background 100ms, border-color 100ms, color 100ms;
  }
  button:hover, .btn:hover { background: var(--rule-soft); border-color: var(--rule-soft); }
  button.primary {
    color: #fff; background: var(--accent); border-color: var(--accent);
  }
  button.primary:hover { background: var(--accent-hover); border-color: var(--accent-hover); }
  button.danger { color: #fff; background: transparent; border-color: var(--danger); color: var(--danger); }
  button.danger:hover { background: var(--danger); color: #fff; }
  .ext { color: var(--ink-dim); margin-left: auto; font-size: 12px; }
  .ext:hover { color: var(--accent); }

  .empty { text-align: center; color: var(--ink-dim); padding: 80px 20px; }
  .empty code { font-family: ui-monospace, "SF Mono", Consolas, monospace; background: var(--panel-2); border: 1px solid var(--rule); padding: 2px 8px; color: var(--accent); border-radius: var(--radius); }

  .schedule-line { color: var(--ink-dim); font-size: 12px; margin-top: 8px; }
  .schedule-line strong { color: var(--accent); font-weight: 700; }

  dialog#shortcuts {
    background: var(--panel); color: var(--ink);
    border: 1px solid var(--rule);
    border-radius: var(--radius);
    padding: 22px 26px; box-shadow: var(--shadow);
    font-family: inherit; font-size: 13px; max-width: 380px;
  }
  dialog#shortcuts::backdrop { background: rgba(0,0,0,0.6); }
  dialog#shortcuts h2 { margin: 0 0 14px 0; font-size: 16px; font-weight: 700; color: var(--accent); }
  dialog#shortcuts table { border-collapse: collapse; width: 100%; }
  dialog#shortcuts td { padding: 5px 8px; }
  dialog#shortcuts td:first-child { color: var(--accent); font-weight: 700; width: 80px; text-align: right; }
  dialog#shortcuts .close { margin-top: 16px; }
</style>
</head>
<body>
<header>
  <div class="header-row">
    <h1>Ultra Zoom <span class="accent">// gallery review</span></h1>
    <div class="stats">
      <div>{{ counts.enhanced }} pending · {{ counts.approved }} approved · {{ counts.queued }} queued · {{ counts.posted }} posted</div>
      {% if counts.next_slot %}<div>Next free slot: <strong>{{ counts.next_slot }}</strong></div>{% endif %}
      <div class="db-path">{{ db_path }}</div>
    </div>
  </div>
  <nav>
    {% for s in tabs %}
      <a href="{{ url_for('index', status=s, q=query) }}" class="{{ 'active' if status==s else '' }}">
        {{ s }}<span class="count">{{ counts[s] if s != 'all' else counts.total }}</span>
      </a>
    {% endfor %}
  </nav>
</header>

<form class="toolbar" method="get" action="{{ url_for('index') }}">
  <input type="hidden" name="status" value="{{ status }}">
  <input type="search" name="q" id="search" value="{{ query or '' }}" placeholder="Search title, source, url…" autocomplete="off">
  <button type="submit">Search</button>
  {% if query %}<a href="{{ url_for('index', status=status) }}" class="btn">Clear</a>{% endif %}
  <span class="help" onclick="document.getElementById('shortcuts').showModal()" tabindex="0">? shortcuts</span>
</form>

{% set msgs = get_flashed_messages(with_categories=true) %}
{% if msgs %}
  <div class="flash-stack">
    {% for cat, msg in msgs %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}
  </div>
{% endif %}

<main>
{% if not rows %}
  <div class="empty">
    {% if status == 'enhanced' %}
      Nothing waiting on review. Run <code>python discover.py --reddit --commons --nasa</code>
      then <code>python enhance.py --verbose</code>.
    {% else %}
      Nothing in <em>{{ status }}</em>.
    {% endif %}
  </div>
{% endif %}

{% for r in rows %}
  <article class="card" data-id="{{ r.id }}" data-url="{{ r.source_url or '' }}" tabindex="-1">
    <div class="compare">
      <figure>
        <span class="label before">ORIGINAL</span>
        <img src="{{ url_for('serve_candidate', cid=r.id) }}" alt="">
        <span class="dim">{{ r.image_width or '?' }}×{{ r.image_height or '?' }} · {{ ((r.image_bytes or 0) // 1024) }}KB</span>
      </figure>
      {% if r.enhanced_path %}
      <figure>
        <span class="label after">ENHANCED · 4×</span>
        <img src="{{ url_for('serve_enhanced', cid=r.id) }}" alt="">
        <span class="dim">{{ r.enhanced_width or '?' }}×{{ r.enhanced_height or '?' }} · {{ ((r.enhanced_bytes or 0) // 1024) }}KB</span>
      </figure>
      {% else %}
      <figure>
        <span class="label">NOT ENHANCED YET</span>
        {% if r.enhance_error %}<div style="color: var(--danger); font-size: 12px; padding: 16px;">{{ r.enhance_error }}</div>{% endif %}
      </figure>
      {% endif %}
    </div>
    <div class="body">
      <div class="meta">
        <span class="source {{ r.source }}">{{ r.source }}</span>
        {% if r.source_score %}<span>{{ r.source_score }} pts</span>{% endif %}
        {% if r.source_author %}<span>by {{ r.source_author }}</span>{% endif %}
        {% if r.source_published_at %}<span>{{ r.source_published_at[:10] }}</span>{% endif %}
        {% if r.source_url %}<a href="{{ r.source_url }}" target="_blank" rel="noopener">source ↗</a>{% endif %}
      </div>

      <form method="post" action="{{ url_for('update', cid=r.id) }}">
        <div class="form-grid">
          <label class="field">
            Title
            <input name="title" value="{{ r.title or r.source_title or '' }}" maxlength="200">
          </label>
          <label class="field">
            Tags (comma-separated)
            <input name="tags" value="{{ r.tags or '' }}" placeholder="space, mountain, nature">
          </label>
        </div>
        {% if r.scheduled_at %}
          <div class="schedule-line">Scheduled for <strong>{{ r.scheduled_at }}</strong> UTC</div>
        {% endif %}
        <div class="actions">
          <button type="submit" name="action" value="save">Save</button>
          {% if r.status == 'enhanced' %}
            <button type="submit" name="action" value="approve" class="primary" data-shortcut="v">Approve & schedule</button>
            <button type="submit" name="action" value="reject" class="danger" data-shortcut="x">Reject</button>
          {% elif r.status in ('approved', 'queued') %}
            <button type="submit" name="action" value="reject" class="danger" data-shortcut="x">Pull from queue</button>
          {% endif %}
        </div>
      </form>
    </div>
  </article>
{% endfor %}
</main>

<dialog id="shortcuts">
  <h2>Keyboard shortcuts</h2>
  <table>
    <tr><td>j / ↓</td><td>next card</td></tr>
    <tr><td>k / ↑</td><td>previous card</td></tr>
    <tr><td>v</td><td>approve & schedule</td></tr>
    <tr><td>x</td><td>reject</td></tr>
    <tr><td>e</td><td>edit title</td></tr>
    <tr><td>/</td><td>focus search</td></tr>
    <tr><td>?</td><td>this dialog</td></tr>
    <tr><td>esc</td><td>blur / close</td></tr>
  </table>
  <form method="dialog"><button>close</button></form>
</dialog>

<script>
(() => {
  const cards = Array.from(document.querySelectorAll('.card'));
  let active = -1;
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
      e.preventDefault(); document.getElementById('shortcuts').showModal(); return;
    }
    if (e.key === '/') { e.preventDefault(); document.getElementById('search').focus(); return; }
    if (e.key === 'j' || e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(active + 1, cards.length - 1)); return; }
    if (e.key === 'k' || e.key === 'ArrowUp')   { e.preventDefault(); setActive(Math.max(active - 1, 0)); return; }
    if (active < 0) return;
    const card = cards[active];
    if (e.key === 'e') {
      e.preventDefault();
      const inp = card.querySelector('input[name="title"]');
      if (inp) inp.focus();
    } else if (['v', 'x'].includes(e.key)) {
      e.preventDefault(); clickShortcut(card, e.key);
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
    status = request.args.get("status", DEFAULT_STATUS)
    query = (request.args.get("q") or "").strip()
    if status not in STATUSES:
        status = DEFAULT_STATUS

    where = []
    params: list = []
    if status != "all":
        where.append("c.status = ?")
        params.append(status)
    if query:
        where.append(
            "(LOWER(COALESCE(c.title,'')) LIKE ? "
            " OR LOWER(COALESCE(c.source_title,'')) LIKE ? "
            " OR LOWER(COALESCE(c.source_url,'')) LIKE ? "
            " OR LOWER(COALESCE(c.tags,'')) LIKE ?)"
        )
        like = f"%{query.lower()}%"
        params.extend([like, like, like, like])

    sql = """
        SELECT c.*, q.scheduled_at
        FROM candidates c
        LEFT JOIN queue q ON q.candidate_id = c.id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.id DESC"

    conn = connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        counts = {s: 0 for s in STATUSES}
        for s in STATUSES:
            if s == "all":
                continue
            counts[s] = conn.execute(
                "SELECT COUNT(*) FROM candidates WHERE status=?", (s,)
            ).fetchone()[0]
        counts["total"] = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        # Peek next free slot for the header.
        taken = [r[0] for r in conn.execute(
            "SELECT scheduled_at FROM queue WHERE status IN ('pending','claimed')"
        ).fetchall()]
        try:
            counts["next_slot"] = next_free_slot(taken).isoformat(timespec="minutes")
        except Exception:
            counts["next_slot"] = None
    finally:
        conn.close()

    return render_template_string(
        TEMPLATE,
        rows=rows, status=status, query=query, counts=counts,
        tabs=STATUSES, db_path=str(app.config["DB_PATH"]),
    )


@app.route("/c/<int:cid>", methods=["POST"])
def update(cid: int):
    action = request.form.get("action") or "save"
    title = (request.form.get("title") or "").strip() or None
    tags = (request.form.get("tags") or "").strip() or None
    now = datetime.now(timezone.utc).isoformat()

    conn = connect()
    try:
        if action == "save":
            conn.execute(
                "UPDATE candidates SET title=?, tags=?, reviewed_at=? WHERE id=?",
                (title, tags, now, cid),
            )
            flash("Saved.", "info")
        elif action == "approve":
            taken = [r[0] for r in conn.execute(
                "SELECT scheduled_at FROM queue WHERE status IN ('pending','claimed')"
            ).fetchall()]
            slot = next_free_slot(taken).isoformat(timespec="seconds")
            conn.execute(
                "UPDATE candidates SET title=?, tags=?, status='approved', reviewed_at=? WHERE id=?",
                (title, tags, now, cid),
            )
            conn.execute(
                "INSERT INTO queue (candidate_id, scheduled_at, enqueued_at, status) "
                "VALUES (?,?,?,?) "
                "ON CONFLICT(candidate_id) DO UPDATE SET scheduled_at=excluded.scheduled_at, "
                "enqueued_at=excluded.enqueued_at, status='pending', last_error=NULL",
                (cid, slot, now, "pending"),
            )
            conn.execute("UPDATE candidates SET status='queued' WHERE id=?", (cid,))
            flash(f"Approved. Scheduled for {slot} UTC.", "info")
        elif action == "reject":
            conn.execute(
                "UPDATE candidates SET status='rejected', reviewed_at=? WHERE id=?",
                (now, cid),
            )
            conn.execute("DELETE FROM queue WHERE candidate_id=?", (cid,))
            flash("Rejected.", "danger")
        conn.commit()
    finally:
        conn.close()
    return redirect(request.referrer or url_for("index"))


def _serve(folder: Path, rel_field: str, cid: int):
    conn = connect()
    try:
        row = conn.execute(f"SELECT {rel_field} FROM candidates WHERE id=?", (cid,)).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        abort(404)
    rel = row[0]
    # Stored as "image-gallery/candidates/ab/abc.jpg" relative to repo's outreach/
    abs_path = Path(__file__).parent.parent / rel
    if not abs_path.exists() or not abs_path.is_file():
        abort(404)
    return send_from_directory(abs_path.parent, abs_path.name)


@app.route("/img/candidate/<int:cid>")
def serve_candidate(cid: int):
    return _serve(CANDIDATES_DIR, "image_path", cid)


@app.route("/img/enhanced/<int:cid>")
def serve_enhanced(cid: int):
    return _serve(ENHANCED_DIR, "enhanced_path", cid)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Triage UI for the image-gallery pipeline.")
    p.add_argument("--db", type=Path, default=db_module.DB_PATH,
                   help=f"Path to gallery.db (default: {db_module.DB_PATH})")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5051,
                   help="Bind port (default: 5051; comments-discovery uses 5050)")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db.expanduser().resolve()
    if not db_path.exists():
        db_module.init_db(db_path)
        print(f"Initialized empty gallery DB at {db_path}")
    app.config["DB_PATH"] = db_path
    print(f"Reviewing {db_path}")
    print(f"Open http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
