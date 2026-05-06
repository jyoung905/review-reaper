#!/usr/bin/env python3
"""Create a Review Reaper mini-audit payload from ops/targets.csv.

Safe by default: prints JSON only. Use --save to save through the admin API.
Does not email the prospect. Email sending is a separate explicit admin action.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "ops" / "targets.csv"


def load_password() -> str:
    if os.getenv("REVIEW_REAPER_ADMIN_PASSWORD"):
        return os.getenv("REVIEW_REAPER_ADMIN_PASSWORD", "")
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip()
    return ""


def direct_email(contact: str) -> str:
    first = contact.split(";", 1)[0].strip()
    return first if "@" in first and " " not in first else ""


def split_examples(raw: str) -> list[str]:
    sep = "|" if "|" in raw else ";"
    out = []
    for p in raw.split(sep):
        p = p.strip().strip('"').strip()
        if p and not p.lower().startswith("low-star themes"):
            out.append(p)
    return out[:3]


def themes_from_weakness(weakness: str) -> list[str]:
    w = weakness.lower()
    themes = []
    if any(x in w for x in ["price", "quote", "billing", "fee", "upsell", "refund"]):
        themes.append("Pricing / billing transparency")
    if any(x in w for x in ["staff", "front desk", "rude", "customer service"]):
        themes.append("Customer service tone")
    if any(x in w for x in ["communication", "appointment", "booking", "scheduling"]):
        themes.append("Communication and follow-up")
    if any(x in w for x in ["repair", "treatment", "service", "result"]):
        themes.append("Service quality confidence")
    return themes or ["General customer confidence"]


def draft_response(business: str, weakness: str, example: str) -> str:
    w = weakness.lower()
    if any(x in w or x in example.lower() for x in ["rude", "staff", "front desk", "customer service"]):
        return (
            "Thank you for bringing this to our attention. We are sorry the interaction with our team did not feel respectful or helpful. "
            "That is not the impression we want patients or customers to leave with. Please contact our manager so we can review what happened and address it with the team."
        )
    if "dental" in business.lower() or "upsell" in w or "oda" in example.lower():
        return (
            "Thank you for sharing this. We are sorry the treatment recommendation and fees did not feel clear. "
            "Patients should feel informed before making decisions about care. Please contact our office manager so we can review the visit details, "
            "answer questions about the estimate, and make sure your concerns are handled properly."
        )
    if "auto" in business.lower() or "repair" in business.lower() or "quote" in w:
        return (
            "Thank you for taking the time to leave this feedback. We are sorry the estimate and repair communication did not feel clear. "
            "Customers should understand what work is recommended and why before making a decision. Please contact our manager so we can review the visit and address your concern directly."
        )
    return (
        "Thank you for sharing this feedback. We are sorry the experience did not meet expectations. "
        "Please contact our manager directly so we can understand what happened and work toward a resolution."
    )


def build_payload(row: dict) -> dict:
    examples = split_examples(row.get("bad_review_examples", ""))
    drafts = [draft_response(row["business_name"], row.get("weakness", ""), ex) for ex in examples]
    return {
        "prospect_email": direct_email(row.get("email_or_contact", "")) or "unknown@example.com",
        "business_name": row["business_name"],
        "website": row.get("website", ""),
        "review_profile_url": row.get("notes", ""),
        "public_rating": row.get("rating", ""),
        "review_count": row.get("review_count", ""),
        "bad_review_examples": examples,
        "complaint_themes": themes_from_weakness(row.get("weakness", "")),
        "response_drafts": drafts,
        "recommendation": (
            "Start by responding to the most specific negative reviews with calm, non-defensive replies. "
            "Then monitor new 1–3 star reviews monthly so recurring issues do not sit unanswered. "
            "Avoid admitting fault; acknowledge the experience, invite private follow-up, and show future customers the business is responsive."
        ),
        "status": "draft",
    }


def post_json(url: str, payload: dict):
    data = json.dumps(payload).encode()
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("business_name")
    parser.add_argument("--base-url", default=os.getenv("REVIEW_REAPER_BASE_URL", "https://review-reaper-production.up.railway.app"))
    parser.add_argument("--save", action="store_true", help="Save via admin API")
    args = parser.parse_args()

    rows = list(csv.DictReader(TARGETS.open()))
    row = next((r for r in rows if r["business_name"].lower() == args.business_name.lower()), None)
    if not row:
        raise SystemExit(f"Business not found: {args.business_name}")
    payload = build_payload(row)
    if not args.save:
        print(json.dumps(payload, indent=2))
        return 0
    payload["password"] = load_password()
    status, body = post_json(args.base_url.rstrip("/") + "/api/admin/mini-audit/save", payload)
    print(status, body)
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
