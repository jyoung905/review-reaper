# Review Reaper Revenue Status — 2026-05-06

## Live app health
- Production landing: `https://review-reaper-production.up.railway.app/` returns 200.
- Production pricing: `/pricing` returns 200 and shows the $97/mo checkout page.
- Production Stripe checkout: `/api/create-checkout-session` returns a live Stripe Checkout URL.
- Old Railway URL `https://web-production-523053.up.railway.app/` returns 404; use `review-reaper-production.up.railway.app`.

## Code fixes prepared locally
- Added `/health` JSON endpoint for deploy/uptime checks.
- Locked `/api/send-outreach` behind admin password auth. It previously accepted unauthenticated POSTs.
- Locked `/api/scrape-businesses` behind admin password auth.
- Fixed admin JS helper so GET requests no longer send a JSON body.
- Made outreach email `FROM_EMAIL`, `FROM_NAME`, and CTA `BASE_URL` configurable from environment.
- Escaped dynamic outreach email fields before rendering HTML.

## Local verification
- `python3 -m compileall api src` passes in the project venv.
- Local `/health` returns JSON 200.
- Local unauthenticated `/api/send-outreach` returns 401.
- Local authenticated `/api/scrape-businesses` returns 200 placeholder response.
- Local `/pricing` returns 200.
- Local checkout returns simulated success because local `STRIPE_PRICE_ID` is blank; production checkout is live.

## First outreach batch
- Draft-only outreach previews generated: `ops/outreach-previews-2026-05-06.md`.
- Prospect list updated: `ops/targets.csv`.
- Nothing has been sent externally.

### Candidate 1: Midtown Dental Centre
- Contact found: `info@midtowndental.ca`; contact page `https://midtowndental.ca/contact/`; phone `(416) 966-3368`.
- Angle: pricing transparency and alleged unnecessary upsells.
- Status: draft ready; needs James approval before send.

### Candidate 2: WestClair Dental
- Contact found: official contact form `https://westclairdental.com/contact`; phone `+1 416-760-7660`.
- No direct email found on official site.
- Angle: staff/front desk rudeness complaints.
- Status: contact-form draft ready; needs James approval before send.

## Blockers
- Railway CLI is not logged in locally, so direct `railway up` deploy is blocked unless login is restored.
- Cold outreach send still requires James approval for first batch/content.

## Expanded prospect batch update
- Added 8 more Toronto/GTA prospects from subagent research, bringing `ops/targets.csv` to 10 total targets.
- 7 targets currently have direct-email payloads prepared by `ops/send_outreach_batch.py`; 3 are contact-form/phone only.
- Important quality rule added to `ops/outreach-previews-2026-05-06.md`: rows marked for screenshot verification should not be sent until exact public review evidence is captured.
- Verified contact emails from official site HTML for: Rejuvenation Med Clinic, Medica Laser Spa, Skin Vitality, Tony Shamas, Dupont Auto Repair, Harbourfront Chiropractic.
- Nothing has been sent externally.

## Evidence verification + send-ready batch
- Verified exact public review evidence for Midtown Dental Centre, WestClair Dental, and Dupont Auto Repair.
- Direct-email send-ready rows: Midtown Dental Centre and Dupont Auto Repair.
- Contact-form verified row: WestClair Dental; no direct email found, so not included in email sender.
- Remaining 7 targets require manual Google screenshot verification before quote-based outreach.
- Added `ops/evidence-verified-2026-05-06.csv` and `ops/send-ready-approval-pack-2026-05-06.md`.
- Updated `ops/send_outreach_batch.py` so default mode only includes `send_ready_needs_approval` rows and uses verified exact review snippets, not generic placeholder reviews.

## First outreach sent
- Sent approved first batch on 2026-05-06 at ~10:44 EDT.
- Midtown Dental Centre → `info@midtowndental.ca` → SendGrid accepted status 202.
- Dupont Auto Repair → `info@dupontautorepair.ca` → SendGrid accepted status 202.
- Logged both sends in `ops/sent-log.csv`.
- Marked both targets as sent in `ops/targets.csv` with follow-up due 2026-05-11 if no reply.

## Outbound paused after business-plan review
- James correctly flagged that the outbound/customer journey was underdeveloped.
- Outbound is now paused until business plan, reply handling, onboarding, and fulfillment are completed.
- Added docs:
  - `ops/OUTBOUND_PAUSED.md`
  - `ops/BUSINESS_PLAN.md`
  - `ops/REPLY_HANDLING_SOP.md`
  - `ops/ONBOARDING_AND_FULFILLMENT.md`
- New strategy: cold email should offer a free mini-audit first, not push straight to monthly subscription.
- If existing recipients reply, draft/helpful responses should be prepared; do not send externally without James approval unless explicitly delegated.
