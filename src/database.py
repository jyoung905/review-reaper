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
