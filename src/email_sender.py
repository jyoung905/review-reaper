"""
Review Reaper - SendGrid Email Integration

Handles sending cold outreach emails to businesses about their bad reviews.
"""

import os
import json
import html as html_lib
from pathlib import Path
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, From, To, Subject, HtmlContent


SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "reviewreaper.biz@gmail.com")
FROM_NAME = os.getenv("FROM_NAME", "Review Reaper")
BASE_URL = os.getenv("BASE_URL", "https://review-reaper-production.up.railway.app").rstrip('/')
ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", FROM_EMAIL)


def send_outreach_email(recipient_email: str, business_name: str, reviews: list) -> dict:
    """
    Send a cold outreach email to a business showing them their bad reviews
    with AI-generated response drafts.

    Args:
        recipient_email: The email address to send to.
        business_name: The name of the business.
        reviews: List of dicts, each with at least:
                 'reviewer_name', 'rating', 'text', 'ai_generated_text',
                 optionally 'complaint_themes' and 'recovery_offer'.

    Returns:
        dict with 'success' bool and 'message' str.
    """
    if not SENDGRID_API_KEY or SENDGRID_API_KEY == "your_sendgrid_api_key_here":
        return {"success": False, "message": "SENDGRID_API_KEY not configured"}

    # Build the HTML email body
    html_body = _build_outreach_html(business_name, reviews)

    message = Mail(
        from_email=From(FROM_EMAIL, FROM_NAME),
        to_emails=To(recipient_email),
        subject=Subject(f"I noticed {business_name} has unanswered bad reviews"),
        html_content=HtmlContent(html_body),
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return {
            "success": True,
            "status_code": response.status_code,
            "message": f"Email sent to {recipient_email} (status {response.status_code})",
        }
    except Exception as e:
        return {"success": False, "message": f"SendGrid error: {str(e)}"}


def send_transactional_email(recipient_email: str, subject: str, html_body: str) -> dict:
    """Send a transactional/service email. Skips obvious QA addresses."""
    if recipient_email.endswith("@example.com") or "ops-test" in recipient_email:
        return {"success": True, "skipped": True, "message": "Skipped QA/test recipient"}
    if not SENDGRID_API_KEY or SENDGRID_API_KEY == "your_sendgrid_api_key_here":
        return {"success": False, "message": "SENDGRID_API_KEY not configured"}
    message = Mail(
        from_email=From(FROM_EMAIL, FROM_NAME),
        to_emails=To(recipient_email),
        subject=Subject(subject),
        html_content=HtmlContent(html_body),
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        return {"success": True, "status_code": response.status_code, "message": f"Email sent to {recipient_email} (status {response.status_code})"}
    except Exception as e:
        return {"success": False, "message": f"SendGrid error: {str(e)}"}


def send_admin_notification(subject: str, body: str) -> dict:
    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#1a1a2e">
      <h2>{html_lib.escape(subject)}</h2>
      <pre style="white-space:pre-wrap;background:#f8f9ff;border:1px solid #e2e8f0;border-radius:8px;padding:14px">{html_lib.escape(body)}</pre>
      <p><a href="{BASE_URL}/admin/ops" style="display:inline-block;background:#e94560;color:#fff;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:700">Open Review Reaper Ops</a></p>
    </div>
    """
    return send_transactional_email(ADMIN_NOTIFY_EMAIL, subject, html_body)


def send_mini_audit_confirmation(recipient_email: str, business_name: str) -> dict:
    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#1a1a2e">
      <h2>We received your Review Reaper mini-audit request</h2>
      <p>Thanks — we’ll review public reputation signals for <strong>{html_lib.escape(business_name)}</strong> and prepare a short mini-audit before asking you to subscribe.</p>
      <p>The audit focuses on negative review themes, suggested response drafts, and the first reputation fix we would make.</p>
      <p>Nothing is posted publicly. This is a private review.</p>
    </div>
    """
    return send_transactional_email(recipient_email, "We received your Review Reaper mini-audit request", html_body)


def send_onboarding_confirmation(recipient_email: str, business_name: str) -> dict:
    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#1a1a2e">
      <h2>Your Review Reaper onboarding is received</h2>
      <p>We received the setup details for <strong>{html_lib.escape(business_name)}</strong>.</p>
      <p>Next step: we’ll prepare your first review scan and response pack. You’ll approve or edit anything before it is used publicly.</p>
      <p>Review Reaper does not auto-post responses.</p>
    </div>
    """
    return send_transactional_email(recipient_email, "Your Review Reaper onboarding is received", html_body)


def _build_outreach_html(business_name: str, reviews: list) -> str:
    """Build a simple HTML email body for outreach."""
    review_cards = ""
    rating_stars = {1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}

    for i, r in enumerate(reviews[:3], 1):
        stars = rating_stars.get(r.get("rating", 0), "")
        reviewer = html_lib.escape(str(r.get("reviewer_name", "Anonymous")))
        text = html_lib.escape(str(r.get("text", "")))
        response = html_lib.escape(str(r.get("ai_generated_text", "")))
        themes = r.get("complaint_themes", [])
        offer = html_lib.escape(str(r.get("recovery_offer", "")))

        themes_html = ""
        if themes:
            theme_tags = " ".join(
                f'<span style="display:inline-block;background:#eef2ff;color:#4338ca;'
                f'padding:2px 8px;border-radius:4px;font-size:12px;margin:2px">'
                f'{html_lib.escape(str(t).replace("_", " ").title())}</span>'
                for t in themes
            )
            themes_html = f'<div style="margin:8px 0">{theme_tags}</div>'

        offer_html = ""
        if offer:
            offer_html = (
                f'<div style="background:#fff7ed;border-left:3px solid #f59e0b;'
                f'padding:8px 12px;margin:8px 0;font-size:13px;border-radius:0 4px 4px 0">'
                f'<strong>💡 Suggested Recovery Offer:</strong> {offer}</div>'
            )

        review_cards += f"""
        <div style="border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:12px 0;background:#f8f9ff">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                <strong>{reviewer}</strong>
                <span>{stars}</span>
            </div>
            <div style="color:#6c7a9a;font-size:13px;margin-bottom:8px;font-style:italic">
                "{text[:500]}{'...' if len(text) > 500 else ''}"
            </div>
            {themes_html}
            <div style="background:#f0fdf4;border-left:3px solid #10b981;padding:8px 12px;
                        border-radius:0 4px 4px 0;font-size:13px;margin:8px 0">
                <strong>✅ AI-Generated Response:</strong><br>{response[:400]}{'...' if len(response) > 400 else ''}
            </div>
            {offer_html}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a2e;background:#f8f9ff;margin:0;padding:0">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9ff;padding:24px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%">

<!-- Header -->
<tr>
<td style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:24px;border-radius:12px 12px 0 0;text-align:center">
<div style="font-size:28px;color:#fff">&#9760; <span style="color:#e94560">Review</span> <span style="color:#fff">Reaper</span></div>
</td>
</tr>

<!-- Body -->
<tr>
<td style="background:#fff;padding:32px 24px;border-radius:0 0 12px 12px">
<h1 style="font-size:22px;margin:0 0 12px">Hi there,</h1>
<p style="color:#6c7a9a;font-size:15px;line-height:1.6;margin:0 0 8px">
I noticed <strong>{html_lib.escape(business_name)}</strong> has unanswered negative reviews on public review profiles.
Left unaddressed, bad reviews can cost you potential customers.
</p>
<p style="color:#6c7a9a;font-size:15px;line-height:1.6;margin:0 0 16px">
Here's how <strong>3 of them</strong> could have been handled with AI-generated responses:
</p>

{review_cards}

<div style="background:#f0fdf4;border:1px solid #d1fae5;border-radius:8px;padding:16px;margin:16px 0;text-align:center">
<p style="color:#065f46;font-size:14px;margin:0 0 8px">
<strong>📊 Review Reaper automatically:</strong>
</p>
<p style="color:#065f46;font-size:13px;margin:4px 0">
✅ Detects negative reviews (rating ≤ 3) across public review profiles<br>
✅ Generates professional, context-aware response drafts<br>
✅ Suggests personalized recovery offers<br>
✅ Tracks complaint themes across all your locations<br>
✅ Requires your approval before anything is posted
</p>
</div>

<p style="color:#6c7a9a;font-size:14px;margin:16px 0 0">
Want to see <strong>{html_lib.escape(business_name)}'s</strong> full audit? We can show you every negative review with ready-to-approve responses.
</p>

<div style="text-align:center;margin:24px 0">
<a href="{BASE_URL}/mini-audit" style="display:inline-block;padding:14px 32px;background:#e94560;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px">
Request Your Free Mini-Audit →
</a>
</div>

<p style="color:#a8b2d1;font-size:12px;line-height:1.5;margin:24px 0 0">
This email was sent by Review Reaper — AI-powered review response management.<br>
If you'd prefer not to receive these, you can reply with "unsubscribe".
</p>
</td>
</tr>

<!-- Footer -->
<tr>
<td style="background:#1a1a2e;padding:16px;text-align:center;border-radius:0 0 12px 12px">
<p style="color:#6c7a9a;font-size:11px;margin:0">&#9760; Review Reaper — Turn bad reviews into revenue.</p>
</td>
</tr>

</table>
</td></tr>
</table>
</body>
</html>"""
    return html
