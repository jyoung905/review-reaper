"""
Review Reaper - AI Response Generator

Generates professional response drafts for negative reviews
and creates recovery offer templates.
Tone adapts to business type (auto shop ≠ dental office).
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"


# ─── Tone Profiles ─────────────────────────────────────────────────────────

TONE_PROFILES = {
    "auto_shop": {
        "industry_context": "automotive repair and maintenance shop",
        "tone": "professional, straightforward, mechanically competent",
        "resolution_moves": [
            "offer a complimentary re-inspection",
            "offer a discount on their next service visit",
            "invite them back for a corrected repair at no charge",
            "offer a free car wash/detail with next appointment",
        ],
        "vocabulary_hints": "Use automotive terms naturally. Be specific about technical issues. Sound like you know cars."
    },
    "dental": {
        "industry_context": "dental practice",
        "tone": "warm, professional, reassuring, health-focused",
        "resolution_moves": [
            "offer a complimentary follow-up visit",
            "offer a discount on their next cleaning",
            "waive the consultation fee for a second opinion",
            "offer a free teeth whitening as a goodwill gesture",
        ],
        "vocabulary_hints": "Focus on patient comfort and oral health. Be gentle in language. Show clinical confidence."
    },
    "restaurant": {
        "industry_context": "restaurant or food service",
        "tone": "friendly, apologetic, hospitality-focused",
        "resolution_moves": [
            "offer a complimentary meal on their next visit",
            "offer a discount on their next order",
            "invite them back as a guest of the manager",
            "offer a free appetizer or dessert",
        ],
        "vocabulary_hints": "Be warm and personal. Reference hospitality values. Show you care about the dining experience."
    },
    "property_management": {
        "industry_context": "property management or real estate",
        "tone": "professional, solution-oriented, tenant-focused",
        "resolution_moves": [
            "schedule an immediate maintenance inspection",
            "offer a rent credit for the inconvenience",
            "assign a dedicated property manager to their case",
            "offer priority service for future maintenance requests",
        ],
        "vocabulary_hints": "Be formal but approachable. Reference lease terms and company policies where relevant. Show accountability."
    },
    "medical": {
        "industry_context": "medical practice or clinic",
        "tone": "professional, empathetic, clinical but warm",
        "resolution_moves": [
            "offer a complimentary follow-up consultation",
            "waive the copay for the next visit",
            "schedule a call with the practice manager",
            "offer a free health screening",
        ],
        "vocabulary_hints": "Use medical terminology appropriately. Prioritize patient well-being. Be mindful of HIPAA/privacy."
    },
    "fitness": {
        "industry_context": "fitness center or gym",
        "tone": "motivational, energetic, supportive",
        "resolution_moves": [
            "offer a free personal training session",
            "offer a month of membership at no charge",
            "invite them for a facility tour with the manager",
            "offer a complimentary nutrition consultation",
        ],
        "vocabulary_hints": "Be encouraging and energetic. Reference fitness goals. Sound like a coach."
    },
    "general": {
        "industry_context": "business",
        "tone": "professional, sincere, solution-focused",
        "resolution_moves": [
            "offer a full refund or replacement",
            "offer a discount on their next purchase",
            "invite them to speak with a manager directly",
            "offer a complimentary service to make things right",
        ],
        "vocabulary_hints": "Be professional and earnest. Focus on resolution and customer satisfaction."
    }
}


def _get_tone_profile(business_type):
    """Get tone profile, falling back to general."""
    profile = TONE_PROFILES.get(business_type, TONE_PROFILES["general"])
    if business_type not in TONE_PROFILES:
        profile = TONE_PROFILES["general"].copy()
        profile["industry_context"] = f"{business_type.replace('_', ' ')} business"
    return profile


def _call_openai(prompt, max_tokens=500):
    """Call OpenAI API to generate text. In dry-run, returns mock response."""
    if DRY_RUN:
        # Return a template-based response instead of calling API
        print("   [DRY RUN] Skipping OpenAI API call, using template")
        return None  # caller will fall back to templates
    
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required for production mode")
    
    client = OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a professional reputation management assistant. Generate responses for negative Google reviews. Be sincere, specific, and solution-oriented."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    
    return response.choices[0].message.content.strip()


# ─── Template Response Generator (dry-run capable) ─────────────────────────

TEMPLATES = {
    "service": {
        "subject": "poor customer service",
        "response": "Thank you for your honest feedback, {reviewer_name}. I'm genuinely sorry to hear about your experience with our team — that's not the standard we strive for. We pride ourselves on being {tone_adj} and it's clear we fell short here. I'd love the opportunity to make this right for you personally. Please reach out to me directly at {contact} so I can address your concerns and ensure you receive the experience you deserve.",
        "offer": "Complimentary {service_type} on your next visit as our apology for the inconvenience."
    },
    "wait_time": {
        "subject": "wait times and delays",
        "response": "Hi {reviewer_name}, thank you for sharing this. You're absolutely right — your time is valuable and waiting {duration} is unacceptable. I apologize sincerely for the delay. We're working on improving our scheduling to prevent this from happening again. In the meantime, I'd like to personally make sure your next visit runs smoothly. Please contact me at {contact} and I'll ensure you're prioritized.",
        "offer": "We'd like to offer you priority scheduling for your next visit, plus {discount}% off any service."
    },
    "price": {
        "subject": "pricing concerns",
        "response": "Thank you for your transparency, {reviewer_name}. I understand your frustration regarding the cost. We aim to be upfront about pricing and it sounds like we missed the mark in your case. I'd appreciate the chance to review your invoice personally and discuss it with you. Please reach out to me at {contact} and I'll make sure we find a fair resolution.",
        "offer": "We'd like to offer {discount}% off your next service as a gesture of goodwill."
    },
    "quality": {
        "subject": "quality of work",
        "response": "{reviewer_name}, thank you for bringing this to our attention. I apologize that the quality of our work did not meet expectations. We stand behind what we do and I'd like to personally ensure this is corrected. Please contact me at {contact} so I can arrange for a thorough re-inspection and make things right at no additional cost to you.",
        "offer": "Complimentary re-service or full refund — whichever you prefer. Plus {discount}% off your next booking."
    },
    "communication": {
        "subject": "poor communication",
        "response": "I appreciate you letting us know, {reviewer_name}. Clear communication is something we take seriously, and I'm sorry we let you down in this regard. You shouldn't have to chase us for updates. I'd like to personally ensure you have a direct line to someone who can help. Please reach me directly at {contact}.",
        "offer": "We'll assign you a dedicated contact person going forward, plus {discount}% off your next service."
    },
    "honesty": {
        "subject": "trust concerns",
        "response": "{reviewer_name}, I want to thank you for your candor. It concerns me greatly to hear that you felt misled — that is never our intention and I apologize sincerely. Building trust with our customers is the foundation of our business. I would very much like to speak with you personally to understand what happened and find a fair resolution. Please contact me at {contact}.",
        "offer": "We will honor the original quoted price and offer a {discount}% discount on your next visit."
    },
    "cleanliness": {
        "subject": "cleanliness issues",
        "response": "Thank you for your feedback, {reviewer_name}. Cleanliness and presentation matter deeply to us, and I'm sorry we didn't meet that standard during your visit. I've shared your comments with our team and we're addressing it immediately. I'd like to invite you back so we can show you the experience we're truly capable of providing. Please reach me at {contact}.",
        "offer": "Complimentary {service_type} with a priority cleanliness guarantee on your return visit."
    },
    "rude_behavior": {
        "subject": "staff behavior",
        "response": "{reviewer_name}, I want to sincerely apologize for the way you were treated. How our team interacts with customers is just as important as the work we do, and we clearly fell short here. This has been addressed internally and I personally guarantee you a different experience going forward. Please give me a chance to make this right — contact me directly at {contact}.",
        "offer": "I'd like to personally handle your next appointment and offer {discount}% off as our apology."
    },
    "general_dissatisfaction": {
        "subject": "overall dissatisfaction",
        "response": "Thank you for your honest review, {reviewer_name}. I'm sorry your experience didn't meet expectations. Every piece of feedback helps us improve, and yours is no exception. I'd love the opportunity to learn more about what went wrong and make it right. Please reach out to me directly at {contact}.",
        "offer": "As our apology, we'd like to offer {discount}% off your next visit — on us."
    }
}


def generate_response_template(review_text, reviewer_name, business_type, themes, rating):
    """
    Generate a response draft using templates (works in dry-run mode).
    Creates a natural-sounding response based on complaint themes.
    
    If OpenAI key is present and dry_run is False, uses AI for richer generation.
    """
    theme = themes[0] if themes else "general_dissatisfaction"
    template = TEMPLATES.get(theme, TEMPLATES["general_dissatisfaction"])
    profile = _get_tone_profile(business_type)
    
    # Map industry context to template variables
    service_types = {
        "auto_shop": "inspection",
        "dental": "checkup",
        "restaurant": "meal",
        "property_management": "inspection visit",
        "medical": "consultation",
        "fitness": "training session",
        "general": "service",
    }
    
    service_type = service_types.get(business_type, "service")
    contact = f"[your_email@example.com]"
    
    # Try OpenAI first if available and not in dry-run
    if not DRY_RUN:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "your_openai_api_key_here":
            prompt = (
                f"Generate a professional response to a {rating}-star Google review for a {profile['industry_context']}.\n\n"
                f"The reviewer '{reviewer_name}' wrote:\n\"{review_text}\"\n\n"
                f"Identified complaint themes: {', '.join(themes)}.\n\n"
                f"Tone should be: {profile['tone']}\n"
                f"Vocabulary hints: {profile['vocabulary_hints']}\n\n"
                f"Requirements:\n"
                f"1. Acknowledge the specific issue\n"
                f"2. Apologize sincerely\n"
                f"3. Offer a specific resolution path\n"
                f"4. Invite offline conversation\n"
                f"5. Keep it to 3-4 sentences\n"
                f"6. Sound human, not corporate\n\n"
                f"Also include ONE specific recovery offer (e.g., discount, free service, etc.).\n\n"
                f"Format:\n"
                f"---RESPONSE---\n[response text]\n"
                f"---OFFER---\n[offer text]"
            )
            
            ai_response = _call_openai(prompt)
            if ai_response:
                parts = ai_response.split("---OFFER---")
                response_text = parts[0].replace("---RESPONSE---", "").strip()
                offer_text = parts[1].strip() if len(parts) > 1 else template["offer"]
                return response_text, offer_text
    
    # Fall back to template
    discount = "15"
    duration = "over an hour" if "hours" in review_text.lower() or "forever" in review_text.lower() else "longer than expected"
    
    response = template["response"].format(
        reviewer_name=reviewer_name or "there",
        tone_adj=profile["tone"].split(",")[0],
        contact=contact,
        duration=duration,
    )
    
    offer = template["offer"].format(
        service_type=service_type,
        discount=discount,
    )
    
    return response, offer


def generate_recovery_offer(business_type, themes, template_only=False):
    """Generate a recovery offer template based on business type and complaint themes."""
    profile = _get_tone_profile(business_type)
    
    if not template_only:
        # Pick the most fitting resolution move
        moves = profile["resolution_moves"]
        return random.choice(moves) if moves else TEMPLATES["general_dissatisfaction"]["offer"]
    
    # Return a comprehensive offer
    return (
        f"We'd like to make this right. "
        f"As a gesture of goodwill, we're offering [discount_percentage]% off your next visit OR "
        f"a complimentary [free_service]. "
        f"Please contact us at [phone/email] and mention this review. "
        f"We value your business and want to earn back your trust."
    )


def generate_all_responses(business_data, business_id):
    """
    Generate response drafts for all negative reviews of a business.
    
    Returns list of dicts with review_id, response_text, recovery_offer, themes
    """
    from .database import save_response_draft
    
    negative_reviews = business_data.get("negative_reviews", [])
    business_info = business_data.get("business", {})
    business_type = business_info.get("business_type", "general")
    
    results = []
    for r in negative_reviews:
        themes = r.get("themes", ["general_dissatisfaction"])
        sentiment = r.get("sentiment", "negative")
        
        response_text, recovery_offer = generate_response_template(
            review_text=r.get("text", ""),
            reviewer_name=r.get("reviewer_name", "Customer"),
            business_type=business_type,
            themes=themes,
            rating=r.get("rating", 1),
        )
        
        results.append({
            "reviewer_name": r.get("reviewer_name"),
            "rating": r.get("rating"),
            "review_text": r.get("text"),
            "themes": themes,
            "sentiment": sentiment,
            "response_text": response_text,
            "recovery_offer": recovery_offer,
        })
        
        print(f"   ✍️  Draft for {r.get('reviewer_name', 'Customer')}: {themes[0]}")
    
    return results


import random  # needed for recovery offer random selection


if __name__ == "__main__":
    from scraper import scrape_and_analyze
    
    place_id = "ChIJN1t_tDeuEmsRUsoyG83frY4"
    data = scrape_and_analyze(place_id)
    
    print("\n✍️  Generating response drafts...")
    drafts = generate_all_responses(data, business_id=1)
    
    for d in drafts:
        print(f"\n{'='*60}")
        print(f"📝 {d['reviewer_name']} ({d['rating']}⭐): {d['review_text'][:60]}...")
        print(f"   Themes: {', '.join(d['themes'])}")
        print(f"\n   Response: {d['response_text']}")
        print(f"\n   🎁 Offer: {d['recovery_offer']}")
