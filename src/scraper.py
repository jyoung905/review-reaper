"""
Review Reaper - Google Reviews Scraper

Fetches reviews from Google Places API by Place ID.
Filters negative reviews (rating ≤ 3), identifies common complaint themes.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# --- Public Place ID lookup (no API key needed for basic) ---
# Google Place IDs can be found at: https://developers.google.com/maps/documentation/places/web-service/place-id

# Sample review data for dry-run / demo mode
SAMPLE_REVIEWS = {
    "ChIJN1t_tDeuEmsRUsoyG83frY4": {  # Example: random place in Toronto
        "name": "Sample Auto Shop",
        "address": "123 Main St, Toronto, ON",
        "phone": "+1-416-555-0100",
        "website": "https://example.com/auto",
        "rating": 3.2,
        "total_reviews": 47,
        "business_type": "auto_shop",
        "reviews": [
            {
                "reviewer_name": "Mike T.",
                "rating": 1,
                "text": "Horrible service. Brought my car in for an oil change and they scratched the paint. Manager was rude when I complained.",
                "date_posted": "2026-04-15"
            },
            {
                "reviewer_name": "Sarah L.",
                "rating": 1,
                "text": "Waited 3 hours for a simple tire rotation. No apology, no explanation. Will never come back.",
                "date_posted": "2026-04-10"
            },
            {
                "reviewer_name": "James K.",
                "rating": 2,
                "text": "Decent work but way overpriced. Charged $200 for a diagnostic that took 10 minutes. Felt ripped off.",
                "date_posted": "2026-03-28"
            },
            {
                "reviewer_name": "Emily R.",
                "rating": 2,
                "text": "They fixed the brake issue but left grease stains all over my passenger seat. Cleanliness matters.",
                "date_posted": "2026-03-15"
            },
            {
                "reviewer_name": "Dave P.",
                "rating": 3,
                "text": "Average experience. Communication could be better. Had to call twice to check on my car's status.",
                "date_posted": "2026-03-01"
            },
            {
                "reviewer_name": "Lisa M.",
                "rating": 1,
                "text": "Worst customer service experience. They quoted me $500, then tried to charge $900 after the work was done.",
                "date_posted": "2026-02-20"
            },
            {
                "reviewer_name": "Tom W.",
                "rating": 2,
                "text": "The repair itself was fine but getting someone on the phone is impossible. Voicemail never returned.",
                "date_posted": "2026-02-10"
            },
            {
                "reviewer_name": "Rachel N.",
                "rating": 1,
                "text": "Took my car in for an AC repair. They kept it for a week and the AC still doesn't work properly. Complete waste of time and money.",
                "date_posted": "2026-01-25"
            },
            {
                "reviewer_name": "Chris B.",
                "rating": 3,
                "text": "Okay shop but they upsell everything. Came in for a simple fix and they tried to sell me $2000 worth of unnecessary work.",
                "date_posted": "2026-01-15"
            },
            {
                "reviewer_name": "Anna D.",
                "rating": 2,
                "text": "Parking lot is a nightmare. Also had to wait 45 minutes past my appointment time. Not respecting customers' time.",
                "date_posted": "2026-01-05"
            }
        ]
    },
    "ChIJC8N0v7yuEmsR7KQh8LOOdHY": {
        "name": "Oakville Dental Care",
        "address": "456 Lakeshore Rd, Oakville, ON",
        "phone": "+1-905-555-0200",
        "website": "https://example.com/dental",
        "rating": 3.5,
        "total_reviews": 62,
        "business_type": "dental",
        "reviews": [
            {
                "reviewer_name": "Karen M.",
                "rating": 1,
                "text": "Rude front desk staff. Made me feel like I was inconveniencing them just by showing up for my appointment.",
                "date_posted": "2026-04-12"
            },
            {
                "reviewer_name": "John D.",
                "rating": 1,
                "text": "Had a filling done and it fell out 2 weeks later. Had to pay again for the replacement. Feels like a scam.",
                "date_posted": "2026-04-05"
            },
            {
                "reviewer_name": "Patricia L.",
                "rating": 2,
                "text": "Dentist was fine but the billing is a mess. They billed my insurance wrong and I spent hours on the phone fixing it.",
                "date_posted": "2026-03-20"
            },
            {
                "reviewer_name": "Robert F.",
                "rating": 1,
                "text": "They keep pushing expensive treatments I don't need. Every visit is a sales pitch for Invisalign or whitening.",
                "date_posted": "2026-03-10"
            },
            {
                "reviewer_name": "Jennifer S.",
                "rating": 3,
                "text": "Clean office, friendly hygienist. But the wait times are ridiculous. Was 40 minutes late for my appointment.",
                "date_posted": "2026-02-28"
            },
            {
                "reviewer_name": "Michael B.",
                "rating": 2,
                "text": "Good dentist but impossible to get appointments. Booked 3 months out for a routine cleaning.",
                "date_posted": "2026-02-15"
            },
            {
                "reviewer_name": "Susan W.",
                "rating": 1,
                "text": "The dentist was rough and impatient. Made me feel rushed. Didn't explain what he was doing.",
                "date_posted": "2026-02-01"
            },
            {
                "reviewer_name": "David C.",
                "rating": 2,
                "text": "Cancelled my appointment last minute twice in a row. Very unprofessional scheduling.",
                "date_posted": "2026-01-20"
            },
            {
                "reviewer_name": "Amanda H.",
                "rating": 1,
                "text": "Hidden fees everywhere. Quoted one price, charged another. When I questioned it, they got defensive.",
                "date_posted": "2026-01-10"
            },
            {
                "reviewer_name": "Peter G.",
                "rating": 3,
                "text": "Decent work but the office feels chaotic. Multiple staff couldn't find my file. Needs better organization.",
                "date_posted": "2026-01-02"
            }
        ]
    }
}

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"


# ─── Keyword / Sentiment Analysis ─────────────────────────────────────────

COMPLAINT_KEYWORDS = {
    "service": ["rude", "unhelpful", "ignored", "dismissive", "terrible service",
                "bad service", "poor service", "customer service", "front desk",
                "staff", "attitude", "unprofessional", "disrespectful", "cold"],
    "wait_time": ["wait", "waiting", "delay", "late", "slow", "took forever",
                  "hours", "time", "appointment", "scheduling", "cancelled",
                  "reschedule", "no-show", "overbook"],
    "price": ["expensive", "overpriced", "ripoff", "rip off", "overcharge",
              "hidden fee", "billing", "quote", "charged more", "overbilled",
              "overpaid", "cost", "price", "money", "overpriced", "over charged"],
    "quality": ["poor quality", "bad work", "fell apart", "broken", "defective",
                "not working", "worse", "didn't fix", "still broken", "failed",
                "scratch", "damage", "stain", "mess", "unfinished"],
    "communication": ["no response", "no call", "no update", "didn't call back",
                      "voicemail", "phone", "email", "communication",
                      "informed", "notified", "explain", "explanation",
                      "never called", "never heard back"],
    "honesty": ["scam", "bait and switch", "misled", "lied", "dishonest",
                "sneaky", "tricked", "upsell", "unnecessary", "sales pitch",
                "pushy", "pressure", "hidden agenda"],
    "cleanliness": ["dirty", "messy", "clean", "hygiene", "stains", "grease",
                    "stained", "smell", "sanitary", "germs"],
    "rude_behavior": ["rude", "angry", "yell", "shout", "condescending",
                      "belittling", "impatient", "sarcastic", "nasty",
                      "aggressive", "confrontational", "dismissive"]
}

BUSINESS_ADJECTIVES = {
    "auto_shop": "mechanically inclined",
    "dental": "dental practice",
    "general": "business",
    "restaurant": "dining",
    "property_management": "property",
    "franchise": "franchise",
    "retail": "retail",
    "medical": "medical practice"
}


def search_by_place_id(place_id):
    """
    Fetch reviews for a business by Google Place ID.
    In MVP dry-run mode, returns sample data.
    In production, calls Google Places API.
    """
    if DRY_RUN and place_id in SAMPLE_REVIEWS:
        data = SAMPLE_REVIEWS[place_id]
        print(f"📋 [DRY RUN] Using sample data for: {data['name']}")
        return data
    
    if DRY_RUN:
        # Return generic sample for unknown place IDs
        print(f"📋 [DRY RUN] Place ID not in samples, using generic auto shop data")
        sample = list(SAMPLE_REVIEWS.values())[0].copy()
        sample["name"] = f"Business ({place_id[:12]}...)"
        return sample
    
    # Production mode: call Google Places API
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY required for production mode")
    
    import requests
    
    # Step 1: Get place details
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,website,rating,user_ratings_total,review",
        "key": api_key,
    }
    
    resp = requests.get(details_url, params=params)
    data = resp.json()
    
    if data.get("status") != "OK":
        raise Exception(f"Places API error: {data.get('status')} - {data.get('error_message', '')}")
    
    result = data.get("result", {})
    reviews_raw = result.get("reviews", [])
    
    reviews = []
    for r in reviews_raw:
        reviews.append({
            "reviewer_name": r.get("author_name"),
            "rating": r.get("rating", 0),
            "text": r.get("text", ""),
            "date_posted": r.get("relative_time_description", ""),
        })
    
    return {
        "name": result.get("name", "Unknown"),
        "address": result.get("formatted_address", ""),
        "phone": result.get("formatted_phone_number", ""),
        "website": result.get("website", ""),
        "rating": result.get("rating", 0),
        "total_reviews": result.get("user_ratings_total", 0),
        "business_type": "general",
        "reviews": reviews,
    }


def find_place_id(business_name, location=None):
    """
    Search for a business by name and return the most likely Place ID.
    In dry-run mode, returns a sample Place ID.
    """
    if DRY_RUN:
        print(f"🔍 [DRY RUN] Searching for '{business_name}' — returning sample")
        return list(SAMPLE_REVIEWS.keys())[0]
    
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY required for production mode")
    
    import requests
    
    query = business_name
    if location:
        query = f"{business_name} {location}"
    
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,name,formatted_address",
        "key": api_key,
    }
    
    resp = requests.get(url, params=params)
    data = resp.json()
    
    if data.get("status") != "OK" or not data.get("candidates"):
        return None
    
    return data["candidates"][0]["place_id"]


def analyze_sentiment(review_text):
    """
    Simple keyword-based sentiment analysis for negative reviews.
    Returns a sentiment label and identified complaint themes.
    """
    if not review_text:
        return "negative-unspecified", ["no text"]
    
    text_lower = review_text.lower()
    found_themes = []
    
    for theme, keywords in COMPLAINT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found_themes.append(theme)
                break  # one match per theme is enough
    
    # Deduplicate
    found_themes = list(set(found_themes))
    
    if not found_themes:
        found_themes = ["general_dissatisfaction"]
    
    # Determine intensity
    intense_words = ["worst", "horrible", "terrible", "awful", "disgusting",
                     "never", "scam", "thief", "fraud", "unacceptable"]
    intense_count = sum(1 for w in intense_words if w in text_lower)
    
    if intense_count >= 2:
        sentiment = "very_negative"
    elif intense_count >= 1:
        sentiment = "negative"
    else:
        sentiment = "mildly_negative"
    
    return sentiment, found_themes


def detect_business_type_from_name(name):
    """Infer business type from the name."""
    if not name:
        return "general"
    name_lower = name.lower()
    type_hints = {
        "auto": "auto_shop",
        "car": "auto_shop",
        "garage": "auto_shop",
        "mechanic": "auto_shop",
        "tire": "auto_shop",
        "dental": "dental",
        "dentist": "dental",
        "restaurant": "restaurant",
        "cafe": "restaurant",
        "pizza": "restaurant",
        "grill": "restaurant",
        "property": "property_management",
        "realty": "property_management",
        "rental": "property_management",
        "apartment": "property_management",
        "fitness": "fitness",
        "gym": "fitness",
        "med": "medical",
        "clinic": "medical",
        "doctor": "medical",
        "retail": "retail",
        "shop": "retail",
        "store": "retail",
        "franchise": "franchise",
    }
    for hint, biz_type in type_hints.items():
        if hint in name_lower:
            return biz_type
    return "general"


def scrape_and_analyze(place_id, custom_business_type=None):
    """
    Pull reviews by Place ID, filter negative (rating ≤ 3),
    analyze complaint themes, and return structured data.
    
    Returns: dict with business info, negative reviews, and theme analysis
    """
    print(f"\n🔍 Fetching reviews for Place ID: {place_id}")
    
    raw = search_by_place_id(place_id)
    
    name = raw.get("name", "Unknown")
    address = raw.get("address", "")
    phone = raw.get("phone", "")
    website = raw.get("website", "")
    rating = raw.get("rating", 0)
    total_reviews = raw.get("total_reviews", 0)
    all_reviews = raw.get("reviews", [])
    business_type = custom_business_type or detect_business_type_from_name(name)
    
    # Filter negative reviews (rating ≤ 3)
    negative = [r for r in all_reviews if r.get("rating", 5) <= 3]
    
    print(f"📊 {name}: {total_reviews} total, {len(negative)} negative (≤3⭐)")
    
    # Analyze each negative review
    analyzed = []
    theme_counts = {}
    
    for r in negative:
        sentiment, themes = analyze_sentiment(r.get("text", ""))
        r["sentiment"] = sentiment
        r["themes"] = themes
        analyzed.append(r)
        
        for t in themes:
            theme_counts[t] = theme_counts.get(t, 0) + 1
    
    # Sort themes by frequency
    sorted_themes = sorted(theme_counts.items(), key=lambda x: -x[1])
    
    print("\n📈 Top Complaint Themes:")
    for theme, count in sorted_themes[:5]:
        pct = round(count / len(negative) * 100)
        print(f"   • {theme.replace('_', ' ').title()}: {count}/{len(negative)} ({pct}%)")
    
    return {
        "business": {
            "name": name,
            "place_id": place_id,
            "address": address,
            "phone": phone,
            "website": website,
            "rating": rating,
            "total_reviews": total_reviews,
            "business_type": business_type,
            "negative_count": len(negative),
        },
        "negative_reviews": analyzed,
        "theme_analysis": sorted_themes,
    }


if __name__ == "__main__":
    import sys
    place_id = sys.argv[1] if len(sys.argv) > 1 else list(SAMPLE_REVIEWS.keys())[0]
    result = scrape_and_analyze(place_id)
    print(f"\n✅ Found {result['business']['negative_count']} negative reviews")
    print(f"   Top theme: {result['theme_analysis'][0] if result['theme_analysis'] else 'N/A'}")
