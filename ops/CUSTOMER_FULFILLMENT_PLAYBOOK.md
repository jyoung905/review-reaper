# Review Reaper Customer Fulfillment Playbook

## Service promise
Review Reaper gives customers approval-ready reputation work. It does not auto-post, impersonate the customer, fake reviews, or admit liability.

## Fulfillment stages

### 1. Mini-audit lead
Trigger: `/mini-audit` submission or manually verified prospect.

Operator checklist:
- Verify business name, website, review profile, and contact email.
- Capture 2–3 real low-star review examples.
- Identify 1–3 recurring complaint themes.
- Generate response drafts with `ops/create_mini_audit_from_target.py` or manually through the same structure.
- Save via `/api/admin/mini-audit/save`.
- Review the public report URL.
- Only then email/mark sent from `/admin/ops`.

### 2. Subscription conversion
Trigger: customer clicks report CTA and pays through Stripe.

Operator checklist:
- Confirm Stripe checkout/webhook created or updated the customer record.
- Confirm `/subscribe/success` points them to onboarding.
- Watch `/admin/ops` for onboarding submission.

### 3. Onboarding
Trigger: `/onboarding` submission.

Operator checklist:
- Move status from `new` → `in_progress`.
- Confirm approval email, tone, liability notes, review profile URL.
- If data is missing, draft a clarification email; do not guess.
- Prepare first response pack.

### 4. First response pack
Deliverable: 5–10 approval-ready response drafts for unresolved 1–3 star reviews.

Each draft should include:
- review snippet
- complaint theme
- recommended public response
- optional private recovery note
- risk note if the review involves liability, medical/dental treatment, discrimination, refund disputes, or legal threats

### 5. Monthly service loop
- Check reviews weekly or monthly depending on plan/manual capacity.
- Draft responses for new negative reviews.
- Summarize recurring complaint themes.
- Send pack for approval.
- Mark approved/sent/closed internally.

## Response rules
- Calm, concise, non-defensive.
- Acknowledge the experience without admitting fault.
- Invite private follow-up.
- Never mention protected health/personal information.
- Never argue facts publicly.
- Never promise refunds, outcomes, legal remedies, or compensation unless the customer approved that language.

## Escalation rules
Flag for human/customer review before drafting if a review mentions:
- injury, medical/dental harm, malpractice, discrimination, harassment
- legal threats, chargebacks, police, regulators
- explicit personal data
- employee names in a sensitive context
- allegations that require investigation

## Domain/email handoff phase
Before scaling outreach, James should provide:
- domain for Review Reaper
- sending mailbox/domain
- SPF/DKIM/DMARC access or DNS access
- preferred public sender name

Until then, keep outbound manual and low volume.
