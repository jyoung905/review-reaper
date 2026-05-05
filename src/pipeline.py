"""
Review Reaper - Pipeline Coordinator

Orchestrates the full workflow:
1. Find/add a business by Place ID
2. Scrape and analyze reviews
3. Generate AI response drafts
4. Store everything in SQLite
"""

import sys
import json
from pathlib import Path

from .database import (
    init_db, add_business, get_business_by_place_id, get_business,
    add_reviews, save_audit_request, get_stats, list_businesses,
    get_negative_reviews, get_drafts_by_status, get_review, save_response_draft
)
from .scraper import scrape_and_analyze, find_place_id
from .response_generator import generate_all_responses

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def run_full_pipeline(place_id, business_type=None):
    """
    Complete pipeline: scrape → analyze → generate → store.
    
    Returns the business_id for the tracked business.
    """
    print(f"\n{'='*60}")
    print(f"🔄 REVIEW REAPER PIPELINE")
    print(f"{'='*60}")
    
    # Step 1: Scrape & analyze
    data = scrape_and_analyze(place_id, custom_business_type=business_type)
    biz = data["business"]
    
    # Step 2: Store business
    biz_id = add_business(
        name=biz["name"],
        place_id=biz["place_id"],
        address=biz.get("address"),
        phone=biz.get("phone"),
        website=biz.get("website"),
        business_type=biz.get("business_type", "general"),
        rating=biz.get("rating"),
        total_reviews=biz.get("total_reviews", 0),
    )
    print(f"📦 Business stored: {biz['name']} (ID: {biz_id})")
    
    # Step 3: Store negative reviews
    count = add_reviews(biz_id, data["negative_reviews"])
    print(f"📝 Stored {count} negative reviews")
    
    # Step 4: Generate and save response drafts
    print(f"\n✍️  Generating AI response drafts...")
    drafts = generate_all_responses(data, biz_id)
    
    for d in drafts:
        # Get the review we just stored
        negative_reviews = get_negative_reviews(biz_id)
        for rev in negative_reviews:
            if rev.get("reviewer_name") == d["reviewer_name"]:
                save_response_draft(
                    review_id=rev["id"],
                    business_id=biz_id,
                    text=d["response_text"],
                    recovery_offer=d["recovery_offer"],
                    sentiment_label=d["sentiment"],
                    complaint_themes=d["themes"],
                )
                break
    
    print(f"\n✅ Pipeline complete! {len(drafts)} response drafts generated.")
    
    return biz_id


def run_audit_check(place_id, email=None, business_name=None, business_type=None):
    """
    Quick audit for a business: scrape, analyze, return summary without saving everything.
    Used for the "Free Review Audit" feature.
    """
    print(f"\n📋 Running free audit for: {business_name or place_id}")
    
    data = scrape_and_analyze(place_id, custom_business_type=business_type)
    biz = data["business"]
    
    negative = len(data["negative_reviews"])
    top_themes = data["theme_analysis"][:3]
    
    summary = {
        "business_name": biz["name"],
        "rating": biz["rating"],
        "total_reviews": biz["total_reviews"],
        "negative_reviews": negative,
        "positive_reviews": biz["total_reviews"] - negative,
        "negative_percentage": round(negative / max(biz["total_reviews"], 1) * 100, 1),
        "top_themes": [{"theme": t[0], "count": t[1]} for t in top_themes],
        "business_type": biz.get("business_type", "general"),
    }
    
    print(f"\n📊 Audit Summary for {biz['name']}:")
    print(f"   Rating: {biz['rating']:.1f}⭐ ({biz['total_reviews']} reviews)")
    print(f"   Negative reviews: {negative} ({summary['negative_percentage']}%)")
    print(f"   Top themes: {', '.join(t[0] for t in top_themes)}")
    
    return summary


def show_dashboard():
    """Print a simple terminal dashboard."""
    stats = get_stats()
    businesses = list_businesses()
    
    print(f"\n{'='*60}")
    print(f"📊 REVIEW REAPER DASHBOARD")
    print(f"{'='*60}")
    print(f"\n📈 Overview:")
    print(f"   Businesses tracked:  {stats['total_businesses']}")
    print(f"   Total reviews:       {stats['total_reviews']}")
    print(f"   Negative (≤3⭐):      {stats['negative_reviews']}")
    print(f"   Pending drafts:      {stats['pending_drafts']}")
    print(f"   Approved drafts:     {stats['approved_drafts']}")
    print(f"   Sent responses:      {stats['sent_drafts']}")
    print(f"   Pending audit reqs:  {stats['pending_audits']}")
    
    if businesses:
        print(f"\n🏢 Tracked Businesses:")
        for b in businesses:
            print(f"   • {b['name']}: {b['negative_count']} negative reviews, "
                  f"{b.get('pending_responses', 0)} pending responses")
    
    return stats


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Review Reaper Pipeline")
    parser.add_argument("--step", choices=["scrape", "generate", "all", "audit", "dashboard", "init-db"],
                        default="dashboard", help="Pipeline step to run")
    parser.add_argument("--place-id", help="Google Place ID")
    parser.add_argument("--type", help="Business type (auto_shop, dental, etc.)")
    parser.add_argument("--name", help="Business name for audit")
    parser.add_argument("--email", help="Email for audit results")
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    
    args = parser.parse_args()
    
    if args.init_db or args.step == "init-db":
        init_db()
        sys.exit(0)
    
    step = args.step
    
    if step == "dashboard":
        show_dashboard()
    
    elif step == "all":
        if not args.place_id:
            print("❌ --place-id required for full pipeline")
            sys.exit(1)
        init_db()
        run_full_pipeline(args.place_id, args.type)
    
    elif step in ("scrape",):
        if not args.place_id:
            print("❌ --place-id required")
            sys.exit(1)
        init_db()
        data = scrape_and_analyze(args.place_id, args.type)
        print(json.dumps(data, indent=2, default=str))
    
    elif step == "generate":
        if not args.place_id:
            print("❌ --place-id required")
            sys.exit(1)
        init_db()
        data = scrape_and_analyze(args.place_id, args.type)
        drafts = generate_all_responses(data, business_id=0)
        for d in drafts:
            print(json.dumps(d, indent=2))
    
    elif step == "audit":
        if not args.place_id:
            print("❌ --place-id required for audit")
            sys.exit(1)
        summary = run_audit_check(args.place_id, args.email, args.name, args.type)
        print(json.dumps(summary, indent=2))
    
    else:
        parser.print_help()
