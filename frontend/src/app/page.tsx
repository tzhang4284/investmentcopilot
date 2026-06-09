"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { api, fmt } from "@/lib/api";
import type { Allocation, HoldingsResponse, Memo, Metrics, Thesis } from "@/lib/types";
import { Card, EmptyState, MetricCard, Pnl, Spinner, Badge } from "@/components/ui";

const PIE_COLORS = ["#34d399", "#60a5fa", "#f59e0b", "#a78bfa", "#f87171", "#2dd4bf", "#fb923c", "#94a3b8"];

export default function Dashboard() {
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [allocation, setAllocation] = useState<Allocation | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [memos, setMemos] = useState<Memo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      api<HoldingsResponse>("/api/portfolio/holdings"),
      api<Allocation>("/api/portfolio/allocation"),
      api<Metrics>("/api/portfolio/metrics"),
      api<Thesis[]>("/api/theses"),
      api<Memo[]>("/api/memos"),
    ]).then(([h, a, m, t, me]) => {
      if (h.status === "fulfilled") setHoldings(h.value);
      if (a.status === "fulfilled") setAllocation(a.value);
      if (m.status === "fulfilled") setMetrics(m.value);
      if (t.status === "fulfilled") setTheses(t.value);
      if (me.status === "fulfilled") setMemos(me.value);
      setLoading(false);
    });
  }, []);

  if (loading) return <Spinner label="Loading dashboard…" />;

  const hasData = holdings && holdings.holdings.length > 0;
  const movers = (holdings?.holdings ?? [])
    .filter((h) => h.day_change_pct != null)
    .sort((a, b) => Math.abs(b.day_change_pct!) - Math.abs(a.day_change_pct!))
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted mt-1">Your fund at a glance</p>
        </div>
        {hasData && (
          <div className="text-right">
            <div className="text-xs text-muted uppercase tracking-wider">Net Asset Value</div>
            <div className="text-3xl font-semibold">{fmt.usd(holdings!.total_value)}</div>
          </div>
        )}
      </header>

      {!hasData && (
        <Card>
          <EmptyState
            message="No portfolio data yet."
            hint="Go to Portfolio and upload your Fidelity or Merrill Edge CSV exports."
          />
          <div className="text-center">
            <Link href="/portfolio" className="text-accent text-sm hover:underline">
              Upload CSVs →
            </Link>
          </div>
        </Card>
      )}

      {hasData && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Sharpe (1y)"
              value={metrics?.sharpe != null ? metrics.sharpe.toFixed(2) : "—"}
              sub={metrics?.method === "current-holdings-backfill" ? "current-holdings backfill" : undefined}
            />
            <MetricCard
              label="Beta vs SPY"
              value={metrics?.beta_vs_spy != null ? metrics.beta_vs_spy.toFixed(2) : "—"}
            />
            <MetricCard
              label="Max Drawdown"
              value={metrics?.max_drawdown != null ? fmt.pct(metrics.max_drawdown) : "—"}
              tone={metrics?.max_drawdown != null && metrics.max_drawdown < -0.15 ? "neg" : null}
            />
            <MetricCard
              label="Top-5 Concentration"
              value={allocation?.concentration ? fmt.pct(allocation.concentration.top5_weight) : "—"}
              sub={allocation?.concentration ? `HHI ${allocation.concentration.hhi.toFixed(3)}` : undefined}
            />
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <Card title="Sector Allocation">
              {allocation?.by_sector?.length ? (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={allocation.by_sector}
                        dataKey="value"
                        nameKey="sector"
                        innerRadius={55}
                        outerRadius={90}
                        paddingAngle={2}
                        label={({ name }) => name}
                      >
                        {allocation.by_sector.map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} stroke="none" />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(v) => fmt.usd(Number(v))}
                        contentStyle={{ background: "#11161d", border: "1px solid #1f2733", borderRadius: 8 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState message="Sector data unavailable" hint="Needs market data access" />
              )}
            </Card>

            <Card title="Top Movers Today">
              {movers.length ? (
                <table className="w-full text-sm">
                  <tbody>
                    {movers.map((h) => (
                      <tr key={h.ticker} className="border-b border-edge/50 last:border-0">
                        <td className="py-2">
                          <Link href={`/stock/${h.ticker}`} className="font-medium hover:text-accent">
                            {h.ticker}
                          </Link>
                        </td>
                        <td className="py-2 text-muted truncate max-w-40">{h.description}</td>
                        <td className="py-2 text-right">{fmt.usd(h.market_value)}</td>
                        <td className="py-2 text-right">
                          <Pnl value={h.day_change_pct} suffix="%" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState message="No live quote data" hint="Day moves appear when market data is reachable" />
              )}
            </Card>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <Card title="Active Theses">
              {theses.filter((t) => t.status === "active").length ? (
                <div className="space-y-2">
                  {theses
                    .filter((t) => t.status === "active")
                    .slice(0, 5)
                    .map((t) => (
                      <Link
                        key={t.id}
                        href="/theses"
                        className="flex items-center justify-between rounded-lg border border-edge/60 px-3 py-2 hover:border-accent/40"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{t.ticker}</span>
                          <Badge tone={t.direction === "long" ? "pos" : "neg"}>{t.direction}</Badge>
                        </div>
                        <span className="text-sm text-muted">
                          target {t.target_price ? fmt.usd(t.target_price) : "—"}
                        </span>
                      </Link>
                    ))}
                </div>
              ) : (
                <EmptyState message="No active theses" hint="Draft one on the Theses page" />
              )}
            </Card>

            <Card title="Recent Memos">
              {memos.length ? (
                <div className="space-y-2">
                  {memos.slice(0, 5).map((m) => (
                    <div key={m.id} className="rounded-lg border border-edge/60 px-3 py-2">
                      <div className="font-medium text-sm">{m.title}</div>
                      <div className="text-xs text-muted">{new Date(m.created_at).toLocaleDateString()}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState message="No memos yet" hint="Generate one from a stock page" />
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
