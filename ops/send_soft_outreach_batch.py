#!/usr/bin/env python3
"""Send soft Review Reaper mini-audit outreach from ops/email-ready-15-*.csv.

Safety gates:
  1) --send is required
  2) REVIEW_REAPER_OUTREACH_APPROVED=yes is required

This script sends the softer mini-audit ask, not the older review-card email.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = ROOT / "ops" / "email-ready-15-2026-05-06.csv"
SENT_LOG = ROOT / "ops" / "sent-log.csv"
TARGETS = ROOT / "ops" / "targets.csv"
LOCK_FILE = ROOT / "ops" / ".send-soft-outreach.lock"


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def load_admin_password() -> str:
    value = os.getenv("REVIEW_REAPER_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    if value:
        return value
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def post_json(url: str, payload: dict) -> tuple[int, str]:
    data = json.dumps(payload).encode()
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()


def send(row: dict, base_url: str, password: str) -> tuple[bool, str, int | None]:
    payload = {
        "password": password,
        "recipient_email": row["email"],
        "business_name": row["business_name"],
        "pain_angle": row["pain_angle"],
    }
    status, body = post_json(base_url.rstrip("/") + "/api/send-soft-outreach", payload)
    return 200 <= status < 300, body[:500], status


def load_sent_rows() -> list[dict]:
    if not SENT_LOG.exists() or SENT_LOG.stat().st_size == 0:
        return []
    return list(csv.DictReader(SENT_LOG.open()))


def sent_index(rows: list[dict]) -> tuple[set[str], set[str]]:
    names = {r.get("business_name", "").strip().lower() for r in rows if r.get("business_name")}
    emails = {r.get("email_or_contact", "").strip().lower() for r in rows if r.get("email_or_contact")}
    return names, emails


def sent_today_count(rows: list[dict], today: str) -> int:
    return sum(1 for r in rows if r.get("date", "").startswith(today))


def append_sent(row: dict, status_code: int | None, note: str) -> None:
    sent_at = datetime.now()
    followup_due = sent_at + timedelta(days=5)
    exists = SENT_LOG.exists() and SENT_LOG.stat().st_size > 0
    with SENT_LOG.open("a", newline="") as f:
        fields = ["date", "business_name", "email_or_contact", "subject", "status", "followup_due", "notes"]
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({
            "date": sent_at.isoformat(timespec="seconds"),
            "business_name": row["business_name"],
            "email_or_contact": row["email"],
            "subject": f"Quick review mini-audit for {row['business_name']}",
            "status": "sent",
            "followup_due": followup_due.date().isoformat(),
            "notes": f"Soft mini-audit outreach. {note}. Status code: {status_code or 'n/a'}",
        })


def mark_target_sent(sent_rows: list[dict]) -> None:
    if not TARGETS.exists():
        return
    targets = list(csv.DictReader(TARGETS.open()))
    if not targets:
        return
    sent_by_name = {r["business_name"]: r for r in sent_rows}
    today = datetime.now().date().isoformat()
    followup = (datetime.now() + timedelta(days=5)).date().isoformat()
    for row in targets:
        if row["business_name"] in sent_by_name:
            email = sent_by_name[row["business_name"]]["email"]
            row["status"] = f"sent_{today}_followup_{followup}"
            marker = f"SENT {today} via SendGrid soft outreach to {email}; follow up {followup} if no reply."
            if marker not in row.get("notes", ""):
                row["notes"] = (row.get("notes", "") + " | " + marker).strip(" |")
    with TARGETS.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=targets[0].keys())
        writer.writeheader()
        writer.writerows(targets)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", default=str(DEFAULT_BATCH))
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--daily-cap", type=int, default=int(os.getenv("REVIEW_REAPER_DAILY_CAP", "80")))
    parser.add_argument("--base-url", default=os.getenv("REVIEW_REAPER_BASE_URL", "https://www.reviewreaper.co"))
    args = parser.parse_args()

    rows = list(csv.DictReader(Path(args.batch).open()))[: args.limit]
    rows = [r for r in rows if r.get("status") == "ready_for_soft_mini_audit_outreach_not_sent"]

    if not args.send:
        for row in rows:
            print(f"DRY RUN: {row['business_name']} -> {row['email']}")
        print(f"Dry run only. {len(rows)} email(s) prepared; no emails sent.", file=sys.stderr)
        return 0

    if os.getenv("REVIEW_REAPER_OUTREACH_APPROVED") != "yes":
        print("Refusing to send: set REVIEW_REAPER_OUTREACH_APPROVED=yes after James approves the batch.", file=sys.stderr)
        return 2

    password = load_admin_password()
    if not password:
        print("Missing admin password.", file=sys.stderr)
        return 2

    sent_rows: list[dict] = []
    skipped = 0
    failures = 0
    today = datetime.now().date().isoformat()
    with LOCK_FILE.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for row in rows:
            # Reload before every send so overlapping waves cannot exceed
            # the daily cap or send duplicate names/emails.
            existing = load_sent_rows()
            existing_names, existing_emails = sent_index(existing)
            already_today = sent_today_count(existing, today)
            business_key = row["business_name"].strip().lower()
            email_key = row["email"].strip().lower()

            if args.daily_cap > 0 and already_today >= args.daily_cap:
                print(f"Daily cap reached ({already_today}/{args.daily_cap}); stopping before {row['business_name']}.")
                break
            if business_key in existing_names or email_key in existing_emails:
                print(f"SKIP duplicate already sent: {row['business_name']} -> {row['email']}")
                skipped += 1
                continue

            ok, note, status_code = send(row, args.base_url, password)
            print(f"{row['business_name']} -> {row['email']} :: {note}")
            if ok:
                append_sent(row, status_code, note)
                sent_rows.append(row)
            else:
                failures += 1

        mark_target_sent(sent_rows)
    print(f"Sent {len(sent_rows)} / {len(rows)}. Skipped: {skipped}. Failures: {failures}.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
