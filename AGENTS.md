# AGENTS.md — LLM / AI-Assistant Handoff Guide

> **Purpose of this file:** you are (probably) an AI coding assistant — Claude, GPT, Gemini, Cursor, Copilot, or similar — picking up this project cold. This document contains everything you need to be productive immediately: what the app is, how it's architected, every convention and gotcha discovered during the original build, exact commands to run, and recipes for the most likely next tasks. **Read this before writing any code.** Humans are welcome too.

---

## 1. What this project is

**Investment Copilot** is a single-user "personal hedge fund" web app. The owner acts as Portfolio Manager; the app replicates a hedge fund's analyst team and back office:

- **Ingest** real brokerage data via CSV exports from **Fidelity** and **Merrill Edge** (auto-detected, dirty-CSV tolerant, idempotent re-uploads)
- **Analyze** the portfolio: live P&L, sector/asset-class allocation, concentration (top-5 weight, HHI), Sharpe, beta vs SPY, max drawdown
- **Research** stocks: price charts, fundamentals, SEC EDGAR financial trends
- **Run comps**: target vs peer set across EV/EBITDA, P/E (ttm/fwd), P/S, EV/Rev, growth, margins, with peer median/mean and premium/discount
- **Track insiders**: SEC Form 4 ingestion, cluster-buy detection (≥3 insiders buying within 14 days), sentiment score in [-1, 1]
- **Develop theses**: direction/target/catalysts/risks CRUD, entry-vs-target tracking, AI drafting and bull/bear critique
- **AI Analyst**: streaming Claude chat with tool use over the user's real portfolio, quotes, fundamentals, comps, insiders, filings, and theses; generates one-page markdown research memos

**Guardrails:** single user, no multi-tenancy, no Alembic migrations (`Base.metadata.create_all`), no Docker. Auth exists solely to keep strangers out of a personal deployment.

---

## 2. Current status (as of the last session)

| Item | State |
|---|---|
| Full application (backend + frontend) | ✅ Built, on branch `claude/eager-hopper-d17kdr` |
| Backend tests | ✅ 15/15 passing (`backend/tests/`, fully offline) |
| Frontend production build | ✅ Clean in both auth-enabled and auth-disabled configs |
| Google sign-in + email allowlist + API token shield | ✅ Implemented and smoke-tested |
| Vercel serverless packaging (backend) + Postgres support | ✅ Implemented |
| Draft PR | **#1** `claude/eager-hopper-d17kdr` → `main` |
| Cloud deployment | ⬜ **Not done — user-side setup**: create Neon DB, two Vercel projects, Google OAuth credentials. Follow [DEPLOYMENT.md](DEPLOYMENT.md) exactly. |

There is **no CI configured** on the repo. If you add CI, a sensible minimal workflow is: `pytest backend/tests` + `npm run build` in `frontend/` (with `AUTH_DISABLED=true`).

---

## 3. Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │  Vercel project "frontend"  (Next.js 16)     │
 Browser ── HTTPS ──▶  │                                              │
                       │  proxy.ts ──── no session? ──▶ /signin       │
                       │     │  (Auth.js v5, Google, ALLOWED_EMAILS)  │
                       │     ▼                                        │
                       │  /api/[...path]/route.ts  (catch-all proxy)  │
                       │     • await auth()  → 401 if no session      │
                       │     • adds  Authorization: Bearer <token>    │
                       └─────────────────┬────────────────────────────┘
                                         │ HTTPS (token never in browser)
                       ┌─────────────────▼────────────────────────────┐
                       │  Vercel project "backend"  (FastAPI, Python) │
                       │  api/index.py → app.main:app                 │
                       │  middleware: reject non-Bearer requests      │
                       │  (exempt: /api/health)                       │
                       └─────────────────┬────────────────────────────┘
                                         │ SQLAlchemy
                          ┌──────────────▼──────────────┐
                          │ Neon Postgres (production)  │
                          │ SQLite backend/data/ (local)│
                          └─────────────────────────────┘
        External: yfinance (quotes/fundamentals, DB-cached with TTL)
                  SEC EDGAR JSON + Form 4 XML (throttled, UA required)
                  Claude API (AI analyst; optional — app degrades cleanly)
```

**Key security property:** the browser *never* talks to FastAPI directly and never sees `API_AUTH_TOKEN` or `BACKEND_URL`. All `/api/*` calls go through the authenticated Next.js catch-all route, which checks the session server-side and injects the bearer token. The backend rejects everything else (constant-time compare via `hmac.compare_digest`).

---

## 4. Repo map

```
.
├── AGENTS.md                ← you are here (also loaded via CLAUDE.md)
├── CLAUDE.md                ← "@AGENTS.md" (Claude Code auto-load)
├── README.md                ← human quick-start
├── DEPLOYMENT.md            ← step-by-step Vercel + Neon + Google OAuth guide
├── .env.example             ← every env var, annotated, both apps
├── backend/
│   ├── pyproject.toml       ← deps; extras: [dev]=pytest, [pg]=psycopg2-binary
│   ├── requirements.txt     ← MIRROR of pyproject deps for Vercel's Python builder — keep in sync!
│   ├── vercel.json          ← rewrites all → api/index; memory 1024MB, maxDuration 300s
│   ├── api/index.py         ← Vercel serverless entrypoint; calls init_db() at import
│   ├── Procfile             ← for Railway/Render alternative hosting (harmless otherwise)
│   ├── fixtures/            ← 4 realistic dirty CSVs: {fidelity,merrill}_{positions,transactions}.csv
│   ├── tests/               ← test_broker_parsers.py + test_analytics.py (15 tests total) — fully offline
│   └── app/
│       ├── main.py          ← app factory, CORS (localhost:3000), bearer-token middleware, /api/health
│       ├── config.py        ← pydantic-settings; sqlalchemy_url property normalizes postgres:// → postgresql://
│       ├── db.py            ← engine (SQLite w/ check_same_thread, or PG w/ pool_pre_ping), get_db, init_db
│       ├── models.py        ← all 8 ORM tables (see §5.1)
│       ├── schemas.py       ← Pydantic request/response models
│       ├── brokers/
│       │   ├── __init__.py  ← ⚠️ MUST import fidelity, merrill or adapters never register (see §12)
│       │   ├── base.py      ← BrokerAdapter ABC, NormalizedPosition/Transaction, detect_broker(),
│       │   │                   register_adapter(), find_header_row(), iter_data_rows(), to_float(), to_date()
│       │   ├── fidelity.py  ← Fidelity positions + transactions parser
│       │   └── merrill.py   ← Merrill Edge positions + transactions parser
│       ├── services/
│       │   ├── portfolio.py   ← ingest_csv(), rebuild_lots() (FIFO), get_holdings()
│       │   ├── market_data.py ← cached() TTL wrapper, get_quote(s), get_fundamentals, get_history, suggest_peers
│       │   ├── edgar.py       ← ticker→CIK, submissions, Form 4 XML parse (lxml), company facts; throttled
│       │   ├── insiders.py    ← refresh(), get_activity(), detect_cluster_buys(), sentiment()
│       │   ├── analytics.py   ← compute_metrics(), series_metrics(), beta(), compute_allocation()
│       │   ├── comps.py       ← build_comps(): peer stats + premium/discount vs median
│       │   └── ai/
│       │       ├── client.py  ← THE ONLY place Claude calls are constructed (see §6)
│       │       ├── tools.py   ← 7 tool schemas + dispatch()
│       │       ├── chat.py    ← SSE agentic loop (max 8 iterations), anyio thread bridging
│       │       ├── thesis.py  ← draft/critique via messages.parse → Pydantic
│       │       └── memo.py    ← streaming memo generation, saved to DB
│       └── routers/         ← portfolio, stocks, insiders, theses, chat, memos (prefixes /api/<name>)
└── frontend/
    ├── package.json         ← next 16.2.9, react 19, next-auth 5.0.0-beta.31, recharts, react-markdown, tailwind v4
    ├── next.config.ts       ← intentionally EMPTY of rewrites (proxy route replaced them)
    ├── AGENTS.md / CLAUDE.md ← warns: Next.js 16 differs from training data; read node_modules/next/dist/docs
    └── src/
        ├── auth.ts          ← NextAuth config: Google provider, ALLOWED_EMAILS allowlist, authDisabled flag
        ├── proxy.ts         ← Next.js 16 middleware (renamed!); redirects unauthed pages → /signin
        ├── app/
        │   ├── layout.tsx           ← server component; await auth(); passes email to Sidebar
        │   ├── page.tsx             ← Dashboard (NAV, metrics, sector pie, movers, theses, memos)
        │   ├── signin/page.tsx      ← Google sign-in page (server action → signIn("google"))
        │   ├── api/auth/[...nextauth]/route.ts  ← NextAuth handlers (wins over catch-all: more specific)
        │   ├── api/[...path]/route.ts           ← ★ authenticated catch-all proxy to FastAPI (see §8)
        │   ├── portfolio/  stock/  stock/[ticker]/  comps/  insiders/  theses/  chat/
        ├── components/      ← Sidebar (user menu + signout), ui.tsx (Card, MetricCard, Pnl, Badge, …)
        └── lib/             ← api.ts (typed fetch + fmt helpers), sse.ts (fetch-stream SSE reader), types.ts
```

---

## 5. Backend deep dive

### 5.1 Database tables (`backend/app/models.py`)

| Table | Purpose | Critical details |
|---|---|---|
| `accounts` | broker + label | unique `(broker, account_label)` |
| `positions` | current holdings snapshot | **replaced wholesale** on each positions upload |
| `transactions` | trade history | `dedupe_hash` (sha256) **unique** → re-uploading the same CSV is a no-op |
| `lots` | FIFO lots | derived; fully recomputed from transactions on ingest |
| `theses` | investment theses | `catalysts`/`risks` are JSON columns |
| `memos` | AI research memos | markdown in `content_md` |
| `insider_transactions` | Form 4 rows | unique `(accession_no, row_index)` → idempotent refresh |
| `market_cache` | yfinance/EDGAR cache | key like `"quote:AAPL"`; TTL enforced in service layer, not DB |

Schema changes: there are **no migrations**. `init_db()` runs `create_all` (new tables/columns on fresh DBs only). If you alter an existing column, document that the user must drop the local `backend/data/copilot.db` (or migrate Postgres manually).

### 5.2 CSV parsing (`backend/app/brokers/`) — the make-or-break subsystem

Real brokerage CSVs are dirty: preamble lines before the header, footer disclaimers, `"$1,234.56"`, `(123.45)` negatives, `--` placeholders, BOM. Rules encoded in `base.py`:

- Decode `utf-8-sig`. `find_header_row()` scans the first ~30 lines for the row matching the most expected column names — never assume row 0.
- Columns are mapped **by normalized header name** (with synonyms), never by index.
- `to_float()`: strips `$ , % "`; `--`/`n/a`/empty → `None`; `(123.45)` → `-123.45`.
- Rows that don't parse are collected into `skipped_rows` and returned in the upload response — parsing **never hard-fails** on a bad row.
- **Broker sniffing** (`detect_broker()`): Fidelity positions = headers contain "cost basis total" + "symbol"; Fidelity transactions = "run date" + "settlement date"; Merrill = "unrealized gain/loss" or "symbol/cusip". Merrill rows may carry CUSIPs (9 alphanumerics) instead of tickers — detected and handled.
- Fidelity's **"Pending Activity"** pseudo-row must be skipped (it once appeared as a fake $250 cash holding — regression-tested).
- Money-market symbols (`SPAXX**`, etc.) → `asset_class="cash"`.
- Action mapping: Fidelity `YOU BOUGHT`→buy, `YOU SOLD`→sell, `DIVIDEND RECEIVED`→dividend, etc.; Merrill `Purchase`/`Sale`/`Dividend`.

### 5.3 Market data (`services/market_data.py`)

Every yfinance call goes through `cached(key, ttl, fetch_fn)` backed by the `market_cache` table. TTLs: **quotes 5 min, fundamentals 24 h, history 12 h, peers 7 d**. On fetch failure the last cached payload is served with `"stale": true` (frontend shows a stale badge) — a cache **miss** + failure yields `null`/404/empty-state, never a 500. Peer suggestion uses a static `PEER_MAP` dict with a yfinance-sector fallback.

### 5.4 SEC EDGAR (`services/edgar.py`)

- **A descriptive `User-Agent` with contact email is mandatory** — EDGAR returns 403 without it (`EDGAR_USER_AGENT` env var).
- All requests throttled ≥150 ms apart.
- Form 4 XML parsed with lxml; **every XPath is guarded** — derivative-only filings, missing prices, and absent footnotes are all real cases.

### 5.5 Analytics honesty (`services/analytics.py`)

The app has no historical account snapshots, so the portfolio return series **assumes current holdings were held across the lookback window**. This methodology is labeled `"method": "current-holdings-backfill"` in the API and disclosed in the UI. **Do not remove that labeling**; if you improve the methodology (e.g., reconstruct from transactions), update the label.

### 5.6 API auth middleware (`app/main.py`)

When `API_AUTH_TOKEN` is set, every route except `/api/health` requires `Authorization: Bearer <token>`, compared with `hmac.compare_digest`. When unset (local dev), the API is open. Don't add per-route auth — this middleware is the single chokepoint.

### 5.7 Route inventory

| Prefix | Routes |
|---|---|
| `/api/portfolio` | `POST /upload` (multipart CSV), `GET /holdings`, `/transactions`, `/allocation`, `/metrics` |
| `/api/stocks` | `GET /{t}/quote`, `/fundamentals`, `/history`, `/financials`, `/peers`, `/comps?peers=A,B` |
| `/api/insiders` | `POST /{t}/refresh`, `GET /{t}` (transactions + clusters + sentiment) |
| `/api/theses` | CRUD, `GET /{id}/performance`, `POST /draft`, `POST /{id}/critique` |
| `/api/chat` | `POST` → SSE stream |
| `/api/memos` | `GET` list, `GET /{id}`, `DELETE /{id}`, `POST /generate` |
| `/api/health` | `{ok, ai_available, db_ok}` — the only unauthenticated route |

---

## 6. Claude API rules (read before touching `services/ai/`)

These caused real 400 errors during the build. All Claude call construction is centralized in **`services/ai/client.py`** — keep it that way.

1. Models: `MODEL_DEEP = "claude-opus-4-8"` (analysis), `MODEL_FAST = "claude-haiku-4-5"` (cheap/quick).
2. Use `thinking={"type": "adaptive"}` with opus-4-8. **Never pass `temperature`, `top_p`, or `budget_tokens`** — the API rejects them for this model with a 400.
3. Structured output: `client.messages.parse(..., output_format=SomePydanticModel)` → `response.parsed_output`. Used by thesis draft/critique.
4. Chat loop (`chat.py`): `client.messages.stream(...)` inside an agentic loop; if `stop_reason == "tool_use"`, run `tools.dispatch()`, append `tool_result` blocks, continue. **Max 8 iterations.** Sync SDK is bridged into async FastAPI via `anyio.to_thread` — the SSE generator yields dicts.
5. SSE event protocol (backend → frontend): `{"type": "text", "delta"}`, `{"type": "tool_call", "name", "input"}`, `{"type": "tool_result", "name", "is_error"}`, `{"type": "done"}`, `{"type": "error", "message"}`. The frontend (`lib/sse.ts`, `chat/page.tsx`) depends on these exact shapes.
6. The system prompt carries `cache_control: {"type": "ephemeral"}` for prompt caching.
7. Registered tools (in `tools.py`): `get_portfolio`, `get_quote`, `get_fundamentals`, `get_comps`, `get_insider_activity`, `search_filings`, `get_theses`.
8. **Graceful degradation is a contract:** without `ANTHROPIC_API_KEY`, `ai_available()` is false, AI endpoints return **503**, and the UI disables AI buttons with a tooltip. Non-AI features must never depend on the key.

---

## 7. Frontend deep dive — Next.js 16 gotchas

This repo uses **Next.js 16.2.9 (App Router, Turbopack) — several conventions differ from most LLM training data.** When in doubt, read `frontend/node_modules/next/dist/docs/`.

| Gotcha | Detail |
|---|---|
| `middleware.ts` is dead | Next 16 renamed it **`proxy.ts`** (same semantics). Ours is `src/proxy.ts`; it exports NextAuth's `auth` as the default (or a no-op when `AUTH_DISABLED=true`). Matcher excludes `api`, `signin`, `_next/*`, `favicon.ico`. |
| `params` / `searchParams` are **Promises** | Server components: `await params`. Client components: `use(params)`. See `stock/[ticker]/page.tsx`, `signin/page.tsx`. |
| SSE must use `fetch` + ReadableStream | `EventSource` is GET-only; our chat is a POST. `lib/sse.ts` splits the stream on `\n\n` and parses `data:` lines. Don't "simplify" it to EventSource. |
| `useSearchParams` needs `<Suspense>` | Already wrapped in `comps/` and `insiders/` pages — copy that pattern for new pages. |
| Tailwind **v4** | Configured via `@tailwindcss/postcss` + CSS variables in `globals.css` (dark theme). There is no `tailwind.config.js`. Theme tokens: `background`, `surface`, `edge`, `muted`, `accent`, `negative`. |
| Auth makes pages dynamic | `layout.tsx` calls `await auth()`, so with auth enabled every route is server-rendered per-request. That's expected — don't chase "static optimization" warnings. |
| next-auth is `5.0.0-beta.31` | Auth.js v5 API: `NextAuth()` returns `{handlers, auth, signIn, signOut}`. Env vars use the `AUTH_*` prefix convention. |

Shared UI primitives live in `src/components/ui.tsx` (Card, MetricCard, Pnl, Spinner, ErrorBox, EmptyState, Button, Input, Badge) and formatting helpers in `src/lib/api.ts` (`fmt.usd/compact/pct/pctRaw/num`). Reuse them; don't invent parallel ones.

---

## 8. Auth & security model

Two independent layers — both must hold:

1. **Session layer (frontend):** Auth.js Google provider. The `signIn` callback rejects any email not in `ALLOWED_EMAILS` (comma-separated, case-insensitive) → user sees "not on the allowlist". `src/proxy.ts` redirects unauthenticated page loads to `/signin`.
2. **Token layer (backend):** the catch-all route `src/app/api/[...path]/route.ts` runs `await auth()` (401 JSON if no session), then forwards the request to `BACKEND_URL` with `Authorization: Bearer ${API_AUTH_TOKEN}`. It streams request bodies up (CSV uploads need `duplex: "half"`) and response bodies down (SSE passes through). Backend-down → clean 502 `{"detail": "backend unreachable"}`.

Notes:
- `/api/auth/[...nextauth]` wins over the catch-all because specific segments beat catch-alls in App Router routing.
- **`AUTH_DISABLED=true`** (frontend env) disables both the proxy redirect and the session check — local dev only, never set in production.
- The NextAuth session is a JWT cookie (no DB adapter) — the Postgres DB stores no auth state at all.
- If you add a new backend route, it's automatically protected; nothing to do. If you add a route that must be *public*, exempt it in the backend middleware *and* think hard first.

---

## 9. Environment variables — complete reference

### Backend (local: `backend/.env`; production: Vercel backend project settings)

| Var | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | For AI features | Claude API. App fully functional without it (AI endpoints 503). |
| `EDGAR_USER_AGENT` | For insiders/filings | e.g. `YourName you@example.com`. SEC 403s without it. |
| `DATABASE_URL` | Production | Neon/Postgres URL. Empty → SQLite at `backend/data/copilot.db`. `postgres://` scheme auto-normalized. |
| `API_AUTH_TOKEN` | Production | Shared secret; `openssl rand -hex 32`. Empty → API open (local dev). |
| `RISK_FREE_RATE` | No (default 0.045) | Sharpe calculation. |

### Frontend (local: `frontend/.env.local`; production: Vercel frontend project settings)

| Var | Required? | Purpose |
|---|---|---|
| `AUTH_DISABLED` | Local only | `true` skips sign-in entirely. **Never in production.** |
| `AUTH_SECRET` | Production | Session-cookie signing key; `openssl rand -base64 32`. |
| `AUTH_GOOGLE_ID` / `AUTH_GOOGLE_SECRET` | Production | Google OAuth client (redirect URI: `https://<frontend>/api/auth/callback/google`). |
| `ALLOWED_EMAILS` | Production | Comma-separated allowlist; only these emails can sign in. |
| `BACKEND_URL` | Production | Backend deployment URL. Default `http://localhost:8000`. |
| `API_AUTH_TOKEN` | Production | Must equal the backend's token. |

---

## 10. Runbook — exact commands

```bash
# ── Backend (terminal 1) ─────────────────────────────────────────────
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env          # fill in what you need (see §9)
uvicorn app.main:app --reload --port 8000

# ── Frontend (terminal 2) ────────────────────────────────────────────
cd frontend
npm install
echo "AUTH_DISABLED=true" > .env.local
npm run dev                       # http://localhost:3000

# ── Tests (offline — no network needed) ──────────────────────────────
cd backend && .venv/bin/python -m pytest tests -q      # expect 15 passed

# ── Load fixture data ────────────────────────────────────────────────
for f in backend/fixtures/*.csv; do curl -F "file=@$f" localhost:8000/api/portfolio/upload; done
# Re-run it: transaction counts must NOT double (dedupe_hash) — good regression check.

# ── Auth smoke test (mirrors what was verified in the build) ─────────
API_AUTH_TOKEN=secret123 uvicorn app.main:app --port 8000 &
curl -s localhost:8000/api/health                                        # 200 always
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/theses       # 401
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer secret123" localhost:8000/api/theses  # 200

# ── Production build check ───────────────────────────────────────────
cd frontend && npm run build     # must pass with and without AUTH_DISABLED
```

**Definition of done for any change:** backend tests pass, `npm run build` passes, and if you touched auth/proxy/chat, re-run the auth smoke test and click through the AI chat streaming path.

---

## 11. Deployment

Full step-by-step: **[DEPLOYMENT.md](DEPLOYMENT.md)**. Topology: two Vercel projects from this one repo (root dirs `backend/` and `frontend/`) + Neon Postgres from the Vercel Marketplace. Push to `main` → both redeploy.

Operational caveats:
- **Cold starts:** the Python function imports pandas/yfinance → first request after idle takes ~2–5 s.
- **yfinance on shared egress IPs:** Yahoo may throttle Vercel's IPs harder than a home IP. TTL cache + stale-serve absorbs most of it; if quotes go persistently stale, that's why.
- `backend/vercel.json` sets memory 1024 MB / maxDuration 300 s; the frontend catch-all route also sets `export const maxDuration = 300` for long AI streams.
- **`backend/requirements.txt` must mirror `pyproject.toml` deps** — Vercel installs from requirements.txt; forgetting to sync is a silent way to break production only.

---

## 12. Recipes for likely next tasks

**Add a broker (e.g., Schwab):**
1. Create `backend/app/brokers/schwab.py`: subclass `BrokerAdapter`, implement `sniff()` (header-based detection) + `parse_positions()`/`parse_transactions()` returning `NormalizedPosition`/`NormalizedTransaction`. Decorate with `@register_adapter`.
2. **Import it in `brokers/__init__.py`** — without this the decorator never runs and detection silently fails (this bug happened once already).
3. Add a realistic dirty fixture CSV (preamble, footer, `--`, `(negatives)`, `$1,234.56`) to `backend/fixtures/` and tests to `tests/test_broker_parsers.py` (detection + a parsed-row assertion each for positions and transactions).

**Add an AI tool:**
1. Add its JSON schema to the list in `services/ai/tools.py` and a branch in `dispatch()` calling an existing service function.
2. Mention it in the system prompt in `chat.py` if the model should be steered toward it.
3. No frontend change needed — tool chips render generically from `tool_call` events.

**Add a page:** create `frontend/src/app/<name>/page.tsx` (`"use client"` + `useEffect` fetch is the house pattern), add to `NAV` in `components/Sidebar.tsx`, reuse `ui.tsx` primitives and `fmt` helpers. Wrap in `<Suspense>` if using `useSearchParams`.

**Add a live brokerage connector (Plaid/SnapTrade):** implement the same `BrokerAdapter` normalization targets from API payloads instead of CSV rows; ingest through the existing `portfolio.ingest` path so dedupe/lots keep working.

**Change the DB schema:** edit `models.py`; remember there are no migrations (§5.1).

---

## 13. Known pitfalls (bugs already hit — don't reintroduce)

1. **Adapter registration**: decorators only run on import → `brokers/__init__.py` must import every adapter module.
2. **Fidelity "Pending Activity"** row parses as a fake cash position unless skipped by symbol match.
3. **EventSource for chat** breaks — the chat endpoint is POST; SSE must be read via `fetch` + ReadableStream.
4. **Claude 400s**: `temperature`/`top_p`/`budget_tokens` with `claude-opus-4-8` + adaptive thinking. Construct calls only in `ai/client.py`.
5. **Next 16**: `middleware.ts` is ignored (use `proxy.ts`); `params`/`searchParams` are Promises.
6. **`.env.local` overrides shell env in some flows** — when testing auth-enabled behavior locally, move `.env.local` aside or you'll silently test with `AUTH_DISABLED=true`.
7. **requirements.txt drift** (see §11).
8. **Sandboxed/CI environments may block yfinance/EDGAR/Claude egress.** The app is designed to degrade (nulls, 404s, empty states, stale flags) — a wall of "Failed to get ticker" logs with a 200 response is *correct* offline behavior, not a bug.

---

## 14. Git & PR conventions

- Active work branch: **`claude/eager-hopper-d17kdr`**; open draft PR: **#1** → `main`. After #1 merges, branch off `main` per feature.
- Never force-push or rewrite `main`.
- Commit messages: imperative summary line + short body of bullet points (see `git log` for the house style).
- Keep PRs as drafts until the owner marks them ready; describe verification performed in the PR body.
- Never commit secrets — `.env`, `.env.local`, `*.db` are gitignored; `.env.example` is the only env file that belongs in git.

---

*Last updated: 2026-07-19. If you make architectural changes, update this file in the same PR.*
