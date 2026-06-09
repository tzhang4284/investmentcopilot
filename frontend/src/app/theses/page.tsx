"use client";

import { useCallback, useEffect, useState } from "react";
import { api, fmt, postJson } from "@/lib/api";
import type { Thesis } from "@/lib/types";
import { Badge, Button, Card, EmptyState, ErrorBox, Input, Spinner } from "@/components/ui";

interface DraftResult {
  thesis_text: string;
  target_price: number;
  time_horizon_months: number;
  catalysts: string[];
  risks: string[];
  conviction: number;
}

interface CritiqueResult {
  bull_case: string;
  bear_case: string;
  weakest_assumptions: string[];
  what_would_change_my_mind: string[];
  verdict: string;
}

interface Performance {
  current_price: number | null;
  return_pct?: number;
  progress_to_target?: number;
}

const emptyForm = {
  ticker: "",
  direction: "long" as "long" | "short",
  target_price: "",
  time_horizon_months: "",
  thesis_text: "",
  catalysts: "",
  risks: "",
  entry_price: "",
};

export default function ThesesPage() {
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState("");
  const [critiques, setCritiques] = useState<Record<number, CritiqueResult>>({});
  const [critiquing, setCritiquing] = useState<number | null>(null);
  const [perf, setPerf] = useState<Record<number, Performance>>({});

  const refresh = useCallback(() => {
    api<Thesis[]>("/api/theses").then((t) => {
      setTheses(t);
      setLoading(false);
      t.forEach((thesis) => {
        api<Performance>(`/api/theses/${thesis.id}/performance`)
          .then((p) => setPerf((prev) => ({ ...prev, [thesis.id]: p })))
          .catch(() => {});
      });
    });
  }, []);

  useEffect(refresh, [refresh]);

  function startEdit(t: Thesis) {
    setEditingId(t.id);
    setForm({
      ticker: t.ticker,
      direction: t.direction,
      target_price: t.target_price?.toString() ?? "",
      time_horizon_months: t.time_horizon_months?.toString() ?? "",
      thesis_text: t.thesis_text,
      catalysts: t.catalysts.join("\n"),
      risks: t.risks.join("\n"),
      entry_price: t.entry_price?.toString() ?? "",
    });
    setShowForm(true);
  }

  async function save() {
    setError("");
    const body = {
      ticker: form.ticker.toUpperCase(),
      direction: form.direction,
      target_price: form.target_price ? parseFloat(form.target_price) : null,
      time_horizon_months: form.time_horizon_months ? parseInt(form.time_horizon_months) : null,
      thesis_text: form.thesis_text,
      catalysts: form.catalysts.split("\n").map((s) => s.trim()).filter(Boolean),
      risks: form.risks.split("\n").map((s) => s.trim()).filter(Boolean),
      entry_price: form.entry_price ? parseFloat(form.entry_price) : null,
    };
    try {
      if (editingId != null) {
        await api(`/api/theses/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        await postJson("/api/theses", body);
      }
      setShowForm(false);
      setForm(emptyForm);
      setEditingId(null);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    }
  }

  async function aiDraft() {
    if (!form.ticker) {
      setError("Enter a ticker first, then let the AI draft the rest.");
      return;
    }
    setDrafting(true);
    setError("");
    try {
      const d = await postJson<DraftResult>("/api/theses/draft", {
        ticker: form.ticker.toUpperCase(),
        direction: form.direction,
        notes: form.thesis_text,
      });
      setForm((f) => ({
        ...f,
        thesis_text: d.thesis_text,
        target_price: d.target_price.toString(),
        time_horizon_months: d.time_horizon_months.toString(),
        catalysts: d.catalysts.join("\n"),
        risks: d.risks.join("\n"),
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI draft failed");
    }
    setDrafting(false);
  }

  async function critique(id: number) {
    setCritiquing(id);
    setError("");
    try {
      const c = await postJson<CritiqueResult>(`/api/theses/${id}/critique`, {});
      setCritiques((prev) => ({ ...prev, [id]: c }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "critique failed");
    }
    setCritiquing(null);
  }

  async function remove(id: number) {
    if (!confirm("Delete this thesis?")) return;
    await api(`/api/theses/${id}`, { method: "DELETE" });
    refresh();
  }

  async function toggleStatus(t: Thesis) {
    await api(`/api/theses/${t.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: t.status === "active" ? "closed" : "active" }),
    });
    refresh();
  }

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Investment Theses</h1>
          <p className="text-sm text-muted mt-1">
            Your book of ideas: direction, target, catalysts, risks — drafted by you or the AI analyst.
          </p>
        </div>
        <Button
          onClick={() => {
            setShowForm(!showForm);
            setEditingId(null);
            setForm(emptyForm);
          }}
        >
          {showForm ? "Cancel" : "+ New thesis"}
        </Button>
      </header>

      {error && <ErrorBox message={error} />}

      {showForm && (
        <Card title={editingId != null ? "Edit Thesis" : "New Thesis"}>
          <div className="grid sm:grid-cols-4 gap-3 mb-3">
            <Input
              placeholder="Ticker"
              value={form.ticker}
              onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })}
              className="uppercase"
            />
            <select
              value={form.direction}
              onChange={(e) => setForm({ ...form, direction: e.target.value as "long" | "short" })}
              className="bg-background border border-edge rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/60"
            >
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
            <Input
              placeholder="Target price"
              type="number"
              value={form.target_price}
              onChange={(e) => setForm({ ...form, target_price: e.target.value })}
            />
            <Input
              placeholder="Horizon (months)"
              type="number"
              value={form.time_horizon_months}
              onChange={(e) => setForm({ ...form, time_horizon_months: e.target.value })}
            />
          </div>
          <textarea
            placeholder="Thesis — or type rough notes and click 'AI draft' to have the analyst write it from live data"
            value={form.thesis_text}
            onChange={(e) => setForm({ ...form, thesis_text: e.target.value })}
            rows={6}
            className="w-full bg-background border border-edge rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60 placeholder:text-muted/60 mb-3"
          />
          <div className="grid sm:grid-cols-2 gap-3 mb-3">
            <textarea
              placeholder="Catalysts (one per line)"
              value={form.catalysts}
              onChange={(e) => setForm({ ...form, catalysts: e.target.value })}
              rows={4}
              className="bg-background border border-edge rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60 placeholder:text-muted/60"
            />
            <textarea
              placeholder="Risks (one per line)"
              value={form.risks}
              onChange={(e) => setForm({ ...form, risks: e.target.value })}
              rows={4}
              className="bg-background border border-edge rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-accent/60 placeholder:text-muted/60"
            />
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Entry price (optional)"
              type="number"
              value={form.entry_price}
              onChange={(e) => setForm({ ...form, entry_price: e.target.value })}
              className="w-44"
            />
            <div className="flex-1" />
            <Button variant="ghost" onClick={aiDraft} disabled={drafting} title="Requires ANTHROPIC_API_KEY">
              {drafting ? "Analyst drafting…" : "✦ AI draft"}
            </Button>
            <Button onClick={save} disabled={!form.ticker}>
              Save
            </Button>
          </div>
        </Card>
      )}

      {theses.length === 0 && !showForm && (
        <Card>
          <EmptyState message="No theses yet" hint="Create one manually or let the AI analyst draft it" />
        </Card>
      )}

      <div className="grid gap-4">
        {theses.map((t) => {
          const p = perf[t.id];
          const critiqueResult = critiques[t.id];
          return (
            <Card key={t.id}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold">{t.ticker}</span>
                  <Badge tone={t.direction === "long" ? "pos" : "neg"}>{t.direction}</Badge>
                  <Badge tone={t.status === "active" ? "default" : "warn"}>{t.status}</Badge>
                  {t.conviction != null && <Badge>conviction {t.conviction}/10</Badge>}
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-muted">
                    entry {t.entry_price ? fmt.usd(t.entry_price) : "—"} · now{" "}
                    {p?.current_price ? fmt.usd(p.current_price) : "—"} · target{" "}
                    {t.target_price ? fmt.usd(t.target_price) : "—"}
                  </span>
                  {p?.return_pct != null && (
                    <span className={p.return_pct >= 0 ? "text-accent" : "text-negative"}>
                      {p.return_pct >= 0 ? "+" : ""}
                      {p.return_pct.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>

              {p?.progress_to_target != null && (
                <div className="mt-3 h-1.5 bg-edge rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent"
                    style={{ width: `${Math.max(0, Math.min(100, p.progress_to_target * 100))}%` }}
                  />
                </div>
              )}

              {t.thesis_text && (
                <p className="text-sm text-foreground/90 mt-3 leading-relaxed whitespace-pre-line">
                  {t.thesis_text}
                </p>
              )}

              <div className="grid sm:grid-cols-2 gap-4 mt-3">
                {t.catalysts.length > 0 && (
                  <div>
                    <div className="text-xs text-muted uppercase tracking-wider mb-1">Catalysts</div>
                    <ul className="text-sm space-y-0.5">
                      {t.catalysts.map((c, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-accent">▸</span>
                          {c}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {t.risks.length > 0 && (
                  <div>
                    <div className="text-xs text-muted uppercase tracking-wider mb-1">Risks</div>
                    <ul className="text-sm space-y-0.5">
                      {t.risks.map((r, i) => (
                        <li key={i} className="flex gap-2">
                          <span className="text-negative">▸</span>
                          {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {critiqueResult && (
                <div className="mt-4 border-t border-edge pt-4 space-y-3 text-sm">
                  <div>
                    <Badge tone="pos">Bull case</Badge>
                    <p className="mt-1 text-foreground/90 whitespace-pre-line">{critiqueResult.bull_case}</p>
                  </div>
                  <div>
                    <Badge tone="neg">Bear case</Badge>
                    <p className="mt-1 text-foreground/90 whitespace-pre-line">{critiqueResult.bear_case}</p>
                  </div>
                  <div>
                    <Badge tone="warn">Weakest assumptions</Badge>
                    <ul className="mt-1 space-y-0.5">
                      {critiqueResult.weakest_assumptions.map((a, i) => (
                        <li key={i}>• {a}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <Badge>Verdict</Badge>
                    <p className="mt-1 font-medium">{critiqueResult.verdict}</p>
                  </div>
                </div>
              )}

              <div className="flex gap-2 mt-4 border-t border-edge pt-3">
                <Button variant="ghost" onClick={() => startEdit(t)}>
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => critique(t.id)}
                  disabled={critiquing === t.id}
                  title="AI bull/bear critique — requires ANTHROPIC_API_KEY"
                >
                  {critiquing === t.id ? "Critiquing…" : "✦ Critique"}
                </Button>
                <Button variant="ghost" onClick={() => toggleStatus(t)}>
                  {t.status === "active" ? "Close" : "Reopen"}
                </Button>
                <div className="flex-1" />
                <Button variant="danger" onClick={() => remove(t.id)}>
                  Delete
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
