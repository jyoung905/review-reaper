# Review Reaper Onboarding and Fulfillment

## Problem with current app
Current post-payment flow sends the customer to `/subscribe/success` and then points them at the admin dashboard. That is not a real customer onboarding flow.

Do not scale outbound until this is fixed.

## Required onboarding fields
After payment or before payment, collect:
- Business name
- Business location/city
- Website
- Google Business Profile / review profile URL
- Contact person name
- Contact email
- Preferred response tone: warm/professional/direct/apologetic
- Approval recipient email
- Any topics to avoid admitting liability on

## Manual MVP onboarding flow
Until the app is built:
1. Prospect requests mini-audit.
2. We create/send mini-audit manually.
3. If they want monthly service, send Stripe link.
4. After payment, send onboarding email/form.
5. Create customer folder/record.
6. Run first review scan.
7. Send first response pack.

## Fulfillment checklist for each paid customer
- [ ] Save customer details
- [ ] Save review profile URL
- [ ] Capture baseline rating/review count
- [ ] Identify negative reviews
- [ ] Draft responses
- [ ] Draft recovery offers where relevant
- [ ] Summarize complaint themes
- [ ] Send response pack for approval
- [ ] Log sent date
- [ ] Schedule next monthly scan

## Customer promise
Do not promise automatic posting yet.
Promise:
> We send approval-ready response drafts and reputation insights. You stay in control of what gets posted.

## Next product tasks
1. Replace `/subscribe/success` with onboarding form or instructions.
2. Add `/onboarding` route.
3. Store onboarding submissions.
4. Send admin notification on new subscriber/onboarding.
5. Send customer confirmation email.
6. Build mini-audit report template.
