# Review Reaper Ops

## Current operating rule
- James approved daily Review Reaper outbound at up to 80 companies/day starting 2026-05-07.
- Send only verified direct business emails from official sites/contact pages.
- No contact forms, no duplicates, no scraped personal emails, no forced low-fit targets.
- Send in controlled waves of up to 20 and pause if SendGrid rejects, bounce/error/spam-risk signals appear, spam complaints/unsubscribes are detected, or reply quality degrades.

## First batch plan
- Market: Toronto / GTA
- Niches: restaurants, dental clinics, med spas/salons, auto repair, physio/chiro
- Target filter: 20-300 reviews, 3.2-4.4 rating, recent 1-3 star reviews, weak/no owner replies, visible email/contact form

## Files
- `targets.csv` — prospect list
- `drafts.md` — first outreach drafts
- `outreach-previews-YYYY-MM-DD.md` — approval-ready copy previews
- `send_outreach_batch.py` — safe batch sender; dry-run by default
- `sent-log.csv` — sent emails and follow-ups
- `replies.md` — reply tracking

## Sending rule
Generate/send flow still uses the sender scripts, but the daily cron has standing approval from James for up to 80/day.

Use waves, not one blind blast:

```bash
REVIEW_REAPER_OUTREACH_APPROVED=yes ./ops/send_soft_outreach_batch.py --send --limit 20
```

After each wave: verify SendGrid accepted the sends, duplicate-check names/emails, log successful sends in `sent-log.csv`, update `targets.csv`, and continue until 80/day or a quality/deliverability stop condition is hit.
