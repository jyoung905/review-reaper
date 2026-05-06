# Review Reaper Pre-Domain Readiness

## Status
Operational enough for manual/warm traffic. Not ready for high-volume cold outbound until domain and email authentication are set.

## Completed before domain
- Mini-audit-first public funnel.
- Stripe subscription path.
- Onboarding path after checkout.
- Admin ops desk.
- Mini-audit report creation, report pages, and report-send workflow.
- Internal sample audit library.
- Follow-up draft generator.
- Reply event logging and status workflow.
- Onboarding status workflow.
- Admin data API protection.
- QA-safe test cleanup endpoint.
- First response pack template and fulfillment playbook.

## Remaining final phase for James
James provides:
1. Domain.
2. Sending email/mailbox.
3. DNS access or records for SPF, DKIM, DMARC.
4. Preferred public sender identity.

## After domain/email handoff
- Set production `BASE_URL` to the domain.
- Configure SendGrid authenticated sender/domain.
- Verify SPF/DKIM/DMARC.
- Update outreach CTA URLs to domain.
- Send one mailbox-to-mailbox test.
- Run one real mini-audit delivery to James-controlled address.
- Resume low-volume approved outreach only.

## Scale gate
Do not scale beyond 5–10/day until:
- reply handling has been exercised on real replies,
- at least one prospect has viewed a mini-audit,
- one paid onboarding has been rehearsed or completed,
- deliverability is healthy.
