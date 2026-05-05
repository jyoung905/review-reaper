# ☠️ Review Reaper

**AI-powered Google review response system.** Automatically finds negative reviews, analyzes common complaints, and generates professional response drafts with recovery offers.

**Target market:** Multi-location businesses (franchises, dental chains, auto shops, property management)
**Price point:** $97/mo

## Quick Start (Local)

```bash
cd /Users/jamesyoung/.openclaw/workspace/businesses/review-reaper
./start.sh
```

This will:
1. Create a Python virtual environment
2. Install dependencies
3. Create `.env` from template (edit to add your API keys)
4. Start the server at http://localhost:9090

## Deployment

### Option 1: Railway (Recommended — Fastest)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login (opens browser)
railway login

# Deploy from this directory
railway init --name review-reaper"
railway up

# After deploy, set env vars in Railway dashboard:
# - ADMIN_PASSWORD=reaper2026
# - OPENAI_API_KEY=<your key>
# - DRY_RUN=true|false
# - BASE_URL=https://your-app.up.railway.app
```

### Option 2: Render (Free tier)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service → Connect repo
3. Render will auto-detect `render.yaml` blueprint
4. Set env vars in Render dashboard

### Option 3: Docker

```bash
docker compose up -d
```

## Routes

| Path | Description |
|------|-------------|
| `/` | Landing page with free audit CTA |
| `/pricing` | Pricing page with Stripe checkout |
| `/subscribe/success` | Post-subscription success page |
| `/subscribe/cancel` | Post-subscription cancel page |
| `/admin` | Admin dashboard (password-gated) |
| `/admin/login` | Admin login page |
| `/admin/drafts` | Full draft management page |
| `/api/stats` | Dashboard statistics |
| `/api/businesses` | List all tracked businesses |
| `/api/drafts?status=pending` | List drafts (filter by status) |
| `/api/login` | POST: authenticate (returns token) |
| `/api/scan` | POST: run full pipeline on a Place ID |
| `/api/audit` | POST: request a free audit |
| `/api/create-checkout-session` | POST: create Stripe checkout session |
| `/api/stripe-webhook` | POST: Stripe webhook endpoint |
| `/api/draft/approve` | POST: approve a draft |
| `/api/draft/reject` | POST: reject a draft |
| `/api/draft/mark-sent` | POST: mark draft as sent |

## Architecture

```
review-reaper/
├── api/
│   └── server.py          # HTTP server (all pages + API + Stripe)
├── src/
│   ├── database.py        # SQLite ORM
│   ├── scraper.py         # Google Reviews scraper + sentiment analysis
│   ├── response_generator.py  # AI response draft generator
│   └── pipeline.py        # Orchestrator (scrape → analyze → generate → store)
├── data/
│   └── reviewreaper.db    # SQLite database (auto-created)
├── Dockerfile             # Containerized deployment
├── docker-compose.yml     # Docker Compose for local hosting
├── railway.json           # Railway config
├── render.yaml            # Render blueprint
├── Procfile               # Heroku-style deployment
├── .env                   # Configuration (gitignored)
├── .env.template          # Config template
├── requirements.txt       # Python dependencies
├── start.sh               # Quick start script
├── deploy.sh              # One-click Railway deploy script
└── README.md
```

## Stripe Integration

Review Reaper now has built-in Stripe checkout for $97/mo subscriptions.

### Setup

1. Create a Stripe account at [stripe.com](https://stripe.com)
2. Get your keys from [Stripe Dashboard](https://dashboard.stripe.com/apikeys)
3. Create a product → recurring price → $97/mo
4. Add to `.env`:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PRICE_ID=price_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

### Test Mode

Without Stripe keys, the checkout creates simulated success URLs. Navigate to `/pricing` and click "Subscribe Now" to see it in action.

## Configuration

Edit `.env`:

```env
OPENAI_API_KEY=your_key          # Required for AI generation
ADMIN_PASSWORD=reaper2026        # Dashboard password
DRY_RUN=true                     # true = sample data, false = live Google Places API
PORT=9090                        # Server port
BASE_URL=http://localhost:9090   # Public URL (set in production)
STRIPE_SECRET_KEY=               # Stripe secret key
STRIPE_PRICE_ID=                 # $97/mo Stripe price ID
STRIPE_PUBLISHABLE_KEY=          # Stripe publishable key
```

## Dry-Run Mode

With `DRY_RUN=true` (default), the system works entirely with sample data — no API keys needed. Two sample businesses are included:

| Place ID | Business | Negative Reviews |
|----------|----------|-----------------|
| `ChIJN1t_tDeuEmsRUsoyG83frY4` | Sample Auto Shop | 10 |
| `ChIJC8N0v7yuEmsR7KQh8LOOdHY` | Oakville Dental Care | 10 |

## Production Mode

1. Set `DRY_RUN=false` in `.env`
2. Add your `GOOGLE_MAPS_API_KEY` to `.env`
3. Add your `OPENAI_API_KEY` to `.env`
4. Find your business's Google Place ID (use the [Google Place ID Finder](https://developers.google.com/maps/documentation/places/web-service/place-id))
5. Run the pipeline

## Key Design Decisions

- **Single port** — landing page, admin dashboard, and API all served from one HTTP server
- **Stripe checkout** — $97/mo subscription with built-in checkout flow
- **Manual review** — every response requires explicit approval before sending
- **Dry-run first** — test everything with sample data before connecting to live APIs
- **PlaceID entry** — manual Place ID entry for MVP; auto-search later
- **Tone adaptation** — responses adapt based on business type (auto shop ≠ dental)
