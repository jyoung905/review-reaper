# Review Reaper Ops

## Current operating rule
- Prepare targets and outreach drafts proactively.
- Do not send external cold outreach until James approves the first batch/content.

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
Generate/send flow:

```bash
./ops/send_outreach_batch.py --limit 5
```

This only prints API payloads. To actually send after James approves the exact batch/content:

```bash
REVIEW_REAPER_OUTREACH_APPROVED=yes ./ops/send_outreach_batch.py --send --limit 5
```

Do not set `REVIEW_REAPER_OUTREACH_APPROVED=yes` until the batch has explicit approval.
