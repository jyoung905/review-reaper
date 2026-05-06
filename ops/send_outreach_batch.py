#!/usr/bin/env python3
"""Prepare or send Review Reaper outreach batches.

Default mode is safe: it prints the JSON payloads that would be sent.
External sending requires BOTH:
  1) --send
  2) environment variable REVIEW_REAPER_OUTREACH_APPROVED=yes

This keeps accidental cold outreach from happening during agent work.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "ops" / "targets.csv"
SENT_LOG = ROOT / "ops" / "sent-log.csv"

SAMPLE_REVIEWS = {
    "pricing": [
        {
            "reviewer_name": "Public reviewer",
            "rating": 2,
            "text": "I felt the quoted treatment and final price were not explained clearly.",
            "complaint_themes": ["pricing_transparency", "trust"],
            "ai_generated_text": "Thank you for sharing this. We are sorry the cost and treatment options did not feel clearly explained. That is not the experience we want patients to have. Please contact our office manager so we can review the visit details, answer questions about the estimate, and make sure you feel heard.",
            "recovery_offer": "Offer a direct office-manager callback and a no-charge estimate review before any future treatment.",
        },
        {
            "reviewer_name": "Public reviewer",
            "rating": 1,
            "text": "They added things after the procedure and I was surprised by the bill.",
            "complaint_themes": ["billing_surprise", "communication"],
            "ai_generated_text": "We are sorry for the frustration around your billing experience. Patients should understand recommended treatment and expected costs before moving forward. Please reach out to us directly so we can review what happened and discuss next steps.",
            "recovery_offer": "Offer a private billing review and written treatment estimate for their next appointment.",
        },
    ],
    "staff": [
        {
            "reviewer_name": "Public reviewer",
            "rating": 2,
            "text": "The front desk was rude and I did not feel welcomed.",
            "complaint_themes": ["front_desk", "customer_service"],
            "ai_generated_text": "We are sorry your interaction with our team felt unwelcoming. That is not the standard we expect. Please contact the clinic manager directly so we can understand what happened and address it with the team.",
            "recovery_offer": "Offer a manager callback and priority scheduling if the patient wants to return.",
        },
        {
            "reviewer_name": "Public reviewer",
            "rating": 1,
            "text": "The dentist was rude and inappropriate.",
            "complaint_themes": ["professionalism", "bedside_manner"],
            "ai_generated_text": "We are concerned to read this and are sorry the visit left you feeling this way. We take professionalism seriously and would appreciate the chance to review the situation privately with you. Please contact our manager so we can follow up properly.",
            "recovery_offer": "Offer private follow-up with the manager and, if appropriate, a different provider for future care.",
        },
    ],
    "default": [
        {
            "reviewer_name": "Public reviewer",
            "rating": 2,
            "text": "The experience was disappointing and no one followed up.",
            "complaint_themes": ["customer_experience", "follow_up"],
            "ai_generated_text": "We are sorry your experience was disappointing and that follow-up was lacking. Please contact our manager directly so we can understand what happened and work toward a resolution.",
            "recovery_offer": "Offer a manager callback and a clear resolution path.",
        }
    ],
}


def load_env_password() -> str:
    value = os.getenv("REVIEW_REAPER_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    if value:
        return value
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip()
    return ""


def select_reviews(weakness: str):
    w = weakness.lower()
    if "pricing" in w or "upsell" in w or "billing" in w:
        return SAMPLE_REVIEWS["pricing"]
    if "staff" in w or "front desk" in w or "rude" in w:
        return SAMPLE_REVIEWS["staff"]
    return SAMPLE_REVIEWS["default"]


def direct_email(contact: str) -> str:
    first = contact.split(";", 1)[0].strip()
    return first if "@" in first and " " not in first else ""


def payload_for(row: dict, password: str) -> dict | None:
    email = direct_email(row.get("email_or_contact", ""))
    if not email:
        return None
    return {
        "password": password,
        "recipient_email": email,
        "business_name": row["business_name"],
        "reviews": select_reviews(row.get("weakness", "")),
    }


def post_json(url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode()
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()


def append_sent(row: dict, response_text: str):
    exists = SENT_LOG.exists() and SENT_LOG.stat().st_size > 0
    with SENT_LOG.open("a", newline="") as f:
        fields = ["date", "business_name", "recipient", "status", "response"]
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "date": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "business_name": row["business_name"],
            "recipient": direct_email(row.get("email_or_contact", "")),
            "status": "sent",
            "response": response_text[:500],
        })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("REVIEW_REAPER_BASE_URL", "https://review-reaper-production.up.railway.app"))
    parser.add_argument("--send", action="store_true", help="Actually send via production API. Requires REVIEW_REAPER_OUTREACH_APPROVED=yes")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    rows = list(csv.DictReader(TARGETS.open()))[: args.limit]
    password = load_env_password()
    payloads = [(r, payload_for(r, password)) for r in rows]
    payloads = [(r, p) for r, p in payloads if p]

    if not args.send:
        print(json.dumps([p for _, p in payloads], indent=2))
        print(f"\nDry run only. {len(payloads)} sendable direct-email payload(s) prepared; no emails sent.", file=sys.stderr)
        return 0

    if os.getenv("REVIEW_REAPER_OUTREACH_APPROVED") != "yes":
        print("Refusing to send: set REVIEW_REAPER_OUTREACH_APPROVED=yes after James approves the batch.", file=sys.stderr)
        return 2
    if not password:
        print("Missing admin password.", file=sys.stderr)
        return 2

    endpoint = args.base_url.rstrip("/") + "/api/send-outreach"
    for row, payload in payloads:
        status, body = post_json(endpoint, payload)
        print(row["business_name"], status, body[:300])
        if 200 <= status < 300:
            append_sent(row, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
