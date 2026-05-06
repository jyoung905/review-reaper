# Review Reaper Elite Operating System

## Current rule
Outbound is paused until the business is fully operational. Existing replies are handled through the operating desk and SOP.

## Live customer journey
1. Prospect sees landing page or outreach.
2. CTA points to `/mini-audit`, not straight to paid subscription.
3. Prospect requests a free mini-audit.
4. Ops desk receives the lead in `/admin/ops`.
5. We prepare a useful mini-audit: negative review themes, example response drafts, and recommended fixes.
6. Only after value is delivered do we pitch $97/month.
7. If they subscribe, Stripe redirects to `/subscribe/success`.
8. Success page now sends them to `/onboarding`.
9. Customer submits business profile, review URL, approval email, tone, and liability notes.
10. Ops desk receives onboarding submission and queues first review scan.

## Built app surfaces
- `/mini-audit` — free audit request page.
- `/onboarding` — paid customer onboarding page.
- `/subscribe/success` — now routes to onboarding instead of admin dashboard.
- `/admin/ops` — operating desk for customers/leads, onboarding queue, mini-audits, and reply drafts.

## Built APIs
- `POST /api/mini-audit` — captures free mini-audit lead.
- `POST /api/onboarding` — captures paid customer onboarding.
- `POST /api/reply-event` — logs inbound replies and generates recommended reply drafts; admin-auth required.
- `GET /api/customers?password=...` — admin-only customer/lead list.
- `GET /api/onboarding?password=...` — admin-only onboarding queue.
- `GET /api/mini-audits?password=...` — admin-only mini-audit queue.
- `GET /api/replies?password=...` — admin-only reply queue.

## Built database tables
- `customers`
- `onboarding_submissions`
- `mini_audits`
- `reply_events`

## Offer correction
Cold outreach should offer a free mini-audit first. The email CTA now points to `/mini-audit`.

## Current product promise
Review Reaper does not auto-post responses. It delivers approval-ready review response drafts and complaint insights. Customers remain in control.

## Remaining high-value next builds
1. Generate polished mini-audit report pages from saved data.
2. Add SendGrid notifications to James/admin when mini-audit or onboarding is submitted.
3. Add customer confirmation emails.
4. Add one-click follow-up sequence for no-reply leads.
5. Add domain + branded email/domain authentication.

## Mini-audit report engine
- `/mini-audit/report?id=<id>` renders a customer-facing mini-audit report.
- New `/api/mini-audit` requests now also create a `mini_audits` queue record and return `mini_audit_id`.
- Reports show verified bad-review examples, complaint themes, response drafts, recommendation, and CTA to monthly monitoring.

## Transactional notification layer
- Mini-audit requests send customer confirmation and admin notification when SendGrid is configured.
- Onboarding submissions send customer confirmation and admin notification when SendGrid is configured.
- QA/example recipients are skipped to avoid accidental test sends.

## Fulfillment tooling
- `ops/create_mini_audit_from_target.py "Business Name"` builds a mini-audit payload from verified target evidence.
- Add `--save` to save it through `/api/admin/mini-audit/save` and receive a customer-facing report URL.
- Admin can mark a mini-audit sent through `/api/admin/mini-audit/mark-sent`, which sends the report email and updates status.
- `/admin/ops` shows report URLs for saved mini-audits.

## Follow-up system
- `ops/generate_followups.py` creates follow-up drafts from `ops/sent-log.csv`.
- It sends nothing. It separates due-now follow-ups from upcoming follow-ups.
- Current first-batch follow-ups are due 2026-05-11 if no reply.

## Pre-domain readiness phases
1. Funnel spine — homepage and mini-audit route capture interest before payment.
2. Audit production — use verified evidence and `ops/create_mini_audit_from_target.py` to create reports.
3. Admin operations — `/admin/ops` handles queues, report links, report sending/mark-sent, onboarding status, and reply status.
4. Follow-up — `ops/generate_followups.py` creates due/upcoming follow-up drafts without sending.
5. Final handoff — domain + authenticated email domain remains the owner-supplied phase before scaling.

## Sample audit library
- Internal examples live in `ops/sample-audits/`.
- Current samples: dental pricing transparency, dental staff/front-desk tone, auto repair quote/communication complaints.
- Use these as style references for manual fulfillment; do not send them without current approval.

## Latest local end-to-end rehearsal
Passed locally on port 3012:
- public mini-audit request saved
- admin-created report saved
- report rendered
- mark-sent path exercised with QA-safe skipped email
- onboarding submission saved
- onboarding moved to `in_progress`
- inbound reply logged
- reply moved to `approved`
- `/admin/ops` rendered action buttons
- QA records cleaned afterward

## Security hardening before traffic
- Admin data APIs now require the admin password as query auth for GET requests:
  - `/api/stats`
  - `/api/businesses`
  - `/api/drafts`
  - `/api/audit-requests`
- Admin dashboard/drafts JS appends the stored admin password for GET requests.
- Public routes remain public: homepage, `/mini-audit`, report links, onboarding, pricing, checkout.

## Customer fulfillment docs
- `ops/CUSTOMER_FULFILLMENT_PLAYBOOK.md` defines the manual MVP operating process.
- `ops/FIRST_RESPONSE_PACK_TEMPLATE.md` is the paid customer deliverable template.
- `ops/PRE_DOMAIN_READINESS.md` separates completed pre-domain work from James's final domain/email phase.
