"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, fmt } from "@/lib/api";
import type { Holding, HoldingsResponse, Txn } from "@/lib/types";
import { Badge, Button, Card, EmptyState, ErrorBox, Pnl, Spinner } from "@/components/ui";

interface UploadResult {
  ok: boolean;
  broker: string;
  kind: string;
  skipped_rows: number;
  positions_ingested?: number;
  transactions_ingested?: number;
  duplicates_skipped?: number;
  filename: string;
}

type SortKey = "ticker" | "market_value" | "unrealized_pnl_pct" | "weight";

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [txns, setTxns] = useState<Txn[] | null>(null);
  const [tab, setTab] = useState<"holdings" | "transactions">("holdings");
  const [loading, setLoading] = useState(true);
  const [uploads, setUploads] = useState<UploadResult[]>([]);
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("market_value");
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.allSettled([
      api<HoldingsResponse>("/api/portfolio/holdings"),
      api<{ transactions: Txn[] }>("/api/portfolio/transactions?limit=200"),
    ]).then(([h, t]) => {
      if (h.status === "fulfilled") setHoldings(h.value);
      if (t.status === "fulfilled") setTxns(t.value.transactions);
      setLoading(false);
    });
  }, []);

  useEffect(refresh, [refresh]);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setUploadError("");
    const results: UploadResult[] = [];
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        const res = await fetch("/api/portfolio/upload", { method: "POST", body: form });
        const body = await res.json();
        if (!res.ok) throw new Error(body.detail ?? "upload failed");
        results.push(body as UploadResult);
      } catch (e) {
        setUploadError(`${file.name}: ${e instanceof Error ? e.message : "upload failed"}`);
      }
    }
    setUploads((prev) => [...results, ...prev].slice(0, 6));
    setUploading(false);
    refresh();
  }

  const sorted = [...(holdings?.holdings ?? [])].sort((a, b) => {
    if (sortKey === "ticker") return a.ticker.localeCompare(b.ticker);
    return ((b[sortKey] as number) ?? -Infinity) - ((a[sortKey] as number) ?? -Infinity);
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Portfolio</h1>
        <p className="text-sm text-muted mt-1">
          Upload positions & transaction CSVs exported from Fidelity or Merrill Edge — broker and file type are
          auto-detected.
        </p>
      </header>

      <Card>
        <div
          className="border-2 border-dashed border-edge rounded-xl p-8 text-center cursor-pointer hover:border-accent/50 transition-colors"
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFiles(e.dataTransfer.files);
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept=".csv"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
          <div className="text-sm">
            {uploading ? "Uploading…" : "Drop CSV files here or click to browse"}
          </div>
          <div className="text-xs text-muted mt-1">
            Fidelity: Positions / Activity & Orders exports · Merrill: Holdings / Transactions exports
          </div>
        </div>
        {uploadError && <div className="mt-3"><ErrorBox message={uploadError} /></div>}
        {uploads.length > 0 && (
          <div className="mt-3 space-y-1">
            {uploads.map((u, i) => (
              <div key={i} className="text-xs text-muted flex items-center gap-2">
                <Badge tone="pos">{u.broker}</Badge>
                <Badge>{u.kind}</Badge>
                <span>{u.filename}:</span>
                <span>
                  {u.kind === "positions"
                    ? `${u.positions_ingested} positions`
                    : `${u.transactions_ingested} new, ${u.duplicates_skipped} duplicates`}
                  {u.skipped_rows > 0 && ` · ${u.skipped_rows} junk rows skipped`}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="flex items-center gap-2">
        {(["holdings", "transactions"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-1.5 text-sm capitalize ${
              tab === t ? "bg-edge font-medium" : "text-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
        <div className="flex-1" />
        {holdings && tab === "holdings" && (
          <div className="text-sm text-muted">
            Total: <span className="text-foreground font-medium">{fmt.usd(holdings.total_value)}</span>
          </div>
        )}
        <Button variant="ghost" onClick={refresh}>↻ Refresh</Button>
      </div>

      {loading ? (
        <Spinner />
      ) : tab === "holdings" ? (
        <Card>
          {sorted.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-edge">
                    {(
                      [
                        ["ticker", "Ticker"],
                        [null, "Description"],
                        [null, "Class"],
                        [null, "Qty"],
                        [null, "Price"],
                        ["market_value", "Value"],
                        [null, "Cost"],
                        ["unrealized_pnl_pct", "P&L"],
                        ["weight", "Weight"],
                      ] as [SortKey | null, string][]
                    ).map(([key, label]) => (
                      <th
                        key={label}
                        className={`py-2 pr-3 font-medium ${key ? "cursor-pointer hover:text-foreground" : ""}`}
                        onClick={key ? () => setSortKey(key) : undefined}
                      >
                        {label}
                        {key === sortKey ? " ↓" : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((h: Holding) => (
                    <tr key={h.ticker} className="border-b border-edge/40 last:border-0 hover:bg-edge/20">
                      <td className="py-2.5 pr-3">
                        {h.asset_class === "cash" ? (
                          <span className="font-medium">{h.ticker}</span>
                        ) : (
                          <Link href={`/stock/${h.ticker}`} className="font-medium hover:text-accent">
                            {h.ticker}
                          </Link>
                        )}
                      </td>
                      <td className="py-2.5 pr-3 text-muted truncate max-w-52">{h.description}</td>
                      <td className="py-2.5 pr-3">
                        <Badge tone={h.asset_class === "cash" ? "warn" : "default"}>{h.asset_class}</Badge>
                      </td>
                      <td className="py-2.5 pr-3">{fmt.num(h.quantity)}</td>
                      <td className="py-2.5 pr-3">{fmt.usd(h.price)}</td>
                      <td className="py-2.5 pr-3">{fmt.usd(h.market_value)}</td>
                      <td className="py-2.5 pr-3 text-muted">{h.cost_basis ? fmt.usd(h.cost_basis) : "—"}</td>
                      <td className="py-2.5 pr-3">
                        <Pnl value={h.unrealized_pnl} />{" "}
                        {h.unrealized_pnl_pct != null && (
                          <span className="text-xs">
                            (<Pnl value={h.unrealized_pnl_pct} suffix="%" />)
                          </span>
                        )}
                      </td>
                      <td className="py-2.5">{fmt.pct(h.weight)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message="No holdings yet" hint="Upload a positions CSV above" />
          )}
        </Card>
      ) : (
        <Card>
          {txns?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted text-xs uppercase tracking-wider border-b border-edge">
                    <th className="py-2 pr-3 font-medium">Date</th>
                    <th className="py-2 pr-3 font-medium">Broker</th>
                    <th className="py-2 pr-3 font-medium">Action</th>
                    <th className="py-2 pr-3 font-medium">Ticker</th>
                    <th className="py-2 pr-3 font-medium">Qty</th>
                    <th className="py-2 pr-3 font-medium">Price</th>
                    <th className="py-2 pr-3 font-medium">Amount</th>
                    <th className="py-2 font-medium">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {txns.map((t) => (
                    <tr key={t.id} className="border-b border-edge/40 last:border-0">
                      <td className="py-2 pr-3 whitespace-nowrap">{t.trade_date ?? "—"}</td>
                      <td className="py-2 pr-3"><Badge>{t.broker}</Badge></td>
                      <td className="py-2 pr-3">
                        <Badge tone={t.action === "buy" ? "pos" : t.action === "sell" ? "neg" : "default"}>
                          {t.action}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3 font-medium">{t.ticker || "—"}</td>
                      <td className="py-2 pr-3">{t.quantity != null ? fmt.num(t.quantity) : "—"}</td>
                      <td className="py-2 pr-3">{fmt.usd(t.price)}</td>
                      <td className="py-2 pr-3"><Pnl value={t.amount} /></td>
                      <td className="py-2 text-muted text-xs truncate max-w-60">{t.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message="No transactions yet" hint="Upload a transactions CSV above" />
          )}
        </Card>
      )}
    </div>
  );
}
