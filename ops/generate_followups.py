#!/usr/bin/env python3
"""Generate follow-up drafts for Review Reaper outreach.
No emails are sent.
"""
from __future__ import annotations
import csv
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENT = ROOT / "ops" / "sent-log.csv"
OUT = ROOT / "ops" / f"followup-drafts-{date.today().isoformat()}.md"


def parse_date(value: str):
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except Exception:
        return None


def main():
    rows = list(csv.DictReader(SENT.open())) if SENT.exists() else []
    today = date.today()
    due = []
    future = []
    for r in rows:
        d = parse_date(r.get("followup_due", ""))
        if d and d <= today and r.get("status") == "sent":
            due.append(r)
        elif d:
            future.append(r)
    chunks = [f"# Review Reaper Follow-up Drafts — {today.isoformat()}\n\nNothing has been sent.\n"]
    if due:
        chunks.append("## Due now\n")
        for r in due:
            biz = r.get("business_name", "the business")
            chunks.append(f"### {biz}\n\nTo: `{r.get('email_or_contact','')}`  \nOriginal subject: {r.get('subject','')}\n\nSubject: Quick follow-up on {biz}'s review mini-audit\n\nHi there,\n\nQuick follow-up — want me to send over the free Review Reaper mini-audit for {biz}?\n\nIt would include the negative review themes I found, 2–3 suggested response drafts, and the first reputation fix I’d make.\n\nIf not useful, no worries and I won’t follow up again.\n\n— James\n\n---\n")
    else:
        chunks.append("## Due now\n\nNo follow-ups due today.\n")
    if future:
        chunks.append("\n## Upcoming\n")
        for r in future:
            chunks.append(f"- {r.get('followup_due')}: {r.get('business_name')} → {r.get('email_or_contact')}\n")
    OUT.write_text("".join(chunks))
    print(OUT)


if __name__ == "__main__":
    main()
