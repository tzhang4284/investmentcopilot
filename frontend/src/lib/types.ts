export interface Holding {
  ticker: string;
  description: string;
  asset_class: string;
  quantity: number;
  cost_basis: number;
  price: number | null;
  market_value: number | null;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
  day_change_pct?: number | null;
  weight: number;
  accounts: string[];
}

export interface HoldingsResponse {
  total_value: number;
  holdings: Holding[];
}

export interface Txn {
  id: number;
  broker: string;
  trade_date: string | null;
  ticker: string;
  action: string;
  quantity: number | null;
  price: number | null;
  amount: number | null;
  description: string;
}

export interface Allocation {
  total_value: number;
  by_sector: { sector: string; value: number; weight: number }[];
  by_asset_class: { asset_class: string; value: number; weight: number }[];
  concentration: { top5_weight: number; hhi: number };
  error?: string;
}

export interface Metrics {
  period?: string;
  annualized_return?: number;
  annualized_volatility?: number;
  sharpe?: number | null;
  beta_vs_spy?: number | null;
  max_drawdown?: number;
  method?: string;
  error?: string;
}

export interface Fundamentals {
  ticker: string;
  name?: string;
  sector?: string;
  industry?: string;
  market_cap?: number;
  enterprise_value?: number;
  pe_ttm?: number;
  pe_fwd?: number;
  ps?: number;
  ev_revenue?: number;
  ev_ebitda?: number;
  revenue?: number;
  revenue_growth?: number;
  gross_margin?: number;
  op_margin?: number;
  net_margin?: number;
  fcf?: number;
  fcf_margin?: number;
  dividend_yield?: number;
  beta?: number;
  summary?: string;
  stale?: boolean;
}

export interface CompsResponse {
  target: string;
  peers: string[];
  metrics: { key: string; label: string }[];
  rows: Record<string, unknown>[];
  peer_stats: Record<string, { median: number | null; mean: number | null }>;
  target_premium_discount_vs_median: Record<string, number | null>;
}

export interface InsiderActivity {
  ticker: string;
  transactions: {
    date: string | null;
    insider_name: string;
    insider_title: string;
    code: string;
    shares: number | null;
    price: number | null;
    value: number | null;
  }[];
  cluster_buys: { start: string; end: string; insiders: string[]; total_value: number }[];
  sentiment: { score: number; label: string; buy_value_90d: number; sell_value_90d: number };
}

export interface Thesis {
  id: number;
  ticker: string;
  direction: "long" | "short";
  target_price: number | null;
  time_horizon_months: number | null;
  thesis_text: string;
  catalysts: string[];
  risks: string[];
  conviction: number | null;
  status: "active" | "closed";
  entry_price: number | null;
  entry_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface Memo {
  id: number;
  ticker: string;
  title: string;
  content_md: string;
  created_at: string;
}

export type ChatEvent =
  | { type: "text"; delta: string }
  | { type: "tool_call"; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; name: string; is_error: boolean }
  | { type: "done" }
  | { type: "error"; message: string };

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolCalls?: string[];
}
