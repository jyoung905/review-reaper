"""
Review Reaper - API & HTTP Server

Serves:
- Landing page (/) with audit request
- Admin dashboard (/admin) with full management
- Admin login (/admin/login)
- Admin drafts page (/admin/drafts)
- REST API endpoints (/api/*)

Single port, no external dependencies beyond stdlib + our src modules.
"""

import os
import json
import html
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import stripe
from uuid import uuid4

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "reaper2026")
PORT = int(os.getenv("PORT", "8081"))
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{PORT}")

# Stripe configuration
stripe.api_key = STRIPE_SECRET_KEY
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")  # $97/mo price ID from Stripe dashboard
SUBSCRIPTION_REQUIRED = os.getenv("SUBSCRIPTION_REQUIRED", "false").lower() == "true"

from src.database import (
    init_db, get_connection, get_stats, list_businesses, get_business,
    get_negative_reviews, get_drafts_by_status, update_draft_status,
    save_audit_request, save_response_draft, add_reviews, add_business,
    get_audit_requests, get_complaint_themes, get_review
)
from src.scraper import scrape_and_analyze, find_place_id
from src.response_generator import generate_all_responses
from src.email_sender import send_outreach_email


class ReaperHandler(BaseHTTPRequestHandler):
    """HTTP handler for Review Reaper."""

    def _set_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json(self, data, status=200):
        self.send_response(status)
        self._set_cors()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_html(self, html_str, status=200):
        self.send_response(status)
        self._set_cors()
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html_str.encode('utf-8'))

    def _send_error(self, message, status=400):
        self._send_json({"error": message}, status)

    def _read_body(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            return self.rfile.read(content_length).decode('utf-8')
        return ''

    def _verify_password(self, body=None):
        if body is None:
            body = self._read_body()
        try:
            data = json.loads(body) if isinstance(body, str) else body
            return data.get('password') == ADMIN_PASSWORD
        except:
            return False

    def _require_auth(self, body):
        if not self._verify_password(body):
            self._send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/' or path == '':
            self._send_html(self._landing_page())
        elif path == '/admin':
            self._send_html(self._admin_dashboard())
        elif path == '/admin/login':
            self._send_html(self._admin_login())
        elif path == '/admin/drafts':
            self._send_html(self._admin_drafts())
        elif path == '/health':
            self._send_json({"ok": True, "service": "review-reaper", "ts": datetime.utcnow().isoformat()})
        elif path == '/api/stats':
            self._send_json(get_stats())
        elif path == '/api/businesses':
            self._send_json(list_businesses())
        elif path == '/api/drafts':
            s = params.get('status', [None])[0]
            if s and s not in ('pending', 'approved', 'rejected', 'sent'):
                s = None
            self._send_json(get_drafts_by_status(s))
        elif path == '/api/audit-requests':
            self._send_json(get_audit_requests())
        elif path == '/pricing':
            self._send_html(self._pricing_page())
        elif path == '/subscribe/success':
            self._send_html(self._subscription_success())
        elif path == '/subscribe/cancel':
            self._send_html(self._subscription_cancel())
        else:
            self._send_html(self._landing_page())

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        try:
            if path == '/api/audit':
                self._handle_audit(body)
            elif path == '/api/login':
                self._handle_login(body)
            elif path == '/api/scan':
                if self._require_auth(body):
                    self._handle_scan(body)
            elif path == '/api/draft/approve':
                if self._require_auth(body):
                    self._handle_draft_action(body, 'approved')
            elif path == '/api/draft/reject':
                if self._require_auth(body):
                    self._handle_draft_action(body, 'rejected')
            elif path == '/api/draft/mark-sent':
                if self._require_auth(body):
                    self._handle_draft_action(body, 'sent')
            elif path == '/api/create-checkout-session':
                self._handle_create_checkout_session(body)
            elif path == '/api/send-outreach':
                if self._require_auth(body):
                    self._handle_send_outreach(body)
            elif path == '/api/scrape-businesses':
                if self._require_auth(body):
                    self._handle_scrape_businesses(body)
            elif path == '/api/stripe-webhook':
                self._handle_stripe_webhook(body)
            else:
                self._send_error("Not found", 404)
        except Exception as e:
            self._send_error(str(e))

    def _handle_audit(self, body):
        data = json.loads(body)
        place_id = data.get('place_id', '').strip()
        business_name = data.get('business_name', '').strip()
        email = data.get('email', '').strip()
        if not email:
            self._send_error("Email is required")
            return
        save_audit_request(business_name, place_id, email)
        if place_id:
            from src.pipeline import run_audit_check
            summary = run_audit_check(place_id, email, business_name)
            self._send_json({"success": True, "audit": summary})
        elif business_name:
            found_id = find_place_id(business_name)
            if found_id:
                from src.pipeline import run_audit_check
                summary = run_audit_check(found_id, email, business_name)
                self._send_json({"success": True, "audit": summary})
            else:
                self._send_json({"success": True,
                    "message": "Request saved. We'll find your business and send the audit."})
        else:
            self._send_json({"success": True, "message": "Request saved."})

    def _handle_login(self, body):
        if self._verify_password(body):
            self._send_json({"success": True, "token": "authenticated"})
        else:
            self._send_json({"success": False}, 401)

    def _handle_scan(self, body):
        data = json.loads(body)
        place_id = data.get('place_id', '').strip()
        business_type = data.get('business_type', '')
        if not place_id:
            self._send_error("Place ID is required")
            return
        from src.pipeline import run_full_pipeline
        biz_id = run_full_pipeline(place_id, business_type or None)
        biz = get_business(biz_id)
        neg_count = len(get_negative_reviews(biz_id))
        biz['negative_count'] = neg_count
        self._send_json({"success": True, "business_id": biz_id, "business": biz})

    def _handle_draft_action(self, body, status):
        data = json.loads(body)
        draft_id = data.get('draft_id')
        if not draft_id:
            self._send_error("Draft ID required")
            return
        update_draft_status(draft_id, status)
        self._send_json({"success": True, "status": status})

    # ─── HTML Pages ─────────────────────────────────────────────────────

    def _landing_page(self):
        return self._builtin_landing()

    def _builtin_landing(self):
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Review Reaper — AI-Powered Review Responses</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1a1a2e;line-height:1.6;background:#f8f9ff}}
.container{{max-width:1100px;margin:0 auto;padding:0 24px}}
header{{background:#1a1a2e;color:#fff;padding:16px 0;position:sticky;top:0;z-index:100}}
header .container{{display:flex;justify-content:space-between;align-items:center}}
header .logo{{font-size:1.5rem;font-weight:800;display:flex;align-items:center;gap:8px}}
header .logo span{{color:#e94560}}
header nav a{{color:#ccc;text-decoration:none;margin-left:24px;font-size:.9rem}}
header nav a:hover{{color:#fff}}
.hero{{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);color:#fff;padding:100px 0 80px;text-align:center}}
.hero h1{{font-size:3rem;font-weight:800;margin-bottom:20px;line-height:1.2}}
.hero h1 span{{color:#e94560}}
.hero p{{font-size:1.2rem;color:#a8b2d1;max-width:650px;margin:0 auto 40px}}
.hero .cta-group{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.hero input{{padding:16px 20px;border-radius:8px;border:none;font-size:1rem;width:280px}}
.hero button{{padding:16px 32px;border-radius:8px;border:none;font-size:1rem;font-weight:600;cursor:pointer;background:#e94560;color:#fff;transition:all .2s}}
.hero button:hover{{background:#d63851;transform:translateY(-2px)}}
.hero .trust{{font-size:.85rem;color:#6c7a9a;margin-top:16px}}
.features{{padding:80px 0}}
.features h2{{text-align:center;font-size:2rem;margin-bottom:60px}}
.features-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:32px}}
.feature-card{{background:#fff;padding:32px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.06);transition:all .2s}}
.feature-card:hover{{transform:translateY(-4px);box-shadow:0 8px 30px rgba(0,0,0,.1)}}
.feature-card .icon{{font-size:2rem;margin-bottom:16px}}
.feature-card h3{{font-size:1.2rem;margin-bottom:8px}}
.feature-card p{{color:#6c7a9a;font-size:.9rem}}
.pricing{{background:#fff;padding:80px 0}}
.pricing h2{{text-align:center;font-size:2rem;margin-bottom:12px}}
.pricing .subtitle{{text-align:center;color:#6c7a9a;margin-bottom:48px}}
.pricing-card{{max-width:380px;margin:0 auto;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;border-radius:16px;padding:40px;text-align:center}}
.pricing-card .price{{font-size:3rem;font-weight:800;margin:16px 0}}
.pricing-card .price span{{font-size:1.2rem;color:#a8b2d1}}
.pricing-card ul{{list-style:none;margin:24px 0;text-align:left}}
.pricing-card ul li{{padding:8px 0;border-bottom:1px solid rgba(255,255,255,.1)}}
.pricing-card ul li::before{{content:"\\u2713 ";color:#e94560;font-weight:700}}
.pricing-card .cta{{display:block;padding:16px;background:#e94560;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;margin-top:24px}}
.pricing-card .cta:hover{{background:#d63851}}
.faq{{padding:80px 0}}
.faq h2{{text-align:center;font-size:2rem;margin-bottom:48px}}
.faq-grid{{max-width:700px;margin:0 auto}}
.faq-item{{padding:20px 0;border-bottom:1px solid #e2e8f0}}
.faq-item h4{{font-size:1.05rem;margin-bottom:6px}}
.faq-item p{{color:#6c7a9a;font-size:.9rem}}
footer{{background:#1a1a2e;color:#6c7a9a;padding:32px 0;text-align:center;font-size:.85rem}}
footer a{{color:#a8b2d1;text-decoration:none}}
.toast{{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a1a2e;color:#fff;padding:16px 24px;border-radius:8px;display:none;z-index:1000;font-size:.9rem;box-shadow:0 4px 20px rgba(0,0,0,.2)}}
.toast.show{{display:block}}
@media(max-width:768px){{.hero h1{{font-size:2rem}}.hero input{{width:100%}}.hero .cta-group{{flex-direction:column;align-items:center}}}}
</style>
</head>
<body>
<header><div class="container">
<div class="logo">&#9760; <span>Review</span> Reaper</div>
<nav><a href="#features">Features</a><a href="#pricing">Pricing</a><a href="#faq">FAQ</a><a href="/admin">Dashboard</a></nav>
</div></header>
<section class="hero"><div class="container">
<h1>Turn Bad Reviews Into <span>Revenue</span></h1>
<p>AI-powered review responses that bring customers back. Automatically detect negative reviews, generate professional replies, and offer recovery incentives.</p>
<form id="audit-form" class="cta-group" onsubmit="return submitAudit(event)">
<input type="email" id="audit-email" placeholder="Your email address" required>
<input type="text" id="audit-business" placeholder="Business name (optional)">
<button type="submit">Get Your Free Review Audit &rarr;</button></form>
<p class="trust">&#128274; No credit card required &bull; Free audit report in minutes</p>
</div></section>
<section class="features" id="features"><div class="container">
<h2>Stop Ignoring Bad Reviews. Start Converting Them.</h2>
<div class="features-grid">
<div class="feature-card"><div class="icon">&#128269;</div><h3>Auto-Detect Bad Reviews</h3><p>Enter your Google Place ID and we instantly pull every negative review (rating &le; 3).</p></div>
<div class="feature-card"><div class="icon">&#129302;</div><h3>AI Response Drafts</h3><p>Each negative review gets a professional, context-aware response. Apologizes, addresses the issue, offers a resolution path.</p></div>
<div class="feature-card"><div class="icon">&#127873;</div><h3>Recovery Offers</h3><p>Generate personalized recovery offers &mdash; discounts, free services, priority scheduling &mdash; tailored to the complaint type.</p></div>
<div class="feature-card"><div class="icon">&#128202;</div><h3>Theme Analytics</h3><p>See what customers actually complain about: wait times, pricing, service quality. Know your weak spots instantly.</p></div>
<div class="feature-card"><div class="icon">&#10004;</div><h3>Manual Review Only</h3><p>Every response requires your approval. We draft, you decide. No auto-posting &mdash; your reputation, your voice.</p></div>
<div class="feature-card"><div class="icon">&#127760;</div><h3>Multi-Location Ready</h3><p>Manage all locations from one dashboard. Track trends across your portfolio.</p></div>
</div></div></section>
<section class="pricing" id="pricing"><div class="container">
<h2>Simple Pricing</h2><p class="subtitle">One plan. Everything you need.</p>
<div class="pricing-card">
<div class="price">$97<span>/mo</span></div>
<ul>
<li>Unlimited businesses and locations</li>
<li>AI response drafts for every negative review</li>
<li>Recovery offer generation</li>
<li>Complaint theme analytics</li>
<li>Approve/reject workflow</li>
<li>Email audit reports</li>
</ul>
<a href="/pricing" class="cta">Subscribe Now &rarr;</a>
</div></div></section>
<section class="faq" id="faq"><div class="container">
<h2>Frequently Asked Questions</h2><div class="faq-grid">
<div class="faq-item"><h4>Do you auto-post responses to Google?</h4><p>No. Every response requires your manual approval. We draft, you decide.</p></div>
<div class="faq-item"><h4>What if I don\'t know my Place ID?</h4><p>Enter your business name and we\'ll look it up during the free audit.</p></div>
<div class="faq-item"><h4>Can I customize the response tone?</h4><p>Responses adapt to your business type (auto shop, dental, restaurant) and you can edit drafts before approving.</p></div>
<div class="faq-item"><h4>How many businesses can I track?</h4><p>Unlimited. Track 50 franchise locations or property portfolios under one dashboard.</p></div>
<div class="faq-item"><h4>Do I need a Google Maps API key?</h4><p>Only for live data. Our dry-run mode works with sample data so you can test everything first.</p></div>
<div class="faq-item"><h4>Can I cancel anytime?</h4><p>Yes. No contracts, month-to-month, cancel anytime.</p></div>
</div></div></section>
<footer><div class="container"><p>&#9760; Review Reaper &mdash; &copy; 2026. Turn those reviews into revenue.</p><p><a href="/admin">Admin Dashboard</a></p></div></footer>
<div id="toast" class="toast"></div>
<script>
function showToast(m,e){{var t=document.getElementById("toast");t.textContent=m;t.style.background=e?"#d32f2f":"#1a1a2e";t.classList.add("show");setTimeout(function(){{t.classList.remove("show")}},5000)}}
async function submitAudit(e){{e.preventDefault();var em=document.getElementById("audit-email").value,bz=document.getElementById("audit-business").value,btn=e.target.querySelector("button");btn.disabled=true;btn.textContent="Submitting...";try{{var r=await fetch("/api/audit",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{email:em,business_name:bz}})}}),d=await r.json();if(d.success){{var msg="Audit request submitted!";if(d.audit){{msg="&#10004; Audit complete! "+d.audit.negative_reviews+" negative reviews found."}}showToast(msg);btn.textContent="&#10004; Submitted!";setTimeout(function(){{btn.textContent="Get Your Free Review Audit &rarr;";btn.disabled=false}},3000)}}else{{throw new Error(d.error||"Error")}}}}catch(err){{showToast("Error: "+err.message,true);btn.disabled=false;btn.textContent="Get Your Free Review Audit &rarr;"}}return false}}
</script>
</body>
</html>'''

    def _admin_login(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Review Reaper - Admin</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#1a1a2e;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh}
.login{background:#16213e;padding:48px;border-radius:16px;width:380px;max-width:90vw}
.login h1{font-size:1.5rem;margin-bottom:24px;text-align:center}
.login h1 span{color:#e94560}
.login input{width:100%;padding:14px;border-radius:8px;border:1px solid #333;background:#1a1a2e;color:#fff;font-size:1rem;margin-bottom:16px}
.login button{width:100%;padding:14px;background:#e94560;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer}
.login .error{color:#e94560;font-size:.85rem;text-align:center;margin-top:12px;display:none}
</style>
</head>
<body>
<div class="login">
<h1>&#9760; <span>Review</span> Reaper</h1>
<form id="login-form" onsubmit="return doLogin(event)">
<input type="password" id="password" placeholder="Enter admin password" required>
<button type="submit">Sign In</button>
<p id="error" class="error">Wrong password</p>
</form>
</div>
<script>
async function doLogin(e){e.preventDefault();var pw=document.getElementById("password").value;try{var r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:pw})}),d=await r.json();if(d.success){window.location.href="/admin"}else{document.getElementById("error").style.display="block"}}catch(err){document.getElementById("error").style.display="block"}return false}
</script>
</body>
</html>'''

    def _admin_dashboard(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Review Reaper - Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9ff;color:#1a1a2e}
.main{max-width:1200px;margin:0 auto;padding:32px 24px}
h1{font-size:1.6rem;margin-bottom:24px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:32px}
.stat-card{background:#fff;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.04)}
.stat-card .num{font-size:2rem;font-weight:800;color:#e94560;margin-bottom:4px}
.stat-card .label{color:#6c7a9a;font-size:.85rem}
.card{background:#fff;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.04);padding:24px;margin-bottom:24px}
.card h2{font-size:1.1rem;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{padding:10px 8px;text-align:left;border-bottom:1px solid #e2e8f0}
th{color:#6c7a9a;font-weight:600;font-size:.8rem;text-transform:uppercase}
tr:hover{background:#f8f9ff}
.btn{display:inline-block;padding:8px 16px;border-radius:6px;border:none;font-size:.85rem;font-weight:600;cursor:pointer;text-decoration:none;margin:2px;transition:all .15s}
.btn-primary{background:#e94560;color:#fff}.btn-primary:hover{background:#d63851}
.btn-outline{background:transparent;border:1px solid #e2e8f0;color:#1a1a2e}.btn-outline:hover{background:#f0f0f5}
.btn-sm{padding:4px 10px;font-size:.8rem}
.btn-success{background:#10b981;color:#fff}.btn-success:hover{background:#059669}
.btn-danger{background:#ef4444;color:#fff}.btn-danger:hover{background:#dc2626}
.badge{padding:3px 8px;border-radius:6px;font-size:.75rem;font-weight:600}
.badge-pending{background:#fef3c7;color:#92400e}.badge-approved{background:#d1fae5;color:#065f46}
.badge-rejected{background:#fee2e2;color:#991b1b}.badge-sent{background:#dbeafe;color:#1e40af}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;background:#eef2ff;color:#4338ca;margin:2px}
.scan-form{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;align-items:end}
.scan-form input,.scan-form select{padding:10px 14px;border-radius:6px;border:1px solid #e2e8f0;font-size:.9rem;background:#fff}
.scan-form input[type="text"]{flex:1;min-width:200px}
.nav-bar{display:flex;gap:16px;margin-bottom:24px;align-items:center;flex-wrap:wrap}
.nav-bar a{padding:8px 16px;border-radius:6px;text-decoration:none;font-size:.9rem;font-weight:600;color:#6c7a9a}
.nav-bar a:hover,.nav-bar a.active{background:#e94560;color:#fff}
.toast{position:fixed;bottom:24px;right:24px;background:#1a1a2e;color:#fff;padding:12px 20px;border-radius:8px;display:none;z-index:1000;font-size:.85rem}
.toast.show{display:block}
</style>
</head>
<body>
<div class="main">
<div class="nav-bar">
<a href="/admin" class="active">&#128202; Dashboard</a>
<a href="/admin/drafts">&#9997; Pending Drafts</a>
<a href="/" style="margin-left:auto;color:#e94560">&larr; Back to Site</a>
</div>
<h1>&#9760; Review Reaper Dashboard</h1>
<div id="stats" class="stats-grid"></div>
<div class="card">
<h2>&#128269; Scan New Business</h2>
<form class="scan-form" onsubmit="return scanBiz(event)">
<input type="text" id="scan-place-id" placeholder="Google Place ID (e.g., ChIJN1t_tDeuEmsRUsoyG83frY4)" required>
<select id="scan-type">
<option value="">Auto-detect</option>
<option value="auto_shop">Auto Shop</option>
<option value="dental">Dental</option>
<option value="restaurant">Restaurant</option>
<option value="property_management">Property Mgmt</option>
<option value="medical">Medical</option>
<option value="general">General</option>
</select>
<button type="submit" class="btn btn-primary">Scan &amp; Generate &rarr;</button>
</form>
<div id="scan-result" style="display:none;padding:12px;border-radius:6px;background:#d1fae5;color:#065f46;font-size:.85rem"></div>
</div>
<div class="card"><h2>&#127962; Tracked Businesses</h2><div id="biz-list"></div></div>
<div class="card"><h2>&#9997; Recent Pending Drafts</h2><div id="drafts-list"></div></div>
</div>
<div id="toast" class="toast"></div>
<script>
var PW=sessionStorage.getItem('rr_pw');
if(!PW){var pw=prompt('Admin password:');if(pw){PW=pw;sessionStorage.setItem('rr_pw',pw)}else{window.location.href='/admin/login'}}

function toast(m,e){var t=document.getElementById('toast');t.textContent=m;t.style.background=e?'#d32f2f':'#1a1a2e';t.classList.add('show');setTimeout(function(){t.classList.remove('show')},4000)}

async function api(m,p,b){var o={method:m,headers:{'Content-Type':'application/json'}};if(m!=='GET'){o.body=JSON.stringify(Object.assign({password:PW},b||{}))}var r=await fetch(p,o);return r.json()}

async function loadDash(){try{
var st=await api('GET','/api/stats');
document.getElementById('stats').innerHTML=
'<div class="stat-card"><div class="num">'+(st.total_businesses||0)+'</div><div class="label">Businesses</div></div>'+
'<div class="stat-card"><div class="num">'+(st.negative_reviews||0)+'</div><div class="label">Negative Reviews</div></div>'+
'<div class="stat-card"><div class="num">'+(st.pending_drafts||0)+'</div><div class="label">Pending Drafts</div></div>'+
'<div class="stat-card"><div class="num">'+(st.sent_drafts||0)+'</div><div class="label">Responses Sent</div></div>'+
'<div class="stat-card"><div class="num">'+(st.pending_audits||0)+'</div><div class="label">Audit Requests</div></div>';
var biz=await api('GET','/api/businesses');
var bh='';
if(biz&&biz.length){bh='<table><thead><tr><th>Name</th><th>Type</th><th>Rating</th><th>Negative</th><th>Pending</th></tr></thead><tbody>';
for(var i=0;i<biz.length;i++){var b=biz[i];bh+='<tr><td>'+htmlEsc(b.name)+'</td><td>'+b.business_type+'</td><td>'+(b.rating||'-')+'</td><td>'+b.negative_count+'</td><td>'+(b.pending_responses||0)+'</td></tr>'}
bh+='</tbody></table>'}else{bh='<p style="color:#6c7a9a;font-size:.9rem">No businesses tracked yet. Scan one above!</p>'}
document.getElementById('biz-list').innerHTML=bh;
var dr=await api('GET','/api/drafts?status=pending');
var dh='';
if(dr&&dr.length){for(var i=0;i<Math.min(dr.length,5);i++){var d=dr[i];var themes='';try{var t=JSON.parse(d.complaint_themes);if(t&&t.length){themes=t.map(function(x){return '<span class="tag">'+x.replace(/_/g,' ')+'</span>'}).join(' ')}}catch(e){}
dh+='<div class="draft-card"><div class="header"><strong>'+htmlEsc(d.business_name)+'</strong> <span class="badge badge-pending">'+d.rating+'&#9733;</span></div>'+
'<div style="color:#6c7a9a;font-size:.85rem;margin-bottom:8px">'+htmlEsc(d.review_text).substring(0,120)+(d.review_text.length>120?'...':'')+'</div>'+themes+
'<div class="actions" style="margin-top:8px">'+
'<button class="btn btn-success btn-sm" onclick="approveDraft('+d.id+')">Approve</button>'+
'<button class="btn btn-danger btn-sm" onclick="rejectDraft('+d.id+')">Reject</button>'+
'</div></div>'}
dh+='<div style="margin-top:12px"><a href="/admin/drafts" class="btn btn-outline btn-sm">View All Drafts &rarr;</a></div>'}else{dh='<p style="color:#6c7a9a;font-size:.9rem">No pending drafts. Scan a business to generate some!</p>'}
document.getElementById('drafts-list').innerHTML=dh;
}catch(e){toast('Error loading dashboard: '+e.message,true)}}

function htmlEsc(s){if(!s)return '';return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

async function scanBiz(e){e.preventDefault();var pid=document.getElementById('scan-place-id').value,typ=document.getElementById('scan-type').value;var btn=e.target.querySelector('button');btn.disabled=true;btn.textContent='Scanning...';try{
var r=await api('POST','/api/scan',{place_id:pid,business_type:typ});if(r.success){var sr=document.getElementById('scan-result');sr.style.display='block';sr.textContent='&#10004; Scanned '+r.business.name+' - '+r.business.negative_count+' negative reviews found!';loadDash()}else{toast(r.error||'Scan failed',true)}
}catch(e){toast('Error: '+e.message,true)}btn.disabled=false;btn.textContent='Scan &amp; Generate &rarr;';return false}

async function approveDraft(id){try{var r=await api('POST','/api/draft/approve',{draft_id:id});if(r.success){toast('Draft approved!');loadDash()}else{toast('Failed',true)}}catch(e){toast('Error',true)}}
async function rejectDraft(id){try{var r=await api('POST','/api/draft/reject',{draft_id:id});if(r.success){toast('Draft rejected');loadDash()}else{toast('Failed',true)}}catch(e){toast('Error',true)}}
loadDash();
</script>
</body>
</html>'''

    def _admin_drafts(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Review Reaper - Drafts</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9ff;color:#1a1a2e}
.main{max-width:1000px;margin:0 auto;padding:32px 24px}
h1{font-size:1.6rem;margin-bottom:24px}
.nav-bar{display:flex;gap:16px;margin-bottom:24px}
.nav-bar a{padding:8px 16px;border-radius:6px;text-decoration:none;font-size:.9rem;font-weight:600;color:#6c7a9a}
.nav-bar a:hover,.nav-bar a.active{background:#e94560;color:#fff}
.filter-bar{display:flex;gap:8px;margin-bottom:24px}
.filter-btn{padding:6px 14px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;font-size:.85rem;color:#6c7a9a}
.filter-btn.active{background:#e94560;color:#fff;border-color:#e94560}
.draft-card{border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin-bottom:12px;background:#fff}
.draft-card .header{display:flex;justify-content:space-between;align-items:start;margin-bottom:8px;flex-wrap:wrap;gap:8px}
.draft-card .review-text{color:#6c7a9a;font-size:.85rem;margin-bottom:8px;padding:8px;background:#f8f9ff;border-radius:4px}
.draft-card .response-text{font-size:.85rem;margin-bottom:8px;padding:8px;background:#f0fdf4;border-radius:4px;border-left:3px solid #10b981}
.draft-card .offer-text{font-size:.85rem;margin-bottom:8px;padding:8px;background:#fff7ed;border-radius:4px;border-left:3px solid #f59e0b}
.draft-card .actions{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
.badge{padding:3px 8px;border-radius:6px;font-size:.75rem;font-weight:600}
.badge-pending{background:#fef3c7;color:#92400e}.badge-approved{background:#d1fae5;color:#065f46}
.badge-rejected{background:#fee2e2;color:#991b1b}.badge-sent{background:#dbeafe;color:#1e40af}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.75rem;background:#eef2ff;color:#4338ca;margin:2px}
.btn{padding:6px 14px;border-radius:6px;border:none;font-size:.8rem;font-weight:600;cursor:pointer;transition:all .15s}
.btn-success{background:#10b981;color:#fff}.btn-success:hover{background:#059669}
.btn-danger{background:#ef4444;color:#fff}.btn-danger:hover{background:#dc2626}
.btn-outline{background:transparent;border:1px solid #e2e8f0;color:#1a1a2e}
.btn-sent{background:#3b82f6;color:#fff}
.toast{position:fixed;bottom:24px;right:24px;background:#1a1a2e;color:#fff;padding:12px 20px;border-radius:8px;display:none;z-index:1000;font-size:.85rem}
.toast.show{display:block}
.empty{color:#6c7a9a;font-size:.9rem;text-align:center;padding:48px}
</style>
</head>
<body>
<div class="main">
<div class="nav-bar">
<a href="/admin">&#128202; Dashboard</a>
<a href="/admin/drafts" class="active">&#9997; Drafts</a>
<a href="/" style="margin-left:auto;color:#e94560">&larr; Back</a>
</div>
<h1>&#9997; Response Drafts</h1>
<div class="filter-bar" id="filters">
<button class="filter-btn active" onclick="loadDrafts(null)">All</button>
<button class="filter-btn" onclick="loadDrafts('pending')">Pending</button>
<button class="filter-btn" onclick="loadDrafts('approved')">Approved</button>
<button class="filter-btn" onclick="loadDrafts('rejected')">Rejected</button>
<button class="filter-btn" onclick="loadDrafts('sent')">Sent</button>
</div>
<div id="drafts-container"></div>
</div>
<div id="toast" class="toast"></div>
<script>
var PW=sessionStorage.getItem('rr_pw');
if(!PW){var pw=prompt('Admin password:');if(pw){PW=pw;sessionStorage.setItem('rr_pw',pw)}else{window.location.href='/admin/login'}}
function toast(m,e){var t=document.getElementById('toast');t.textContent=m;t.style.background=e?'#d32f2f':'#1a1a2e';t.classList.add('show');setTimeout(function(){t.classList.remove('show')},4000)}
async function api(m,p,b){var o={method:m,headers:{'Content-Type':'application/json'}};if(m!=='GET'){o.body=JSON.stringify(Object.assign({password:PW},b||{}))}var r=await fetch(p,o);return r.json()}
function htmlEsc(s){if(!s)return '';return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

async function loadDrafts(status){
document.querySelectorAll('.filter-btn').forEach(function(b){b.classList.remove('active')});
event&&event.target&&event.target.classList.add('active');
var url='/api/drafts';
if(status)url+='?status='+status;
try{
var dr=await api('GET',url);
var h='';
if(!dr||!dr.length){h='<div class="empty">No drafts found</div>'}
else{for(var i=0;i<dr.length;i++){var d=dr[i];
var themes='';try{var t=JSON.parse(d.complaint_themes);if(t&&t.length){themes=t.map(function(x){return '<span class="tag">'+htmlEsc(x.replace(/_/g,' '))+'</span>'}).join(' ')}}catch(e){}
var statusClass='badge-'+d.status;
h+='<div class="draft-card"><div class="header"><strong>'+htmlEsc(d.business_name)+'</strong> <div><span class="badge '+statusClass+'">'+d.status+'</span> <span>'+d.rating+'&#9733;</span></div></div>';
h+='<div><strong>Customer:</strong> '+htmlEsc(d.reviewer_name)+'</div>';
h+='<div class="review-text">'+htmlEsc(d.review_text)+'</div>'+themes;
h+='<div class="response-text"><strong>Response:</strong> '+htmlEsc(d.ai_generated_text)+'</div>';
if(d.recovery_offer){h+='<div class="offer-text"><strong>Recovery Offer:</strong> '+htmlEsc(d.recovery_offer)+'</div>'}
if(d.status=='pending'){h+='<div class="actions"><button class="btn btn-success" onclick="act('+d.id+',\'approve\')">&#10004; Approve</button><button class="btn btn-danger" onclick="act('+d.id+',\'reject\')">&#10008; Reject</button></div>'}
else if(d.status=='approved'){h+='<div class="actions"><button class="btn btn-sent" onclick="act('+d.id+',\'mark-sent\')">Mark as Sent</button><button class="btn btn-danger" onclick="act('+d.id+',\'reject\')">Reject</button></div>'}
h+='</div>'}}
document.getElementById('drafts-container').innerHTML=h;
}catch(e){toast('Error: '+e.message,true)}}

async function act(id,action){
try{var r=await api('POST','/api/draft/'+action,{draft_id:id});if(r.success){toast('Draft '+action+'d!');loadDrafts()}else{toast('Failed',true)}}catch(e){toast('Error',true)}}

loadDrafts('pending');
</script>
</body>
</html>'''

    # ─── Email Outreach ─────────────────────────────────────────────────────

    def _handle_send_outreach(self, body):
        """Send a cold outreach email via SendGrid.

        Request body:
        {
            "recipient_email": "owner@business.com",
            "business_name": "Business Name",
            "reviews": [
                {
                    "reviewer_name": "John D.",
                    "rating": 2,
                    "text": "Review text here...",
                    "ai_generated_text": "AI response...",
                    "complaint_themes": ["wait_times"],
                    "recovery_offer": "Optional recovery offer"
                },
                ...
            ]
        }
        """
        try:
            data = json.loads(body)

            recipient_email = data.get('recipient_email', '').strip()
            business_name = data.get('business_name', '').strip()
            reviews = data.get('reviews', [])

            if not recipient_email:
                self._send_error("recipient_email is required")
                return
            if not business_name:
                self._send_error("business_name is required")
                return
            if not reviews:
                self._send_error("reviews array is required with at least one review")
                return

            result = send_outreach_email(recipient_email, business_name, reviews)

            if result.get("success"):
                print(f"\n✉️  Outreach email sent to {recipient_email} for {business_name}")
                self._send_json(result)
            else:
                self._send_error(result.get("message", "Failed to send email"), 500)
        except json.JSONDecodeError:
            self._send_error("Invalid JSON body")
        except Exception as e:
            self._send_error(str(e), 500)

    # ─── Scrape Businesses (Seed / Structure) ───────────────────────────────

    def _handle_scrape_businesses(self, body):
        """Seed/stub endpoint for scraping businesses from Google Maps.

        Request body:
        {
            "location": "Toronto, ON",
            "business_type": "auto_shop",
            "results": [  // optional pre-seeded data
                {
                    "name": "Business Name",
                    "address": "123 Street",
                    "place_id": "ChIJ...",
                    "rating": 4.2,
                    "review_count": 87
                }
            ]
        }

        Currently accepts either manual seed data or returns a placeholder.
        Full Google Maps scraping integration can be added later.
        """
        try:
            data = json.loads(body)
            location = data.get('location', '').strip()
            business_type = data.get('business_type', '').strip()
            seed_results = data.get('results', [])

            if not location:
                self._send_error("location is required")
                return
            if not business_type:
                self._send_error("business_type is required")
                return

            if seed_results:
                # Seed mode: accept pre-provided business data
                for biz in seed_results:
                    if biz.get('place_id'):
                        # Add to database
                        add_business(
                            name=biz.get('name', ''),
                            place_id=biz['place_id'],
                            address=biz.get('address', ''),
                            business_type=business_type,
                            rating=biz.get('rating'),
                            total_reviews=biz.get('review_count', 0)
                        )
                self._send_json({
                    "success": True,
                    "message": f"Seeded {len(seed_results)} businesses",
                    "businesses": seed_results
                })
            else:
                # Placeholder: tell user how to use this endpoint
                self._send_json({
                    "success": True,
                    "message": "Google Maps scraping placeholder. Pass 'results' array with seed data to add businesses, or integrate a real Maps scraper.",
                    "query": {
                        "location": location,
                        "business_type": business_type
                    },
                    "businesses": [],
                    "hint": "Add 'results' field with [{name, address, place_id, rating, review_count}] to seed businesses into the database."
                })
        except json.JSONDecodeError:
            self._send_error("Invalid JSON body")
        except Exception as e:
            self._send_error(str(e), 500)

    # ─── Stripe Integration ────────────────────────────────────────────────

    def _handle_create_checkout_session(self, body):
        """Create a Stripe Checkout Session for $97/mo subscription."""
        try:
            data = json.loads(body) if body else {}
            
            # Create a unique session ID for tracking
            session_id = str(uuid4())
            
            # If we have a Stripe price ID, create a real checkout session
            if STRIPE_PRICE_ID and STRIPE_SECRET_KEY:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price': STRIPE_PRICE_ID,
                        'quantity': 1,
                    }],
                    mode='subscription',
                    success_url=f"{BASE_URL}/subscribe/success?session_id={{CHECKOUT_SESSION_ID}}",
                    cancel_url=f"{BASE_URL}/subscribe/cancel",
                    metadata={
                        'plan': 'monthly',
                        'price': '97',
                    }
                )
                self._send_json({
                    "success": True,
                    "url": checkout_session.url,
                    "session_id": checkout_session.id
                })
            else:
                # No Stripe configured — return a simulated success
                self._send_json({
                    "success": True,
                    "url": f"{BASE_URL}/subscribe/success?session_id={session_id}",
                    "session_id": session_id,
                    "test_mode": True,
                    "message": "Payment simulation mode. Set STRIPE_PRICE_ID and STRIPE_SECRET_KEY in .env for real payments."
                })
        except Exception as e:
            self._send_error(f"Stripe error: {str(e)}", 500)

    def _handle_stripe_webhook(self, body):
        """Handle Stripe webhook events (e.g., subscription completion)."""
        try:
            payload = body
            sig_header = self.headers.get('Stripe-Signature')
            
            if STRIPE_WEBHOOK_SECRET and sig_header:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, STRIPE_WEBHOOK_SECRET
                )
            else:
                # No webhook secret — parse directly for testing
                event = json.loads(payload)
            
            # Handle the event
            event_type = event.get('type', 'unknown')
            
            if event_type == 'checkout.session.completed':
                session = event['data']['object']
                customer_email = session.get('customer_details', {}).get('email', '')
                subscription_id = session.get('subscription', '')
                print(f"\n🎉 New subscription! Email: {customer_email}, Sub: {subscription_id}")
                # Store subscription in settings
                conn = get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (f"subscriber_{customer_email}", json.dumps({
                        "email": customer_email,
                        "subscription_id": subscription_id,
                        "active": True,
                        "created_at": datetime.utcnow().isoformat()
                    }))
                )
                conn.commit()
                conn.close()
            
            self._send_json({"received": True, "event": event_type})
        except Exception as e:
            self._send_error(f"Webhook error: {str(e)}", 400)

    def _pricing_page(self):
        """Full pricing page with Stripe checkout button."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Pricing - Review Reaper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9ff;color:#1a1a2e;min-height:100vh;display:flex;flex-direction:column}
header{background:#1a1a2e;color:#fff;padding:16px 0}
header .container{max-width:1100px;margin:0 auto;padding:0 24px;display:flex;justify-content:space-between;align-items:center}
header .logo{font-size:1.5rem;font-weight:800;display:flex;align-items:center;gap:8px}
header .logo span{color:#e94560}
header nav a{color:#ccc;text-decoration:none;margin-left:24px;font-size:.9rem}
header nav a:hover{color:#fff}
.main{flex:1;display:flex;align-items:center;justify-content:center;padding:48px 24px}
.pricing-card{max-width:420px;width:100%;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;border-radius:16px;padding:48px 40px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.15)}
.pricing-card .plan-name{font-size:1.2rem;color:#a8b2d1;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px}
.pricing-card .price{font-size:3.5rem;font-weight:800;margin:16px 0 4px}
.pricing-card .price span{font-size:1.2rem;color:#a8b2d1;font-weight:400}
.pricing-card .period{color:#6c7a9a;font-size:.9rem;margin-bottom:32px}
.pricing-card ul{list-style:none;margin:24px 0 32px;text-align:left}
.pricing-card ul li{padding:10px 0;border-bottom:1px solid rgba(255,255,255,.08);display:flex;align-items:center;gap:10px}
.pricing-card ul li::before{content:"\u2713";color:#10b981;font-weight:700}
.pricing-card .subscribe-btn{display:block;width:100%;padding:16px;background:#e94560;color:#fff;border:none;border-radius:8px;font-size:1.1rem;font-weight:600;cursor:pointer;transition:all .2s}
.pricing-card .subscribe-btn:hover{background:#d63851;transform:translateY(-2px)}
.pricing-card .subscribe-btn:disabled{opacity:.6;cursor:not-allowed;transform:none}
.pricing-card .guarantee{font-size:.8rem;color:#6c7a9a;margin-top:16px}
.pricing-card .test-mode{background:rgba(234,179,8,.15);color:#fbbf24;padding:8px 12px;border-radius:6px;font-size:.8rem;margin-top:16px}
.toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1a1a2e;color:#fff;padding:16px 24px;border-radius:8px;display:none;z-index:1000;font-size:.9rem;box-shadow:0 4px 20px rgba(0,0,0,.2)}
.toast.show{display:block}
</style>
</head>
<body>
<header><div class="container">
<div class="logo">&#9760; <span>Review</span> Reaper</div>
<nav><a href="/">Home</a><a href="/admin">Dashboard</a></nav>
</div></header>
<div class="main">
<div class="pricing-card">
<div class="plan-name">Professional</div>
<div class="price">$97<span>/mo</span></div>
<div class="period">Billed monthly &bull; Cancel anytime</div>
<ul>
<li>Unlimited businesses &amp; locations</li>
<li>AI response drafts for every negative review</li>
<li>Recovery offer generation</li>
<li>Complaint theme analytics</li>
<li>Approve/reject workflow</li>
<li>Email audit reports</li>
</ul>
<button class="subscribe-btn" id="subscribe-btn" onclick="startCheckout()">Subscribe Now &rarr;</button>
<div class="guarantee">&#128274; 30-day money-back guarantee</div>
<div id="test-mode-badge" class="test-mode" style="display:none">&#9888; Test mode — no real payment processed</div>
</div>
</div>
<div id="toast" class="toast"></div>
<script>
function showToast(m,e){var t=document.getElementById("toast");t.textContent=m;t.style.background=e?"#d32f2f":"#1a1a2e";t.classList.add("show");setTimeout(function(){t.classList.remove("show")},5000)}
async function startCheckout(){var btn=document.getElementById("subscribe-btn");btn.disabled=true;btn.textContent="Redirecting...";try{var r=await fetch("/api/create-checkout-session",{method:"POST",headers:{"Content-Type":"application/json"}}),d=await r.json();if(d.success){if(d.test_mode){document.getElementById("test-mode-badge").style.display="block"}window.location.href=d.url}else{showToast("Error: "+(d.error||"Failed"),true);btn.disabled=false;btn.textContent="Subscribe Now &rarr;"}}catch(e){showToast("Connection error: "+e.message,true);btn.disabled=false;btn.textContent="Subscribe Now &rarr;"}}
</script>
</body>
</html>'''

    def _subscription_success(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Welcome - Review Reaper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9ff;color:#1a1a2e;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border-radius:16px;padding:48px;text-align:center;max-width:480px;width:90%;box-shadow:0 10px 40px rgba(0,0,0,.08)}
.icon{font-size:3rem;margin-bottom:16px}
h1{font-size:1.8rem;margin-bottom:12px}
p{color:#6c7a9a;margin-bottom:24px;line-height:1.6}
.btn{display:inline-block;padding:14px 32px;background:#e94560;color:#fff;text-decoration:none;border-radius:8px;font-weight:600}
.btn:hover{background:#d63851}
</style>
</head>
<body>
<div class="card">
<div class="icon">&#9989;</div>
<h1>Welcome to Review Reaper!</h1>
<p>Your subscription is active. You now have full access to AI-powered review management for all your businesses.</p>
<a href="/admin" class="btn">Go to Dashboard &rarr;</a>
</div>
</body>
</html>'''

    def _subscription_cancel(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Checkout Canceled - Review Reaper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f8f9ff;color:#1a1a2e;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#fff;border-radius:16px;padding:48px;text-align:center;max-width:480px;width:90%;box-shadow:0 10px 40px rgba(0,0,0,.08)}
.icon{font-size:3rem;margin-bottom:16px}
h1{font-size:1.8rem;margin-bottom:12px}
p{color:#6c7a9a;margin-bottom:24px;line-height:1.6}
.btn{display:inline-block;padding:14px 32px;background:#1a1a2e;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;margin:4px}
.btn-primary{background:#e94560}
</style>
</head>
<body>
<div class="card">
<div class="icon">&#128542;</div>
<h1>Checkout Canceled</h1>
<p>No worries — your subscription hasn't been charged. You can come back anytime to get started.</p>
<a href="/pricing" class="btn btn-primary">Try Again</a>
<a href="/" class="btn">Back to Home</a>
</div>
</body>
</html>'''


def main():
    """Initialize DB and start the HTTP server."""
    print("☠️  Review Reaper — AI Review Response System")
    print("=" * 50)
    
    # Initialize database
    init_db()
    
    # Determine host
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🌐 Landing page:    http://localhost:{PORT}")
    print(f"🔐 Admin login:     http://localhost:{PORT}/admin/login")
    print(f"📊 Admin dashboard: http://localhost:{PORT}/admin")
    print(f"⚙️  Dry-run mode:    {os.getenv('DRY_RUN', 'true')}")
    print(f"🔑 Admin password:  {ADMIN_PASSWORD}")
    print()
    
    server = HTTPServer((host, PORT), ReaperHandler)
    print(f"🚀 Server running on http://{host}:{PORT}")
    print("   Press Ctrl+C to stop.")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
