# ReplyRig 🔧⭐

**AI-powered Google review auto-responder for trades businesses.**

ReplyRig connects to your Google Business Profile and automatically responds to every review with a personalized, AI-generated reply — posted within the hour.

- **Stack**: Python + Flask, PostgreSQL, OpenAI GPT-4o-mini, Google Business API, Stripe
- **Price**: $29/mo (vs. Birdeye's $350+/mo)
- **Deploy**: Railway

---

## Quick Start (Local Dev)

### 1. Clone & create virtualenv

```bash
cd ReplyRig
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your actual API keys (see "Keys You Need" below)
```

### 3. Set up PostgreSQL

```bash
createdb replyrig
# Or use SQLite for local dev — it works out of the box if DATABASE_URL is not set
```

### 4. Run

```bash
python app.py
```

Open http://localhost:5000

---

## Keys You Need

### 1. 🔑 Google OAuth Client (Required)

You need a Google Cloud project with the **Google My Business API** enabled.

**Steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "ReplyRig")
3. Enable these APIs:
   - **My Business Account Management API**
   - **My Business Business Information API**
   - **My Business Reviews API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Authorized redirect URIs: `https://replyrig.app/google/callback` (and `http://localhost:5000/google/callback` for dev)
7. Copy **Client ID** and **Client Secret** → paste into `.env`

> ⚠️ The Google My Business API requires your app to go through **Google's verification** for production use. For testing, add your email as a test user under OAuth consent screen.

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

### 2. 🔑 OpenAI API Key (Required)

1. Go to [platform.openai.com](https://platform.openai.com/api-keys)
2. Create a new API key
3. Add to `.env`:

```
OPENAI_API_KEY=sk-...
```

> GPT-4o-mini costs ~$0.00015/1K input tokens. Each review response costs roughly **$0.001** — basically free at $29/mo pricing.

### 3. 🔑 Stripe Keys (Required for payments)

1. Go to [stripe.com](https://stripe.com) → create an account
2. In the Dashboard, get your **Test** keys first:
   - `STRIPE_SECRET_KEY=sk_test_...`
   - `STRIPE_PUBLISHABLE_KEY=pk_test_...`
3. Create a **Recurring Price**:
   - Products → Add Product → "ReplyRig Pro" → $29/mo recurring
   - Copy the **Price ID**: `price_...`
4. Set up **Webhook**:
   - Developers → Webhooks → Add endpoint
   - URL: `https://replyrig.app/stripe/webhook`
   - Events to listen for:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
   - Copy the **Signing Secret**: `whsec_...`

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_MONTHLY_PRICE_ID=price_...
```

### 4. 🔑 Database

Railway provides a PostgreSQL addon automatically. Locally:

```
DATABASE_URL=postgresql://localhost/replyrig
```

---

## Deploy to Railway

### 1. Install Railway CLI

```bash
npm install -g @railway/cli
railway login
```

### 2. Create project

```bash
railway init
railway add postgresql
```

### 3. Set environment variables

In the Railway dashboard → your service → Variables, add all keys from `.env.example`.

Railway auto-sets `DATABASE_URL` from the PostgreSQL addon.

### 4. Deploy

```bash
git push   # Railway auto-deploys on git push
# or:
railway up
```

### 5. Set your domain

Railway Dashboard → your service → Settings → Generate Domain (or add custom domain `replyrig.app`).

Update `BASE_URL` in Railway env vars to your deployed URL.

---

## Project Structure

```
ReplyRig/
├── app.py                    # Flask app factory, routes registration
├── requirements.txt
├── Procfile                  # gunicorn for Railway/Heroku
├── railway.toml              # Railway deployment config
├── .env.example              # Copy to .env, fill in keys
├── models/
│   ├── user.py               # User model (email, password, Stripe plan)
│   └── business.py           # Business + ReviewLog models
├── routes/
│   ├── auth.py               # Register, login, logout
│   ├── dashboard.py          # Main dashboard + business management
│   ├── google_oauth.py       # Google OAuth2 flow
│   └── stripe_webhook.py     # Stripe checkout + webhook handler
├── services/
│   ├── google_reviews.py     # Fetch unanswered reviews via Google API
│   ├── ai_responder.py       # GPT-4o-mini response generation
│   ├── review_poster.py      # Post replies back to Google
│   └── stripe_service.py     # Stripe subscription utilities
├── scheduler/
│   └── review_checker.py     # Hourly APScheduler job
├── templates/                # Jinja2 HTML templates
└── static/style.css          # Custom CSS
```

---

## How It Works

1. User registers → connects Google Business Profile via OAuth
2. User subscribes via Stripe ($29/mo) → plan set to `pro`
3. Background scheduler runs **every hour**:
   - Fetches unanswered reviews from Google API
   - Sends each review to GPT-4o-mini → generates personalized reply
   - Posts reply back to Google via API
   - Logs result to `review_log` table
4. User can view all reviews + replies in the dashboard

---

## Database Schema

Tables are auto-created on startup via SQLAlchemy.

- `users` — accounts, Stripe customer ID, plan (free/pro)
- `businesses` — connected Google locations, OAuth tokens, tone setting
- `review_log` — every review seen, its reply, and status (pending/replied/failed)

---

## Configuration

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Flask session secret (make it long and random) |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o-mini |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key (used in frontend) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_MONTHLY_PRICE_ID` | Stripe Price ID for $29/mo plan |
| `BASE_URL` | Your app's public URL (used for OAuth redirects) |

---

## Next Steps / Roadmap

- [ ] Email notifications when a review is replied to
- [ ] Manual reply override (edit before posting)
- [ ] Reply preview mode (generate but don't post until approved)
- [ ] Multi-location support (already in DB, just UI work)
- [ ] Review analytics (average rating over time, reply rate)
- [ ] Referral program

---

## Support

support@replyrig.app
