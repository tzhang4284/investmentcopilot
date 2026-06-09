"use client";

import { ReactNode } from "react";

export function Card({
  title,
  children,
  className = "",
  actions,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <section className={`bg-surface border border-edge rounded-xl p-5 ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between mb-4">
          {title && <h2 className="text-sm font-semibold text-muted uppercase tracking-wider">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "pos" | "neg" | null;
}) {
  return (
    <div className="bg-surface border border-edge rounded-xl p-4">
      <div className="text-xs text-muted uppercase tracking-wider">{label}</div>
      <div
        className={`text-2xl font-semibold mt-1 ${
          tone === "pos" ? "text-accent" : tone === "neg" ? "text-negative" : ""
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export function Pnl({ value, suffix = "" }: { value: number | null | undefined; suffix?: string }) {
  if (value == null) return <span className="text-muted">—</span>;
  const cls = value > 0 ? "text-accent" : value < 0 ? "text-negative" : "text-muted";
  const sign = value > 0 ? "+" : "";
  return (
    <span className={cls}>
      {sign}
      {value.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: suffix ? 1 : 2 })}
      {suffix}
    </span>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-muted text-sm py-8 justify-center">
      <span className="inline-block h-4 w-4 rounded-full border-2 border-edge border-t-accent animate-spin" />
      {label}
    </div>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="border border-negative/40 bg-negative/10 text-negative rounded-lg px-4 py-3 text-sm">
      {message}
    </div>
  );
}

export function EmptyState({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="text-center py-10">
      <div className="text-muted">{message}</div>
      {hint && <div className="text-xs text-muted/70 mt-1">{hint}</div>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost" | "danger";
  type?: "button" | "submit";
  title?: string;
}) {
  const styles = {
    primary: "bg-accent text-black hover:bg-accent/85 font-medium",
    ghost: "border border-edge text-foreground hover:bg-edge/60",
    danger: "border border-negative/50 text-negative hover:bg-negative/10",
  }[variant];
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg px-3 py-1.5 text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${styles}`}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`bg-background border border-edge rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-accent/60 placeholder:text-muted/60 ${props.className ?? ""}`}
    />
  );
}

export function Badge({ children, tone = "default" }: { children: ReactNode; tone?: "default" | "pos" | "neg" | "warn" }) {
  const styles = {
    default: "bg-edge text-muted",
    pos: "bg-accent/15 text-accent",
    neg: "bg-negative/15 text-negative",
    warn: "bg-yellow-500/15 text-yellow-400",
  }[tone];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${styles}`}>{children}</span>;
}
