"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, Input } from "@/components/ui";

export default function StockSearchPage() {
  const [ticker, setTicker] = useState("");
  const router = useRouter();

  function go() {
    const t = ticker.trim().toUpperCase();
    if (t) router.push(`/stock/${t}`);
  }

  return (
    <div className="space-y-6 max-w-xl">
      <header>
        <h1 className="text-2xl font-semibold">Stock Analysis</h1>
        <p className="text-sm text-muted mt-1">Pull up the full analyst view for any ticker.</p>
      </header>
      <Card>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            go();
          }}
        >
          <Input
            placeholder="Enter ticker, e.g. NVDA"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="flex-1 uppercase"
            autoFocus
          />
          <Button type="submit">Analyze</Button>
        </form>
        <div className="flex gap-2 mt-4 flex-wrap">
          {["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "JPM", "XOM"].map((t) => (
            <button
              key={t}
              onClick={() => router.push(`/stock/${t}`)}
              className="text-xs border border-edge rounded-full px-3 py-1 text-muted hover:text-foreground hover:border-accent/50"
            >
              {t}
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}
