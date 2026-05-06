"""Single-file Flask review UI.

Run:
    python review_ui.py
Then open http://localhost:5000

Workflow:
  - Default view shows 'new' candidates sorted by relevance_score desc
  - Each card shows the article preview, header image, suggested comment
  - Action buttons: Open article, Mark posted, Archive, Skip
  - Filter by status, search by domain
  - All edits write back to the same SQLite DB
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for

from db import connect, init_db

app = Flask(__name__)
init_db()

TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Ultra Zoom outreach review</title>
<style>
  :root {
    --bg: #0e0f12;
    --panel: #16181d;
    --panel-2: #1d2027;
    --ink: #e8e6dd;
    --ink-dim: #8b8a82;
    --accent: #d4a017;       /* aged brass */
    --accent-2: #6b8e6f;     /* faded olive */
    --danger: #b85450;
    --rule: #2a2d35;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0;
    font-family: "JetBrains Mono", "IBM Plex Mono", ui-monospace, monospace;
    background: var(--bg);
    color: var(--ink);
    font-size: 13px;
    line-height: 1.5;
  }
  header {
    border-bottom: 1px solid var(--rule);
    padding: 18px 28px;
    display: flex; align-items: baseline; gap: 24px;
    background: linear-gradient(180deg, #14161a 0%, var(--bg) 100%);
  }
  h1 {
    margin: 0;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
  h1 .accent { color: var(--accent); }
  nav { display: flex; gap: 4px; }
  nav a {
    color: var(--ink-dim);
    text-decoration: none;
    padding: 6px 12px;
    border: 1px solid transparent;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.08em;
  }
  nav a.active {
    color: var(--accent);
    border-color: var(--rule);
    background: var(--panel);
  }
  nav a:hover { color: var(--ink); }
  .stats { margin-left: auto; color: var(--ink-dim); font-size: 11px; }
  main { padding: 24px 28px; max-width: 1100px; }
  .card {
    background: var(--panel);
    border: 1px solid var(--rule);
    margin-bottom: 18px;
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 0;
  }
  .thumb {
    background: var(--panel-2) center/cover no-repeat;
    border-right: 1px solid var(--rule);
    min-height: 160px;
    position: relative;
  }
  .thumb .score {
    position: absolute; top: 8px; left: 8px;
    background: rgba(0,0,0,0.7);
    color: var(--accent);
    padding: 4px 8px;
    font-size: 11px;
    border: 1px solid var(--accent);
  }
  .thumb .system {
    position: absolute; bottom: 8px; left: 8px;
    background: rgba(0,0,0,0.7);
    color: var(--ink-dim);
    padding: 3px 7px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .body { padding: 16px 20px; }
  .title {
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: var(--ink);
  }
  .title a { color: inherit; text-decoration: none; }
  .title a:hover { color: var(--accent); }
  .meta {
    color: var(--ink-dim);
    font-size: 11px;
    margin-bottom: 10px;
    display: flex; gap: 12px; flex-wrap: wrap;
  }
  .meta .signal {
    color: var(--accent-2);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .caption {
    font-style: italic;
    color: var(--ink-dim);
    border-left: 2px solid var(--rule);
    padding: 4px 10px;
    margin: 8px 0;
    font-size: 12px;
  }
  .excerpt {
    color: var(--ink-dim);
    margin: 8px 0 12px 0;
    font-size: 12px;
    max-height: 4.5em;
    overflow: hidden;
    position: relative;
  }
  .suggestion {
    background: var(--panel-2);
    border: 1px solid var(--rule);
    padding: 10px 14px;
    margin: 12px 0;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 13px;
    line-height: 1.6;
    color: var(--ink);
    position: relative;
  }
  .suggestion::before {
    content: "DRAFT";
    position: absolute;
    top: -8px; left: 10px;
    background: var(--bg);
    color: var(--accent);
    font-family: monospace;
    font-size: 9px;
    padding: 0 6px;
    letter-spacing: 0.12em;
  }
  .suggestion.skip {
    color: var(--ink-dim);
    font-style: italic;
  }
  .suggestion.skip::before {
    content: "AI SAID SKIP";
    color: var(--danger);
  }
  textarea {
    width: 100%;
    background: var(--panel-2);
    border: 1px solid var(--rule);
    color: var(--ink);
    font-family: "IBM Plex Serif", Georgia, serif;
    font-size: 13px;
    padding: 10px 14px;
    min-height: 80px;
    resize: vertical;
  }
  textarea:focus { outline: 1px solid var(--accent); border-color: var(--accent); }
  .actions {
    display: flex; gap: 8px;
    margin-top: 12px;
    align-items: center;
  }
  .actions form { display: inline; }
  button, .btn {
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--rule);
    padding: 6px 14px;
    font-family: inherit;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    text-decoration: none;
    display: inline-block;
  }
  button:hover, .btn:hover { border-color: var(--ink); }
  button.primary { color: var(--accent); border-color: var(--accent); }
  button.primary:hover { background: var(--accent); color: var(--bg); }
  button.danger { color: var(--danger); border-color: var(--danger); }
  button.danger:hover { background: var(--danger); color: var(--bg); }
  .ext { color: var(--ink-dim); margin-left: auto; font-size: 11px; }
  .empty {
    text-align: center;
    color: var(--ink-dim);
    padding: 80px 20px;
    font-family: "IBM Plex Serif", Georgia, serif;
    font-style: italic;
  }
  .copy-btn {
    position: absolute;
    top: 8px; right: 8px;
    font-size: 9px;
    padding: 2px 6px;
    background: var(--bg);
    color: var(--ink-dim);
    border: 1px solid var(--rule);
    cursor: pointer;
  }
  .copy-btn:hover { color: var(--accent); border-color: var(--accent); }
</style>
</head>
<body>
<header>
  <h1>Ultra Zoom <span class="accent">// outreach review</span></h1>
  <nav>
    {% for s in ['new', 'reviewed', 'posted', 'archived', 'skipped', 'all'] %}
      <a href="{{ url_for('index', status=s) }}" class="{{ 'active' if status==s else '' }}">{{ s }}</a>
    {% endfor %}
  </nav>
  <div class="stats">
    {{ counts.new }} new · {{ counts.posted }} posted · ${{ '%.4f'|format(counts.cost or 0) }} spent
  </div>
</header>
<main>
{% if not rows %}
  <div class="empty">
    {% if status == 'new' %}
      No new candidates. Run <code>python pipeline.py --verbose</code> to discover more.
    {% else %}
      Nothing in <em>{{ status }}</em>.
    {% endif %}
  </div>
{% endif %}

{% for r in rows %}
  <article class="card">
    <div class="thumb" style="{% if r.header_image_url %}background-image: url('{{ r.header_image_url }}'){% endif %}">
      <span class="score">{{ '%.2f'|format(r.relevance_score) }}</span>
      {% if r.comment_system %}
        <span class="system">{{ r.comment_system }}{% if r.comment_count %} · {{ r.comment_count }}{% endif %}</span>
      {% endif %}
    </div>
    <div class="body">
      <h2 class="title"><a href="{{ r.url }}" target="_blank" rel="noopener">{{ r.article_title or r.url }}</a></h2>
      <div class="meta">
        <span>{{ r.site_title }}</span>
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
          <div style="position: relative;">
            <textarea name="suggested_comment">{{ r.suggested_comment }}</textarea>
            <button type="button" class="copy-btn" onclick="navigator.clipboard.writeText(this.previousElementSibling.value); this.textContent='COPIED'; setTimeout(()=>this.textContent='COPY',1200);">COPY</button>
          </div>
          <div class="actions">
            <button type="submit" name="action" value="save">Save edits</button>
            <button type="submit" name="action" value="posted" class="primary">Mark posted</button>
            <button type="submit" name="action" value="archived">Archive</button>
            <button type="submit" name="action" value="skipped" class="danger">Skip</button>
            <a class="ext" href="{{ r.url }}" target="_blank" rel="noopener">open ↗</a>
          </div>
        </form>
      {% else %}
        <div class="suggestion skip">No comment drafted (article not a fit).</div>
        <form method="post" action="{{ url_for('update', cid=r.id) }}">
          <div class="actions">
            <button type="submit" name="action" value="archived">Archive</button>
            <a class="ext" href="{{ r.url }}" target="_blank" rel="noopener">open ↗</a>
          </div>
        </form>
      {% endif %}
    </div>
  </article>
{% endfor %}
</main>
</body>
</html>
"""


@app.route("/")
def index():
    status = request.args.get("status", "new")
    with connect() as conn:
        if status == "all":
            rows = conn.execute(
                "SELECT * FROM candidates ORDER BY relevance_score DESC, fetched_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE status = ? ORDER BY relevance_score DESC, fetched_at DESC",
                (status,),
            ).fetchall()
        counts = {
            "new": conn.execute("SELECT COUNT(*) FROM candidates WHERE status='new'").fetchone()[0],
            "posted": conn.execute("SELECT COUNT(*) FROM candidates WHERE status='posted'").fetchone()[0],
            "cost": conn.execute("SELECT COALESCE(SUM(suggestion_cost_usd),0) FROM candidates").fetchone()[0],
        }
    return render_template_string(TEMPLATE, rows=rows, status=status, counts=counts)


@app.route("/c/<int:cid>", methods=["POST"])
def update(cid: int):
    action = request.form.get("action")
    edited = request.form.get("suggested_comment")
    now = datetime.now(timezone.utc).isoformat()

    new_status = {
        "save": "reviewed",
        "posted": "posted",
        "archived": "archived",
        "skipped": "skipped",
    }.get(action, "reviewed")

    with connect() as conn:
        if action == "posted":
            conn.execute(
                "UPDATE candidates SET status=?, suggested_comment=?, posted_at=?, reviewed_at=? WHERE id=?",
                (new_status, edited, now, now, cid),
            )
        else:
            conn.execute(
                "UPDATE candidates SET status=?, suggested_comment=?, reviewed_at=? WHERE id=?",
                (new_status, edited, now, cid),
            )

    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
