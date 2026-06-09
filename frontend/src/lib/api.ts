export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const fmt = {
  usd(v: number | null | undefined, digits = 2): string {
    if (v == null) return "—";
    return v.toLocaleString("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: digits,
      minimumFractionDigits: digits,
    });
  },
  compact(v: number | null | undefined): string {
    if (v == null) return "—";
    return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
  },
  pct(v: number | null | undefined, digits = 1): string {
    if (v == null) return "—";
    return `${(v * 100).toFixed(digits)}%`;
  },
  pctRaw(v: number | null | undefined, digits = 1): string {
    if (v == null) return "—";
    return `${v.toFixed(digits)}%`;
  },
  num(v: number | null | undefined, digits = 2): string {
    if (v == null) return "—";
    return v.toLocaleString("en-US", { maximumFractionDigits: digits });
  },
};
