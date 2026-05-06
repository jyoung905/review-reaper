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
