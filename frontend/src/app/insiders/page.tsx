"use client";

import { Suspense, useCallback, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { api, fmt } from "@/lib/api";
import type { InsiderActivity } from "@/lib/types";
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Spinner } from "@/components/ui";

const CODE_LABELS: Record<string, { label: string; tone: "pos" | "neg" | "default" }> = {
  P: { label: "Buy", tone: "pos" },
  S: { label: "Sell", tone: "neg" },
  A: { label: "Award", tone: "default" },
  D: { label: "Disposition", tone: "default" },
  G: { label: "Gift", tone: "default" },
  F: { label: "Tax", tone: "default" },
  M: { label: "Option Ex.", tone: "default" },
};

function InsidersInner() {
  const searchParams = useSearchParams();
  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [data, setData] = useState<InsiderActivity | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (tk: string) => {
    if (!tk) return;
    setLoading(true);
    setError("");
    try {
      setData(await api<InsiderActivity>(`/api/insiders/${tk.toUpperCase()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed");
      setData(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const t = searchParams.get("ticker");
    if (t) load(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshFromSec() {
    if (!ticker) return;
    setRefreshing(true);
    setError("");
    try {
      const res = await api<{ fetched_rows: number; inserted: number }>(
        `/api/insiders/${ticker.toUpperCase()}/refresh`,
        { method: "POST" },
      );
      if (res.fetched_rows === 0) {
        setError("No Form 4 filings retrieved — SEC EDGAR may be unreachable, or the ticker has no recent insider filings.");
      }
      await load(ticker);
    } catch (e) {
      setError(e instanceof Error ? e.message : "refresh failed");
    }
    setRefreshing(false);
  }

  const sent = data?.sentiment;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Insider Activity</h1>
        <p className="text-sm text-muted mt-1">
          SEC Form 4 transactions, cluster-buy detection, and an insider sentiment signal.
        </p>
      </header>

      <Card>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            load(ticker);
          }}
        >
          <Input
            placeholder="Ticker, e.g. AAPL"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            className="w-40 uppercase"
          />
          <Button type="submit" disabled={!ticker || loading}>
            View
          </Button>
          <Button variant="ghost" onClick={refreshFromSec} disabled={!ticker || refreshing}>
            {refreshing ? "Pulling from SEC…" : "↻ Refresh from EDGAR"}
          </Button>
        </form>
      </Card>

      {error && <ErrorBox message={error} />}
      {loading && <Spinner />}

      {data && !loading && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
              <div className="text-xs text-muted uppercase tracking-wider">Insider Sentiment (90d)</div>
              <div
                className={`text-2xl font-semibold mt-1 ${
                  sent?.label === "Bullish" ? "text-accent" : sent?.label === "Bearish" ? "text-negative" : ""
                }`}
              >
                {sent?.label ?? "—"}
              </div>
              <div className="text-xs text-muted mt-1">score {sent?.score ?? "—"}</div>
            </Card>
            <Card>
              <div className="text-xs text-muted uppercase tracking-wider">Buys (90d)</div>
              <div className="text-2xl font-semibold mt-1 text-accent">{fmt.compact(sent?.buy_value_90d)}</div>
            </Card>
            <Card>
              <div className="text-xs text-muted uppercase tracking-wider">Sells (90d)</div>
              <div className="text-2xl font-semibold mt-1 text-negative">{fmt.compact(sent?.sell_value_90d)}</div>
            </Card>
          </div>

          {data.cluster_buys.length > 0 && (
            <Card title="Cluster Buys Detected">
              {data.cluster_buys.map((c, i) => (
                <div key={i} className="flex items-center gap-3 text-sm py-1">
                  <Badge tone="pos">cluster</Badge>
                  <span>
                    {c.insiders.length} insiders bought {fmt.usd(c.total_value, 0)} between {c.start} and {c.end}
                  </span>
                  <span className="text-muted text-xs truncate">({c.insiders.join(", ")})</span>
                </div>
              ))}
            </Card>
          )}

          <Card title={`Form 4 Transactions — ${data.ticker}`}>
            {data.transactions.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-edge">
                      <th className="py-2 pr-3 font-medium">Date</th>
                      <th className="py-2 pr-3 font-medium">Insider</th>
                      <th className="py-2 pr-3 font-medium">Title</th>
                      <th className="py-2 pr-3 font-medium">Type</th>
                      <th className="py-2 pr-3 font-medium text-right">Shares</th>
                      <th className="py-2 pr-3 font-medium text-right">Price</th>
                      <th className="py-2 font-medium text-right">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.map((t, i) => {
                      const code = CODE_LABELS[t.code] ?? { label: t.code, tone: "default" as const };
                      return (
                        <tr key={i} className="border-b border-edge/40 last:border-0">
                          <td className="py-2 pr-3 whitespace-nowrap">{t.date ?? "—"}</td>
                          <td className="py-2 pr-3 font-medium">{t.insider_name}</td>
                          <td className="py-2 pr-3 text-muted text-xs">{t.insider_title || "—"}</td>
                          <td className="py-2 pr-3">
                            <Badge tone={code.tone}>{code.label}</Badge>
                          </td>
                          <td className="py-2 pr-3 text-right">{fmt.num(t.shares, 0)}</td>
                          <td className="py-2 pr-3 text-right">{fmt.usd(t.price)}</td>
                          <td className="py-2 text-right">{t.value != null ? fmt.usd(t.value, 0) : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                message="No insider transactions stored for this ticker"
                hint='Click "Refresh from EDGAR" to pull recent Form 4 filings'
              />
            )}
          </Card>
        </>
      )}
    </div>
  );
}

export default function InsidersPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <InsidersInner />
    </Suspense>
  );
}
