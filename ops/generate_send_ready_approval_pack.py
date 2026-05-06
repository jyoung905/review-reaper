#!/usr/bin/env python3
"""Create a human approval pack for send-ready Review Reaper emails."""
from __future__ import annotations
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'ops' / f'send-ready-approval-pack-{datetime.now().strftime("%Y-%m-%d")}.md'

payloads = json.loads(subprocess.check_output([str(ROOT / 'ops' / 'send_outreach_batch.py')], stderr=subprocess.DEVNULL, cwd=ROOT))
chunks = [f"# Review Reaper Send-Ready Approval Pack — {datetime.now().strftime('%Y-%m-%d')}\n\nNothing has been sent. These are the only direct-email targets with verified public review evidence.\n"]
for p in payloads:
    biz = p['business_name']
    email = p['recipient_email']
    chunks.append(f"## {biz}\n\n**Recipient:** `{email}`  \n**Subject:** I noticed {biz} has unanswered bad reviews\n\n### Evidence included\n")
    for r in p['reviews']:
        chunks.append(f"> {r['text']}\n")
    chunks.append("### Email angle\n")
    chunks.append(f"Hi there,\n\nI noticed **{biz}** has unanswered negative reviews on public review sites. Left unaddressed, bad reviews can cost potential customers.\n\nHere's how 3 of them could have been handled with professional, approval-ready response drafts.\n\nReview Reaper automatically detects negative reviews, drafts context-aware replies, suggests recovery offers, tracks complaint themes, and requires approval before anything is posted.\n\nWant to see **{biz}'s** full audit? I can show every negative review with ready-to-approve responses.\n\n— James / Review Reaper\n\n---\n")
chunks.append("## Send command after approval\n\n```bash\nREVIEW_REAPER_OUTREACH_APPROVED=yes ./ops/send_outreach_batch.py --send\n```\n")
OUT.write_text('\n'.join(chunks))
print(OUT)
