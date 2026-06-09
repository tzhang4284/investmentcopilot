"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ReactMarkdown from "react-markdown";
import { api, fmt, postJson } from "@/lib/api";
import type { Fundamentals, Memo } from "@/lib/types";
import { Badge, Button, Card, EmptyState, ErrorBox, Spinner } from "@/components/ui";

interface HistoryResp {
  points: { date: string; close: number }[];
}
interface Quote {
  price: number;
  change?: number;
  change_pct?: number;
  stale?: boolean;
}
interface Financials {
  entity?: string;
  revenue: { fy: string; value: number }[];
  net_income: { fy: string; value: number }[];
  eps_diluted: { fy: string; value: number }[];
}

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"];

export default function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker: raw } = use(params);
  const ticker = decodeURIComponent(raw).toUpperCase();

  const [quote, setQuote] = useState<Quote | null>(null);
  const [fund, setFund] = useState<Fundamentals | null>(null);
  const [history, setHistory] = useState<HistoryResp | null>(null);
  const [financials, setFinancials] = useState<Financials | null>(null);
  const [period, setPeriod] = useState("1y");
  const [loading, setLoading] = useState(true);
  const [memo, setMemo] = useState<Memo | null>(null);
  const [memoLoading, setMemoLoading] = useState(false);
  const [memoError, setMemoError] = useState("");

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      api<Quote>(`/api/stocks/${ticker}/quote`),
      api<Fundamentals>(`/api/stocks/${ticker}/fundamentals`),
      api<Financials>(`/api/stocks/${ticker}/financials`),
    ]).then(([q, f, fin]) => {
      if (q.status === "fulfilled") setQuote(q.value);
      if (f.status === "fulfilled") setFund(f.value);
      if (fin.status === "fulfilled") setFinancials(fin.value);
      setLoading(false);
    });
  }, [ticker]);

  useEffect(() => {
    api<HistoryResp>(`/api/stocks/${ticker}/history?period=${period}`)
      .then(setHistory)
      .catch(() => setHistory(null));
  }, [ticker, period]);

  async function generateMemo() {
    setMemoLoading(true);
    setMemoError("");
    try {
      const m = await postJson<Memo>("/api/memos/generate", { ticker });
      setMemo(m);
    } catch (e) {
      setMemoError(e instanceof Error ? e.message : "memo failed");
    }
    setMemoLoading(false);
  }

  if (loading) return <Spinner label={`Loading ${ticker}…`} />;

  const valuation: [string, string][] = fund
    ? [
        ["Market Cap", fmt.compact(fund.market_cap)],
        ["EV", fmt.compact(fund.enterprise_value)],
        ["P/E (TTM)", fmt.num(fund.pe_ttm)],
        ["P/E (Fwd)", fmt.num(fund.pe_fwd)],
        ["EV/EBITDA", fmt.num(fund.ev_ebitda)],
        ["EV/Revenue", fmt.num(fund.ev_revenue)],
        ["P/S", fmt.num(fund.ps)],
        ["Div Yield", fund.dividend_yield != null ? fmt.pct(fund.dividend_yield) : "—"],
        ["Rev Growth", fund.revenue_growth != null ? fmt.pct(fund.revenue_growth) : "—"],
        ["Gross Margin", fund.gross_margin != null ? fmt.pct(fund.gross_margin) : "—"],
        ["Op Margin", fund.op_margin != null ? fmt.pct(fund.op_margin) : "—"],
        ["FCF Margin", fund.fcf_margin != null ? fmt.pct(fund.fcf_margin) : "—"],
      ]
    : [];

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{ticker}</h1>
            {fund?.sector && <Badge>{fund.sector}</Badge>}
            {(quote?.stale || fund?.stale) && <Badge tone="warn">stale data</Badge>}
          </div>
          <p className="text-sm text-muted mt-1">{fund?.name ?? ""}</p>
        </div>
        <div className="flex items-center gap-4">
          {quote && (
            <div className="text-right">
              <div className="text-3xl font-semibold">{fmt.usd(quote.price)}</div>
              {quote.change_pct != null && (
                <div className={quote.change_pct >= 0 ? "text-accent text-sm" : "text-negative text-sm"}>
                  {quote.change_pct >= 0 ? "+" : ""}
                  {quote.change_pct.toFixed(2)}% today
                </div>
              )}
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Link href={`/comps?target=${ticker}`}>
              <Button variant="ghost">Comps →</Button>
            </Link>
            <Link href={`/insiders?ticker=${ticker}`}>
              <Button variant="ghost">Insiders →</Button>
            </Link>
          </div>
        </div>
      </header>

      {!quote && !fund && (
        <ErrorBox message={`No market data available for ${ticker}. Market data sources may be unreachable from this machine.`} />
      )}

      <Card
        title="Price"
        actions={
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`text-xs rounded px-2 py-1 ${
                  p === period ? "bg-edge text-foreground" : "text-muted hover:text-foreground"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        }
      >
        {history?.points?.length ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.points}>
                <CartesianGrid stroke="#1f2733" strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fill: "#8b98a9", fontSize: 11 }} minTickGap={50} />
                <YAxis domain={["auto", "auto"]} tick={{ fill: "#8b98a9", fontSize: 11 }} width={70} />
                <Tooltip
                  formatter={(v) => fmt.usd(Number(v))}
                  contentStyle={{ background: "#11161d", border: "1px solid #1f2733", borderRadius: 8 }}
                />
                <Line type="monotone" dataKey="close" stroke="#34d399" dot={false} strokeWidth={1.8} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message="No price history available" />
        )}
      </Card>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card title="Valuation & Quality">
          {fund ? (
            <div className="grid grid-cols-3 gap-x-4 gap-y-3">
              {valuation.map(([label, value]) => (
                <div key={label}>
                  <div className="text-xs text-muted">{label}</div>
                  <div className="text-sm font-medium mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="Fundamentals unavailable" />
          )}
          {fund?.summary && (
            <p className="text-xs text-muted mt-4 leading-relaxed border-t border-edge pt-3">{fund.summary}</p>
          )}
        </Card>

        <Card title="Revenue Trend (10-K, SEC EDGAR)">
          {financials?.revenue?.length ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={financials.revenue}>
                  <CartesianGrid stroke="#1f2733" strokeDasharray="3 3" />
                  <XAxis dataKey="fy" tick={{ fill: "#8b98a9", fontSize: 11 }} />
                  <YAxis tickFormatter={(v) => fmt.compact(Number(v))} tick={{ fill: "#8b98a9", fontSize: 11 }} width={60} />
                  <Tooltip
                    formatter={(v) => fmt.compact(Number(v))}
                    contentStyle={{ background: "#11161d", border: "1px solid #1f2733", borderRadius: 8 }}
                  />
                  <Bar dataKey="value" fill="#60a5fa" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState message="No EDGAR financials" hint="Requires SEC EDGAR access" />
          )}
        </Card>
      </div>

      <Card
        title="AI Research Memo"
        actions={
          <Button onClick={generateMemo} disabled={memoLoading}>
            {memoLoading ? "Writing…" : "Generate memo"}
          </Button>
        }
      >
        {memoError && <ErrorBox message={memoError} />}
        {memo ? (
          <article className="prose-invert max-w-none text-sm leading-relaxed [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-4 [&_h2]:mb-1 [&_p]:mb-2 [&_li]:ml-4 [&_li]:list-disc">
            <ReactMarkdown>{memo.content_md}</ReactMarkdown>
          </article>
        ) : (
          !memoError && (
            <EmptyState
              message="No memo generated yet"
              hint="Requires ANTHROPIC_API_KEY on the backend. The memo cites live fundamentals, comps, and insider data."
            />
          )
        )}
      </Card>
    </div>
  );
}
