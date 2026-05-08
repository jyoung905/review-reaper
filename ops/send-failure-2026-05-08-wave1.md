# Review Reaper outreach pause — 2026-05-08 wave 1

Batch: `ops/email-ready-20-2026-05-08-wave1.csv`

Outcome:
- First 10 sends accepted by production endpoint / SendGrid (`status_code: 202`).
- Next 10 attempts returned `SendGrid error: HTTP Error 403: Forbidden` from production endpoint.
- Per deliverability guardrails, outbound was paused immediately. Waves 2-4 were not sent.

Accepted recipients:
1. Artin Dental Clinic downtown Toronto — info@artindental.com
2. MJ Dental — info@mjdental.com
3. Broadway Dental — info@broadwaydentalclinic.com
4. Cornerstone Physiotherapy — info@cornerstonephysio.com
5. Physiotherapy Toronto — info@rebuildphysiotherapy.com
6. Alpha Health Services — info@alphahealthservices.ca
7. Peak Physio & Sports Rehab — info@peakphysiorehab.com
8. Kinective Health & Performance — info@kinectivehealth.com
9. Thesmilecentre — info@thesmilecentre.com
10. Health First Group — info@healthfirstgroup.ca

Rejected attempts:
- Modern Movement — info@m2modernmovement.ca
- Rishaanphysio — info@rishaanphysio.com
- Physiotherapy Clinic Mississauga — info@deltaphysiotherapy.ca
- Arc Physio Health — info@arcphysiohealth.ca
- Mississauga Auto Repairs — service@mississaugaautorepairs.com
- Maple Vaughan Dental — info@maplevaughandental.com
- Onyx Dentistry — info@onyxdentistry.ca
- crystalline Dental — info@crystallinedental.com
- Nest Dental Clinic — info@nestdentalclinic.ca
- Marketplace Dentistry — info@marketplacedentistry.ca

Next action: inspect SendGrid/account/domain/API-key status before resuming outbound.
