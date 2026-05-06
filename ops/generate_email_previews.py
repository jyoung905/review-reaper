#!/usr/bin/env python3
"""Generate full browser-openable HTML previews for send-ready outreach emails.
No emails are sent.
"""
from __future__ import annotations
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.email_sender import _build_outreach_html  # preview only; does not send
from ops.send_outreach_batch import payload_for, load_env_password

TARGETS = ROOT / "ops" / "targets.csv"
OUTDIR = ROOT / "ops" / "email-previews-2026-05-06"
INDEX = OUTDIR / "index.html"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    password = load_env_password()
    rows = [r for r in csv.DictReader(TARGETS.open()) if r.get("status") == "send_ready_needs_approval"]
    previews = []
    for row in rows:
        payload = payload_for(row, password)
        if not payload:
            continue
        html = _build_outreach_html(payload["business_name"], payload["reviews"])
        name = slug(payload["business_name"])
        path = OUTDIR / f"{name}.html"
        path.write_text(html)
        previews.append((payload["business_name"], payload["recipient_email"], path.name, len(payload["reviews"])))

    links = "\n".join(
        f'<li><a href="{filename}">{business}</a> — {email} — {count} review snippets</li>'
        for business, email, filename, count in previews
    )
    INDEX.write_text(f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Review Reaper Email Previews</title>
<style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:820px;margin:40px auto;padding:0 20px;line-height:1.55;color:#111827}} code{{background:#f3f4f6;padding:2px 5px;border-radius:4px}} li{{margin:10px 0}}</style>
</head><body>
<h1>Review Reaper Email Previews — 2026-05-06</h1>
<p>Generated from the actual SendGrid HTML template. Nothing has been sent.</p>
<ul>{links}</ul>
<p>Send command after approval:</p>
<pre><code>REVIEW_REAPER_OUTREACH_APPROVED=yes ./ops/send_outreach_batch.py --send</code></pre>
</body></html>""")
    print(INDEX)
    for _, _, filename, _ in previews:
        print(OUTDIR / filename)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
