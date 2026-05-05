# ☠️ Review Reaper

**AI-powered Google review response system.** Automatically finds negative reviews, analyzes common complaints, and generates professional response drafts with recovery offers.

**Target market:** Multi-location businesses (franchises, dental chains, auto shops, property management)
**Price point:** $97/mo

## Quick Start

```bash
cd /Users/jamesyoung/.openclaw/workspace/businesses/review-reaper
./start.sh
```

This will:
1. Create a Python virtual environment
2. Install dependencies
3. Create `.env` from template (edit to add your API keys)
4. Start the server

## Architecture

```
review-reaper/
├── api/
│   └── server.py          # HTTP server (landing page + admin + API)
├── src/
│   ├── database.py        # SQLite ORM
│   ├── scraper.py         # Google Reviews scraper + sentiment analysis
│   ├── response_generator.py  # AI response draft generator
│   └── pipeline.py        # Orchestrator (scrape → analyze → generate → store)
├── data/
│   └── reviewreaper.db    # SQLite database (auto-created)
├── public/                # Static HTML (optional, fallback to built-in)
├── .env                   # Configuration
├── .env.template          # Config template
├── requirements.txt       # Python dependencies
├── start.sh               # Quick start script
└── README.md
```

## Routes

| Path | Description |
|------|-------------|
| `/` | Landing page with free audit CTA |
| `/admin` | Admin dashboard (password-gated) |
| `/admin/login` | Admin login page |
| `/admin/drafts` | Full draft management page |
| `/api/stats` | Dashboard statistics |
| `/api/businesses` | List all tracked businesses |
| `/api/drafts?status=pending` | List drafts (filter by status) |
| `/api/login` | POST: authenticate (returns token) |
| `/api/scan` | POST: run full pipeline on a Place ID |
| `/api/audit` | POST: request a free audit |
| `/api/draft/approve` | POST: approve a draft |
| `/api/draft/reject` | POST: reject a draft |
| `/api/draft/mark-sent` | POST: mark draft as sent |

## CLI Commands

```bash
# Initialize database
python -m src.pipeline --init-db

# Run full pipeline (scrape + analyze + generate)
python -m src.pipeline --step all --place-id <PLACE_ID>

# Run audit only
python -m src.pipeline --step audit --place-id <PLACE_ID>

# Show terminal dashboard
python -m src.pipeline
```

## Configuration

Edit `.env`:

```env
OPENAI_API_KEY=your_key          # Required for AI generation
ADMIN_PASSWORD=reaper2026        # Dashboard password
DRY_RUN=true                     # true = sample data, false = live Google Places API
PORT=9090                        # Server port
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
- **No Stripe** — payment integration deferred for MVP
- **Manual review** — every response requires explicit approval before sending
- **Dry-run first** — test everything with sample data before connecting to live APIs
- **PlaceID entry** — manual Place ID entry for MVP; auto-search later
- **Tone adaptation** — responses adapt based on business type (auto shop ≠ dental)
