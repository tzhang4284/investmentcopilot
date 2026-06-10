# Deploying to Vercel (fully cloud-hosted)

The app deploys as **two Vercel projects from this one GitHub repo** plus a
free **Neon Postgres** database. Every `git push` to `main` redeploys both.

```
Browser ──HTTPS──▶ Vercel project "copilot-web"  (frontend/, Next.js)
                     │  Google sign-in (Auth.js) + email allowlist
                     │  /api/* proxied server-side with bearer token
                     ▼
                   Vercel project "copilot-api"  (backend/, FastAPI on Python)
                     │  rejects requests without the bearer token
                     ▼
                   Neon Postgres (Vercel Marketplace, free tier)
```

Nothing reaches the FastAPI backend without (1) a valid Google session on an
allowlisted email **and** (2) the server-side bearer token, which never
leaves Vercel's servers.

---

## 1. Database — Neon Postgres (~2 min)

1. Vercel dashboard → **Storage** → **Create Database** → **Neon (Postgres)** → free plan.
2. Copy the connection string (`postgres://...`). You'll paste it into the
   backend project in step 2. (Tables are created automatically on first boot.)

## 2. Backend project (~5 min)

1. Vercel → **Add New Project** → import `tzhang4284/investmentcopilot`.
2. **Root Directory:** `backend` (leave framework as "Other").
3. Environment variables:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string |
   | `API_AUTH_TOKEN` | output of `openssl rand -hex 32` — save it for step 3 |
   | `ANTHROPIC_API_KEY` | your Claude API key |
   | `EDGAR_USER_AGENT` | `YourName you@example.com` |

4. Deploy. Note the URL (e.g. `https://copilot-api.vercel.app`) and verify
   `https://copilot-api.vercel.app/api/health` returns `{"ok": true, ...}`.
   Every other route returns 401 without the token — that's correct.

## 3. Google OAuth credentials (~5 min)

1. [console.cloud.google.com](https://console.cloud.google.com) → create/select a
   project → **APIs & Services → OAuth consent screen**: External, add yourself
   as a test user (test mode is fine for personal use — no verification needed).
2. **Credentials → Create Credentials → OAuth client ID → Web application**:
   - Authorized JavaScript origins: `https://copilot-web.vercel.app` (your frontend URL)
   - Authorized redirect URI: `https://copilot-web.vercel.app/api/auth/callback/google`
3. Copy the **Client ID** and **Client Secret**.

## 4. Frontend project (~5 min)

1. Vercel → **Add New Project** → import the same repo again.
2. **Root Directory:** `frontend` (Next.js is auto-detected).
3. Environment variables:

   | Name | Value |
   |---|---|
   | `AUTH_SECRET` | output of `openssl rand -base64 32` |
   | `AUTH_GOOGLE_ID` | Google OAuth client ID |
   | `AUTH_GOOGLE_SECRET` | Google OAuth client secret |
   | `ALLOWED_EMAILS` | `you@gmail.com` (comma-separate to add more) |
   | `BACKEND_URL` | backend URL from step 2, e.g. `https://copilot-api.vercel.app` |
   | `API_AUTH_TOKEN` | same token as the backend project |

4. Deploy. If you used a placeholder URL in step 3, update the Google OAuth
   redirect URI to match the real frontend URL.

Done — visiting the site now redirects to a Google sign-in; any account not in
`ALLOWED_EMAILS` is rejected with "not on the allowlist".

---

## Extra hardening (optional, recommended)

- **Vercel Deployment Protection** on the *backend* project
  (Settings → Deployment Protection → Vercel Authentication) blocks even
  unauthenticated probing of preview deployments.
- Rotate `API_AUTH_TOKEN` periodically — change it in both projects.
- Custom domain: add it to the frontend project and update the Google OAuth
  origins/redirect URI.

## Alternative sign-in options (if you don't want Google)

- **GitHub OAuth** — drop-in swap: `import GitHub from "next-auth/providers/github"`
  in `frontend/src/auth.ts`, set `AUTH_GITHUB_ID`/`AUTH_GITHUB_SECRET`. Setup is
  simpler than Google (no consent screen review).
- **Vercel Deployment Protection only** — zero code: enable "Vercel
  Authentication" on the frontend project so only your Vercel account can view
  it. Coarser (no in-app identity) but adequate for single-user.

## Caveats of serverless hosting

- **Cold starts:** the Python function loads pandas/yfinance on first request
  after idle (~2–5 s). Subsequent requests are fast.
- **Long AI streams:** function duration is capped (300 s configured); fine for
  chat/memos.
- **yfinance rate limits:** Vercel egress IPs are shared, so Yahoo may throttle
  more than your home IP. The built-in cache + stale-serve softens this.

## Local development (unchanged)

```bash
# backend
cd backend && uvicorn app.main:app --reload --port 8000
# frontend — with AUTH_DISABLED=true in frontend/.env.local, no Google needed
cd frontend && npm run dev
```
