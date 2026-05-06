#!/usr/bin/env python3
"""Prepare or send Review Reaper outreach batches.

Default mode is safe: it prints the JSON payloads that would be sent.
External sending requires BOTH:
  1) --send
  2) environment variable REVIEW_REAPER_OUTREACH_APPROVED=yes

By default, this only includes rows with status=send_ready_needs_approval.
This keeps accidental cold outreach from happening during agent work.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "ops" / "targets.csv"
SENT_LOG = ROOT / "ops" / "sent-log.csv"


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


def direct_email(contact: str) -> str:
    first = contact.split(";", 1)[0].strip()
    return first if "@" in first and " " not in first else ""


def split_examples(raw: str) -> list[str]:
    # Verified rows use pipe-separated exact snippets. Older rows used semicolons.
    if "|" in raw:
        parts = raw.split("|")
    else:
        parts = raw.split(";")
    out = []
    for p in parts:
        p = p.strip().strip('"').strip()
        if p and not p.lower().startswith("low-star themes to screenshot"):
            out.append(p)
    return out[:3]


def themes_for(weakness: str) -> list[str]:
    w = weakness.lower()
    themes = []
    if any(x in w for x in ["pricing", "quote", "billing", "refund", "upsell"]):
        themes.append("pricing_transparency")
    if any(x in w for x in ["staff", "front desk", "rude", "customer service"]):
        themes.append("customer_service")
    if any(x in w for x in ["communication", "appointment", "booking", "scheduling"]):
        themes.append("communication")
    if any(x in w for x in ["result", "treatment", "repair", "service"]):
        themes.append("service_quality")
    return themes or ["customer_experience"]


def response_for(business_name: str, weakness: str, example: str) -> str:
    w = weakness.lower()
    if "auto" in business_name.lower() or "repair" in business_name.lower() or "quote" in w:
        return (
            "Thank you for sharing this. We are sorry the pricing and repair communication did not feel clear. "
            "Customers should understand the estimate, the work recommended, and the reason for any changes before moving forward. "
            "Please contact our manager so we can review your visit privately and address what happened."
        )
    if "dental" in business_name.lower() or "upsell" in w or "oda" in example.lower():
        return (
            "Thank you for taking the time to share this. We are sorry the treatment recommendation and fees did not feel clear. "
            "Patients should feel informed before making decisions about care. Please contact our office manager so we can review the visit details, "
            "answer questions about the estimate, and make sure your concerns are handled properly."
        )
    return (
        "Thank you for sharing this feedback. We are sorry the experience did not meet expectations. "
        "Please contact our manager directly so we can understand what happened and work toward a resolution."
    )


def recovery_offer_for(weakness: str) -> str:
    w = weakness.lower()
    if any(x in w for x in ["pricing", "quote", "billing", "upsell"]):
        return "Offer a manager callback and a written estimate/billing review before any future work."
    if any(x in w for x in ["staff", "front desk", "rude"]):
        return "Offer a manager callback and a clear escalation path for the customer's concern."
    return "Offer a manager callback and a concrete next step to resolve the complaint."


def reviews_for(row: dict) -> list[dict]:
    examples = split_examples(row.get("bad_review_examples", ""))
    themes = themes_for(row.get("weakness", ""))
    offer = recovery_offer_for(row.get("weakness", ""))
    reviews = []
    for example in examples:
        reviews.append({
            "reviewer_name": "Public reviewer",
            "rating": 2,
            "text": example,
            "complaint_themes": themes,
            "ai_generated_text": response_for(row["business_name"], row.get("weakness", ""), example),
            "recovery_offer": offer,
        })
    return reviews


def payload_for(row: dict, password: str) -> dict | None:
    email = direct_email(row.get("email_or_contact", ""))
    if not email:
        return None
    reviews = reviews_for(row)
    if not reviews:
        return None
    return {
        "password": password,
        "recipient_email": email,
        "business_name": row["business_name"],
        "reviews": reviews,
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
    parser.add_argument("--include-unverified", action="store_true", help="Include all direct-email rows, including screenshot-needed rows. Not recommended.")
    args = parser.parse_args()

    all_rows = list(csv.DictReader(TARGETS.open()))
    if args.include_unverified:
        rows = all_rows
    else:
        rows = [r for r in all_rows if r.get("status") == "send_ready_needs_approval"]
    rows = rows[: args.limit]

    password = load_env_password()
    payloads = [(r, payload_for(r, password)) for r in rows]
    payloads = [(r, p) for r, p in payloads if p]

    if not args.send:
        print(json.dumps([p for _, p in payloads], indent=2))
        print(f"\nDry run only. {len(payloads)} send-ready direct-email payload(s) prepared; no emails sent.", file=sys.stderr)
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
