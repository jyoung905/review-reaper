"""
Review Reaper - SQLite Database Layer
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "reviewreaper.db"


def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            place_id TEXT UNIQUE NOT NULL,
            address TEXT,
            phone TEXT,
            website TEXT,
            business_type TEXT DEFAULT 'general',
            rating REAL,
            total_reviews INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            reviewer_name TEXT,
            rating INTEGER NOT NULL,
            text TEXT,
            date_posted TEXT,
            response_status TEXT DEFAULT 'pending',
                -- pending, responded, skipped
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS response_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL UNIQUE,
            business_id INTEGER NOT NULL,
            ai_generated_text TEXT NOT NULL,
            recovery_offer TEXT,
            sentiment_label TEXT,
            complaint_themes TEXT,  -- JSON array
            status TEXT DEFAULT 'pending',
                -- pending, approved, rejected, sent
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (review_id) REFERENCES reviews(id),
            FOREIGN KEY (business_id) REFERENCES businesses(id)
        );

        CREATE TABLE IF NOT EXISTS audit_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT,
            place_id TEXT,
            email TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            business_name TEXT,
            contact_name TEXT,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            status TEXT DEFAULT 'lead',
                -- lead, subscribed, onboarding_submitted, active, paused, canceled
            source TEXT DEFAULT 'unknown',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS onboarding_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_email TEXT NOT NULL,
            business_name TEXT NOT NULL,
            contact_name TEXT,
            website TEXT,
            city TEXT,
            review_profile_url TEXT,
            place_id TEXT,
            approval_email TEXT,
            preferred_tone TEXT,
            liability_notes TEXT,
            service_notes TEXT,
            status TEXT DEFAULT 'new',
                -- new, setup_started, first_scan_ready, active
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS mini_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_email TEXT NOT NULL,
            business_name TEXT NOT NULL,
            website TEXT,
            review_profile_url TEXT,
            public_rating TEXT,
            review_count TEXT,
            bad_review_examples TEXT,
            complaint_themes TEXT,
            response_drafts TEXT,
            recommendation TEXT,
            status TEXT DEFAULT 'draft',
                -- draft, sent, won, lost
            created_at TEXT DEFAULT (datetime('now')),
            sent_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reply_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT,
            contact_email TEXT,
            inbound_text TEXT,
            classification TEXT,
            recommended_reply TEXT,
            status TEXT DEFAULT 'draft',
                -- draft, approved, sent, closed
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized at {DB_PATH}")


# ─── Business CRUD ────────────────────────────────────────────────────────

def add_business(name, place_id, address=None, phone=None, website=None,
                 business_type="general", rating=None, total_reviews=0):
    """Add a new business or update existing by place_id."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO businesses (name, place_id, address, phone, website,
                                    business_type, rating, total_reviews)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(place_id) DO UPDATE SET
                name=excluded.name,
                address=excluded.address,
                phone=excluded.phone,
                website=excluded.website,
                business_type=excluded.business_type,
                rating=excluded.rating,
                total_reviews=excluded.total_reviews,
                updated_at=datetime('now')
        """, (name, place_id, address, phone, website, business_type, rating, total_reviews))
        conn.commit()
        row = conn.execute("SELECT id FROM businesses WHERE place_id=?", (place_id,)).fetchone()
        return row["id"]
    finally:
        conn.close()


def get_business(business_id):
    """Get business by ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_business_by_place_id(place_id):
    """Get business by Place ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM businesses WHERE place_id=?", (place_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_businesses():
    """List all tracked businesses with review counts."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT b.*,
                   COUNT(r.id) as negative_count,
                   SUM(CASE WHEN rd.status = 'pending' THEN 1 ELSE 0 END) as pending_responses
            FROM businesses b
            LEFT JOIN reviews r ON r.business_id = b.id
            LEFT JOIN response_drafts rd ON rd.review_id = r.id
            GROUP BY b.id
            ORDER BY b.name
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Reviews CRUD ─────────────────────────────────────────────────────────

def add_reviews(business_id, reviews_list):
    """Batch insert reviews for a business. Returns count inserted."""
    conn = get_connection()
    count = 0
    try:
        for r in reviews_list:
            try:
                # Check if this review already exists
                existing = conn.execute(
                    "SELECT id FROM reviews WHERE business_id=? AND reviewer_name=? AND rating=? AND text=?",
                    (business_id, r.get("reviewer_name", ""), r.get("rating", 0),
                     r.get("text", ""))
                ).fetchone()
                if not existing:
                    conn.execute("""
                        INSERT INTO reviews
                            (business_id, reviewer_name, rating, text, date_posted, response_status)
                        VALUES (?, ?, ?, ?, ?, 'pending')
                    """, (business_id, r.get("reviewer_name"), r.get("rating"),
                          r.get("text"), r.get("date_posted")))
                    count += 1
            except Exception as e:
                print(f"      ⚠️  Error adding review: {e}")
        conn.commit()
        return count
    finally:
        conn.close()


def get_negative_reviews(business_id, min_rating=1, max_rating=3):
    """Get negative reviews (rating ≤ 3) for a business."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT r.*, rd.id as draft_id, rd.status as draft_status,
                   rd.ai_generated_text, rd.recovery_offer, rd.complaint_themes
            FROM reviews r
            LEFT JOIN response_drafts rd ON rd.review_id = r.id
            WHERE r.business_id = ? AND r.rating BETWEEN ? AND ?
            ORDER BY r.rating ASC, r.date_posted DESC
        """, (business_id, min_rating, max_rating)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_review(review_id):
    """Get a single review by ID."""
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT r.*, b.name as business_name, b.business_type
            FROM reviews r
            JOIN businesses b ON b.id = r.business_id
            WHERE r.id=?
        """, (review_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─── Response Drafts CRUD ─────────────────────────────────────────────────

def save_response_draft(review_id, business_id, text, recovery_offer=None,
                        sentiment_label=None, complaint_themes=None):
    """Save or update a response draft for a review."""
    themes_json = json.dumps(complaint_themes) if complaint_themes else "[]"
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO response_drafts
                (review_id, business_id, ai_generated_text, recovery_offer,
                 sentiment_label, complaint_themes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(review_id) DO UPDATE SET
                ai_generated_text=excluded.ai_generated_text,
                recovery_offer=excluded.recovery_offer,
                sentiment_label=excluded.sentiment_label,
                complaint_themes=excluded.complaint_themes,
                status='pending'
        """, (review_id, business_id, text, recovery_offer, sentiment_label, themes_json))
        conn.commit()
        row = conn.execute(
            "SELECT id FROM response_drafts WHERE review_id=?", (review_id,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def update_draft_status(draft_id, status):
    """Update the status of a response draft (approve/reject/sent)."""
    conn = get_connection()
    try:
        conn.execute("UPDATE response_drafts SET status=? WHERE id=?",
                     (status, draft_id))
        conn.commit()
        return True
    finally:
        conn.close()


def get_drafts_by_status(status=None):
    """Get all drafts, optionally filtered by status, with business info."""
    conn = get_connection()
    try:
        where = "WHERE rd.status=?" if status else ""
        rows = conn.execute(f"""
            SELECT rd.*, r.reviewer_name, r.rating, r.text as review_text,
                   b.name as business_name, b.business_type
            FROM response_drafts rd
            JOIN reviews r ON r.id = rd.review_id
            JOIN businesses b ON b.id = rd.business_id
            {where}
            ORDER BY rd.created_at DESC
        """, (status,) if status else ()).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Stats ─────────────────────────────────────────────────────────────────

def get_stats():
    """Get overall stats for the admin dashboard."""
    conn = get_connection()
    try:
        stats = {
            "total_businesses": conn.execute(
                "SELECT COUNT(*) FROM businesses").fetchone()[0],
            "total_reviews": conn.execute(
                "SELECT COUNT(*) FROM reviews").fetchone()[0],
            "negative_reviews": conn.execute(
                "SELECT COUNT(*) FROM reviews WHERE rating <= 3").fetchone()[0],
            "pending_drafts": conn.execute(
                "SELECT COUNT(*) FROM response_drafts WHERE status='pending'"
            ).fetchone()[0],
            "approved_drafts": conn.execute(
                "SELECT COUNT(*) FROM response_drafts WHERE status='approved'"
            ).fetchone()[0],
            "sent_drafts": conn.execute(
                "SELECT COUNT(*) FROM response_drafts WHERE status='sent'"
            ).fetchone()[0],
            "pending_audits": conn.execute(
                "SELECT COUNT(*) FROM audit_requests WHERE status='pending'"
            ).fetchone()[0],
            "customers": conn.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0],
            "new_onboarding": conn.execute(
                "SELECT COUNT(*) FROM onboarding_submissions WHERE status='new'"
            ).fetchone()[0],
            "mini_audits": conn.execute(
                "SELECT COUNT(*) FROM mini_audits"
            ).fetchone()[0],
            "reply_drafts": conn.execute(
                "SELECT COUNT(*) FROM reply_events WHERE status='draft'"
            ).fetchone()[0],
        }
        return stats
    finally:
        conn.close()


# ─── Audit Requests ───────────────────────────────────────────────────────

def save_audit_request(business_name, place_id, email):
    """Save a free audit request from the landing page."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO audit_requests (business_name, place_id, email)
            VALUES (?, ?, ?)
        """, (business_name, place_id, email))
        conn.commit()
        return True
    finally:
        conn.close()


def get_audit_requests():
    """Get all audit requests."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM audit_requests ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Customers / Onboarding / Mini-Audits ────────────────────────────────

def upsert_customer(email, business_name=None, contact_name=None,
                    stripe_customer_id=None, stripe_subscription_id=None,
                    status=None, source="unknown"):
    """Create/update a customer or lead record by email."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO customers
                (email, business_name, contact_name, stripe_customer_id,
                 stripe_subscription_id, status, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                business_name=COALESCE(excluded.business_name, customers.business_name),
                contact_name=COALESCE(excluded.contact_name, customers.contact_name),
                stripe_customer_id=COALESCE(excluded.stripe_customer_id, customers.stripe_customer_id),
                stripe_subscription_id=COALESCE(excluded.stripe_subscription_id, customers.stripe_subscription_id),
                status=COALESCE(excluded.status, customers.status),
                source=COALESCE(excluded.source, customers.source),
                updated_at=datetime('now')
        """, (email, business_name, contact_name, stripe_customer_id,
              stripe_subscription_id, status or "lead", source))
        conn.commit()
        row = conn.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def save_onboarding_submission(data):
    """Save customer onboarding details and upsert the customer."""
    email = (data.get("customer_email") or data.get("email") or "").strip().lower()
    business_name = (data.get("business_name") or "").strip()
    if not email or not business_name:
        raise ValueError("customer_email and business_name are required")
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO onboarding_submissions
                (customer_email, business_name, contact_name, website, city,
                 review_profile_url, place_id, approval_email, preferred_tone,
                 liability_notes, service_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email,
            business_name,
            data.get("contact_name", "").strip(),
            data.get("website", "").strip(),
            data.get("city", "").strip(),
            data.get("review_profile_url", "").strip(),
            data.get("place_id", "").strip(),
            (data.get("approval_email") or email).strip().lower(),
            data.get("preferred_tone", "professional").strip(),
            data.get("liability_notes", "").strip(),
            data.get("service_notes", "").strip(),
        ))
        conn.commit()
        onboarding_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    upsert_customer(email, business_name=business_name,
                    contact_name=data.get("contact_name", "").strip(),
                    status="onboarding_submitted", source="onboarding")
    return onboarding_id


def list_onboarding_submissions(status=None):
    conn = get_connection()
    try:
        where = "WHERE status=?" if status else ""
        rows = conn.execute(f"""
            SELECT * FROM onboarding_submissions
            {where}
            ORDER BY created_at DESC
        """, (status,) if status else ()).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_mini_audit(data):
    """Save a mini-audit draft or sent report."""
    email = (data.get("prospect_email") or data.get("email") or "").strip().lower()
    business_name = (data.get("business_name") or "").strip()
    if not email or not business_name:
        raise ValueError("prospect_email and business_name are required")
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO mini_audits
                (prospect_email, business_name, website, review_profile_url,
                 public_rating, review_count, bad_review_examples,
                 complaint_themes, response_drafts, recommendation, status, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email,
            business_name,
            data.get("website", "").strip(),
            data.get("review_profile_url", "").strip(),
            data.get("public_rating", "").strip(),
            data.get("review_count", "").strip(),
            json.dumps(data.get("bad_review_examples", [])),
            json.dumps(data.get("complaint_themes", [])),
            json.dumps(data.get("response_drafts", [])),
            data.get("recommendation", "").strip(),
            data.get("status", "draft"),
            datetime.utcnow().isoformat() if data.get("status") == "sent" else None,
        ))
        conn.commit()
        audit_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()
    upsert_customer(email, business_name=business_name, status="lead", source="mini_audit")
    return audit_id


def list_mini_audits(status=None):
    conn = get_connection()
    try:
        where = "WHERE status=?" if status else ""
        rows = conn.execute(f"""
            SELECT * FROM mini_audits
            {where}
            ORDER BY created_at DESC
        """, (status,) if status else ()).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_mini_audit(audit_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM mini_audits WHERE id=?", (audit_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_customers():
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM customers ORDER BY updated_at DESC, created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_reply_event(data):
    """Save an inbound reply and recommended response draft."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO reply_events
                (business_name, contact_email, inbound_text, classification, recommended_reply)
            VALUES (?, ?, ?, ?, ?)
        """, (
            data.get("business_name", "").strip(),
            data.get("contact_email", "").strip().lower(),
            data.get("inbound_text", "").strip(),
            data.get("classification", "needs_review").strip(),
            data.get("recommended_reply", "").strip(),
        ))
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def list_reply_events(status=None):
    conn = get_connection()
    try:
        where = "WHERE status=?" if status else ""
        rows = conn.execute(f"""
            SELECT * FROM reply_events
            {where}
            ORDER BY created_at DESC
        """, (status,) if status else ()).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_test_records():
    """Remove non-customer smoke-test records created during QA."""
    conn = get_connection()
    try:
        patterns = ('%@example.com', '%ops-test%', '%test%')
        deleted = {}
        for table, col in [
            ('customers', 'email'),
            ('audit_requests', 'email'),
            ('onboarding_submissions', 'customer_email'),
            ('mini_audits', 'prospect_email'),
            ('reply_events', 'contact_email'),
        ]:
            total = 0
            for pat in patterns:
                cur = conn.execute(f"DELETE FROM {table} WHERE {col} LIKE ?", (pat,))
                total += cur.rowcount or 0
            deleted[table] = total
        conn.commit()
        return deleted
    finally:
        conn.close()


# ─── Theme Analysis ───────────────────────────────────────────────────────

def get_complaint_themes(business_id):
    """Aggregate complaint themes for a business across all drafts."""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT complaint_themes FROM response_drafts
            WHERE business_id=? AND complaint_themes IS NOT NULL
        """, (business_id,)).fetchall()
        themes = []
        for row in rows:
            try:
                themes.extend(json.loads(row["complaint_themes"]))
            except (json.JSONDecodeError, TypeError):
                pass
        return themes
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("Database ready.")
