# Investment Copilot

A personal "hedge fund in a box": **you are the PM**, the app is your analyst team and back office.

- **Ingest** your real brokerage data — drop in CSV exports from **Fidelity** and **Merrill Edge** (broker and file type auto-detected, dirty rows handled, re-uploads deduped).
- **Analyze** the book — holdings with live P&L, sector/asset-class allocation, concentration (top-5, HHI), Sharpe, beta vs SPY, max drawdown.
- **Research** stocks — price charts, fundamentals, SEC EDGAR financial trends.
- **Run comps** — target vs peers across EV/EBITDA, P/E, P/S, growth, margins, with peer median/mean and premium/discount.
- **Track insiders** — SEC Form 4 ingestion, cluster-buy detection, insider sentiment score.
- **Develop theses** — direction, target, catalysts, risks; track entry vs target; AI drafts and bull/bear critiques.
- **AI Analyst chat** — streaming Claude analyst with live tools over your portfolio, quotes, fundamentals, comps, insiders, filings, and theses. Generates one-page research memos.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy (SQLite), pandas |
| Market data | yfinance (cached in SQLite with TTL + stale-serve) |
| Filings/insiders | SEC EDGAR JSON APIs + Form 4 XML |
| AI | Claude API (`claude-opus-4-8`) — streaming chat with tool use, structured thesis outputs |
| Frontend | Next.js (App Router, TypeScript), Tailwind CSS, Recharts |

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp ../.env.example .env        # then edit:
#   ANTHROPIC_API_KEY=sk-ant-...        ← enables the AI analyst (optional)
#   EDGAR_USER_AGENT=YourApp/0.1 (you@email.com)   ← required by SEC for insider/filing data
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000  (proxies /api/* to the backend)
```

### 3. Load your data

Export CSVs from your brokers and drop them on the **Portfolio** page (or POST to `/api/portfolio/upload`):

- **Fidelity**: *Accounts & Trade → Portfolio → Positions → Download*, and *Activity & Orders → Download*
- **Merrill Edge**: *Holdings → Export*, and *Activity → Export*

Sample fixtures live in `backend/fixtures/` if you want to try it without real data:

```bash
for f in backend/fixtures/*.csv; do curl -F "file=@$f" localhost:8000/api/portfolio/upload; done
```

## Without an Anthropic API key

Everything except the AI features works: ingestion, holdings, analytics, comps, insiders, thesis CRUD.
AI endpoints (`/api/chat`, thesis draft/critique, memo generation) return `503` and the UI explains why.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests   # fully offline: CSV parsers + analytics
```

## Architecture notes

- **`backend/app/brokers/`** — `BrokerAdapter` interface; each broker implements `sniff()` + positions/transactions parsers. A future live connector (Plaid/SnapTrade) implements the same interface.
- **Market data caching** — every yfinance/EDGAR call is cached in the `market_cache` table; on fetch failure the API serves the last cached payload flagged `"stale": true` rather than erroring.
- **Portfolio metrics methodology** — without historical account snapshots, the return series assumes current holdings were held over the lookback window (labeled `current-holdings-backfill` in API and UI).
- **AI tool use** — `/api/chat` streams SSE events (`text`, `tool_call`, `tool_result`, `done`, `error`) from a server-side agentic loop (max 8 tool iterations).

> Not investment advice. Data sources are free/unofficial (Yahoo Finance, SEC EDGAR) and can be delayed, missing, or wrong.
