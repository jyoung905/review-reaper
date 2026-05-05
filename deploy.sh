#!/bin/bash
# Review Reaper — One-Click Deploy
# Automatically deploys to Railway (requires Railway account - free tier)
#
# Prerequisites:
#   1. Have a Railway account (railway.app — free tier works)
#   2. Run: npm install -g @railway/cli
#   3. Run: railway login
#
# Usage:
#   ./deploy.sh

set -e

cd "$(dirname "$0")"

echo "☠️  Review Reaper — One-Click Deploy"
echo "======================================"
echo ""

# Check railway CLI
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Install it:"
    echo "   npm install -g @railway/cli"
    echo "   railway login"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged in to Railway. Run:"
    echo "   railway login"
    exit 1
fi

echo "🚀 Deploying to Railway..."

# Initialize a new Railway project
railway init --name review-reaper

# Deploy
railway up --ci

# Get the public URL
echo ""
echo "✅ Deploy complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Set environment variables in Railway dashboard:"
echo "      - ADMIN_PASSWORD (default: reaper2026)"
echo "      - OPENAI_API_KEY (for AI generation)"
echo "      - STRIPE_SECRET_KEY (for payments)"
echo "      - STRIPE_PRICE_ID ($97/mo price)"
echo "      - DRY_RUN=false (for live data)"
echo "      - BASE_URL=https://your-app.up.railway.app"
echo "   2. Add a custom domain: railway domain"
echo "   3. Configure Stripe webhook to: https://your-app.up.railway.app/api/stripe-webhook"
echo ""
echo "🔗 Get your URL: railway domain"
