"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { streamChat } from "@/lib/sse";
import type { ChatMessage } from "@/lib/types";
import { Badge, Button } from "@/components/ui";

const SUGGESTIONS = [
  "Summarize my portfolio and flag the biggest risks",
  "Run comps on NVDA — is it expensive vs peers?",
  "Any notable insider buying in my holdings?",
  "Critique my AAPL position: what's the bear case?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    setBusy(true);

    const history = [...messages, { role: "user" as const, content }];
    setMessages([...history, { role: "assistant", content: "", toolCalls: [] }]);

    const abort = new AbortController();
    abortRef.current = abort;

    try {
      await streamChat(
        history.map((m) => ({ role: m.role, content: m.content })),
        (e) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = { ...next[next.length - 1] };
            if (e.type === "text") {
              last.content += e.delta;
            } else if (e.type === "tool_call") {
              const arg =
                e.input && typeof e.input === "object" && "ticker" in e.input
                  ? `(${(e.input as { ticker: string }).ticker})`
                  : "";
              last.toolCalls = [...(last.toolCalls ?? []), `${e.name}${arg}`];
            } else if (e.type === "error") {
              setError(e.message);
            }
            next[next.length - 1] = last;
            return next;
          });
        },
        abort.signal,
      );
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : "stream failed");
      }
    }
    setBusy(false);
  }

  function stop() {
    abortRef.current?.abort();
    setBusy(false);
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <header className="mb-4">
        <h1 className="text-2xl font-semibold">AI Analyst</h1>
        <p className="text-sm text-muted mt-1">
          Your senior analyst, with live access to your portfolio, quotes, fundamentals, comps, insiders, filings,
          and theses.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <div className="grid sm:grid-cols-2 gap-3 max-w-2xl mx-auto mt-12">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="text-left text-sm border border-edge rounded-xl px-4 py-3 text-muted hover:text-foreground hover:border-accent/50 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                m.role === "user" ? "bg-accent/15 text-foreground" : "bg-surface border border-edge"
              }`}
            >
              {m.toolCalls && m.toolCalls.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {m.toolCalls.map((tc, j) => (
                    <Badge key={j} tone="default">
                      ⚙ {tc}
                    </Badge>
                  ))}
                </div>
              )}
              {m.role === "assistant" ? (
                m.content ? (
                  <article className="leading-relaxed [&_h2]:font-semibold [&_h2]:mt-3 [&_h3]:font-semibold [&_p]:mb-2 [&_li]:ml-4 [&_li]:list-disc [&_table]:w-full [&_th]:text-left [&_th]:border-b [&_th]:border-edge [&_th]:py-1 [&_td]:py-1 [&_td]:pr-3 [&_code]:text-accent">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </article>
                ) : (
                  <span className="inline-block h-4 w-4 rounded-full border-2 border-edge border-t-accent animate-spin" />
                )
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        {error && (
          <div className="text-sm text-negative border border-negative/40 bg-negative/10 rounded-lg px-4 py-2 max-w-xl">
            {error}
            {error.includes("ANTHROPIC_API_KEY") && (
              <span className="block text-xs mt-1 text-negative/80">
                Set ANTHROPIC_API_KEY in backend/.env and restart the backend to enable the AI analyst.
              </span>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your analyst anything — they'll pull the data…"
          className="flex-1 bg-surface border border-edge rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-accent/60 placeholder:text-muted/60"
        />
        {busy ? (
          <Button variant="ghost" onClick={stop}>
            ■ Stop
          </Button>
        ) : (
          <Button type="submit" disabled={!input.trim()}>
            Send
          </Button>
        )}
      </form>
    </div>
  );
}
