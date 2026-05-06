#!/usr/bin/env python3
"""Generate manual cold-outreach preview emails from ops/targets.csv.
Does not send anything. Outputs Markdown James can approve/edit.
"""
from __future__ import annotations
import csv
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / 'ops' / 'targets.csv'
OUT = ROOT / 'ops' / f'outreach-previews-{datetime.now().strftime("%Y-%m-%d")}.md'

TEMPLATE = """## {business_name}

**Status:** draft only — not sent  
**Niche/city:** {niche}, {city}  
**Known weakness:** {weakness}  
**Evidence snippets:** {bad_review_examples}  
**Contact needed:** {email_or_contact}

### Subject options
1. Quick note about {business_name}'s unanswered bad reviews
2. I mocked up responses for {business_name}'s recent complaints
3. Bad reviews are fixable — I made examples for {business_name}

### Email draft
Hi {business_name} team,

I was looking at recent public reviews for {business_name} and noticed a pattern around **{weakness_lower}**.

A couple examples stood out:

> {examples_as_quotes}

Most businesses either ignore these reviews or reply with something generic. That usually makes the complaint look more credible.

I built Review Reaper to catch reviews like these, identify the complaint theme, and draft a professional response/recovery offer for approval before anything goes public.

If useful, I can send over a mini audit for {business_name}: the recent negative reviews, the main themes, and 3 ready-to-use response drafts.

It is $97/month if you want ongoing monitoring, but the mini audit is free.

Worth sending it over?

— James  
Review Reaper

---
"""

def split_examples(s: str):
    parts = [p.strip().strip('"') for p in s.replace('“','"').replace('”','"').split(';') if p.strip()]
    return parts[:3] or [s.strip()]

def main():
    rows = list(csv.DictReader(TARGETS.open()))
    chunks = [f"# Review Reaper Outreach Previews — {datetime.now().strftime('%Y-%m-%d')}\n\nThese are drafts only. Nothing has been sent.\n"]
    for r in rows:
        examples = split_examples(r.get('bad_review_examples',''))
        chunks.append(TEMPLATE.format(
            business_name=r.get('business_name','').strip(),
            niche=r.get('niche','').strip(),
            city=r.get('city','').strip(),
            weakness=r.get('weakness','').strip(),
            weakness_lower=r.get('weakness','').strip().lower(),
            bad_review_examples=r.get('bad_review_examples','').strip(),
            email_or_contact=r.get('email_or_contact','').strip() or 'research needed',
            examples_as_quotes='\n> '.join(examples),
        ))
    OUT.write_text('\n'.join(chunks))
    print(OUT)

if __name__ == '__main__':
    main()
