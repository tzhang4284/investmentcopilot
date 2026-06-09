"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, fmt } from "@/lib/api";
import type { CompsResponse } from "@/lib/types";
import { Button, Card, EmptyState, ErrorBox, Input, Spinner, Badge } from "@/components/ui";

function formatMetric(key: string, v: unknown): string {
  if (typeof v !== "number") return "—";
  if (key === "market_cap" || key === "enterprise_value") return fmt.compact(v);
  if (key.includes("margin") || key === "revenue_growth") return fmt.pct(v);
  return fmt.num(v);
}

function CompsInner() {
  const searchParams = useSearchParams();
  const [target, setTarget] = useState(searchParams.get("target") ?? "");
  const [peerInput, setPeerInput] = useState("");
  const [peers, setPeers] = useState<string[]>([]);
  const [data, setData] = useState<CompsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = useCallback(
    async (tk: string, peerList: string[]) => {
      if (!tk) return;
      setLoading(true);
      setError("");
      try {
        const qs = peerList.length ? `?peers=${peerList.join(",")}` : "";
        const res = await api<CompsResponse>(`/api/stocks/${tk.toUpperCase()}/comps${qs}`);
        setData(res);
        setPeers(res.peers);
      } catch (e) {
        setError(e instanceof Error ? e.message : "comps failed");
        setData(null);
      }
      setLoading(false);
    },
    [],
  );

  useEffect(() => {
    const t = searchParams.get("target");
    if (t) run(t, []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function addPeer() {
    const p = peerInput.trim().toUpperCase();
    if (p && !peers.includes(p)) {
      const next = [...peers, p];
      setPeers(next);
      setPeerInput("");
      if (target) run(target, next);
    }
  }

  function removePeer(p: string) {
    const next = peers.filter((x) => x !== p);
    setPeers(next);
    if (target) run(target, next);
  }

  const pd = data?.target_premium_discount_vs_median ?? {};

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Comparables Analysis</h1>
        <p className="text-sm text-muted mt-1">
          Target vs peer multiples with median/mean and premium/discount. Peers auto-suggested, fully editable.
        </p>
      </header>

      <Card>
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            run(target, peers);
          }}
        >
          <Input
            placeholder="Target ticker"
            value={target}
            onChange={(e) => setTarget(e.target.value.toUpperCase())}
            className="w-36 uppercase"
          />
          <Button type="submit" disabled={!target || loading}>
            {loading ? "Building…" : "Build comps"}
          </Button>
          <div className="w-px h-6 bg-edge mx-1" />
          <Input
            placeholder="Add peer…"
            value={peerInput}
            onChange={(e) => setPeerInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addPeer();
              }
            }}
            className="w-32 uppercase"
          />
          {peers.map((p) => (
            <span key={p} className="flex items-center gap-1 bg-edge rounded-full px-3 py-1 text-xs">
              {p}
              <button type="button" onClick={() => removePeer(p)} className="text-muted hover:text-negative">
                ×
              </button>
            </span>
          ))}
        </form>
      </Card>

      {error && <ErrorBox message={error} />}
      {loading && <Spinner label="Pulling fundamentals…" />}

      {data && !loading && (
        <Card title={`${data.target} vs ${data.peers.length} peers`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm whitespace-nowrap">
              <thead>
                <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-edge">
                  <th className="py-2 pr-4 font-medium">Company</th>
                  {data.metrics.map((m) => (
                    <th key={m.key} className="py-2 pr-4 font-medium text-right">
                      {m.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => {
                  const tk = row.ticker as string;
                  const isTarget = row.is_target as boolean;
                  return (
                    <tr
                      key={tk}
                      className={`border-b border-edge/40 ${isTarget ? "bg-accent/5 font-medium" : ""}`}
                    >
                      <td className="py-2.5 pr-4">
                        <Link href={`/stock/${tk}`} className="hover:text-accent">
                          {tk}
                        </Link>
                        {isTarget && (
                          <span className="ml-2">
                            <Badge tone="pos">target</Badge>
                          </span>
                        )}
                        {"error" in row && (
                          <span className="ml-2">
                            <Badge tone="warn">no data</Badge>
                          </span>
                        )}
                      </td>
                      {data.metrics.map((m) => (
                        <td key={m.key} className="py-2.5 pr-4 text-right">
                          {formatMetric(m.key, row[m.key])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
                <tr className="border-b border-edge/40 text-muted">
                  <td className="py-2.5 pr-4 italic">Peer median</td>
                  {data.metrics.map((m) => (
                    <td key={m.key} className="py-2.5 pr-4 text-right">
                      {formatMetric(m.key, data.peer_stats[m.key]?.median)}
                    </td>
                  ))}
                </tr>
                <tr className="text-muted">
                  <td className="py-2.5 pr-4 italic">Peer mean</td>
                  {data.metrics.map((m) => (
                    <td key={m.key} className="py-2.5 pr-4 text-right">
                      {formatMetric(m.key, data.peer_stats[m.key]?.mean)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-5 border-t border-edge pt-4">
            <div className="text-xs text-muted uppercase tracking-wider mb-2">
              {data.target} premium / (discount) vs peer median
            </div>
            <div className="flex flex-wrap gap-3">
              {Object.entries(pd).map(([key, v]) => {
                const label = data.metrics.find((m) => m.key === key)?.label ?? key;
                return (
                  <div key={key} className="bg-background border border-edge rounded-lg px-3 py-2">
                    <div className="text-xs text-muted">{label}</div>
                    <div
                      className={`text-sm font-semibold ${
                        v == null ? "text-muted" : v > 0 ? "text-negative" : "text-accent"
                      }`}
                    >
                      {v == null ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(1)}%`}
                    </div>
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted/70 mt-2">
              Positive = target trades richer than peers; negative = discount.
            </p>
          </div>
        </Card>
      )}

      {!data && !loading && !error && (
        <Card>
          <EmptyState message="Enter a target ticker to build a comps table" />
        </Card>
      )}
    </div>
  );
}

export default function CompsPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <CompsInner />
    </Suspense>
  );
}
