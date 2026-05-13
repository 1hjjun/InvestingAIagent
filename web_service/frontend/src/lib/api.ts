export type AgentRun = {
  trace_id: string;
  answer_text: string;
  chart_data: Record<string, unknown> | null;
  is_saved: boolean;
  stop_reason: string | null;
};

export type TraceSummary = {
  trace_id: string;
  started_at: string | null;
  ended_at: string | null;
  stop_reason: string | null;
  metrics: {
    total_latency_ms?: number | null;
    step_count?: number;
    tool_call_count?: number;
    tool_error_count?: number;
    fallback_count?: number;
  };
  request: {
    user_query?: string;
    image_url?: string | null;
  };
};

export type TraceStep = {
  step: number;
  type: string;
  name: string;
  arguments: unknown;
  result: unknown;
  error: unknown;
  started_at: string | null;
  ended_at: string | null;
  latency_ms: number | null;
};

export type TraceDetail = TraceSummary & {
  prompt: { version: string; text: string };
  model: { provider: string; name: string };
  steps: TraceStep[];
  final_answer: string | null;
  chart_data: Record<string, unknown> | null;
  is_saved: boolean;
  safety: {
    masked_fields: string[];
    excluded_fields: string[];
    notes: string;
  };
};

export type PortfolioAnalytics = {
  total_seed_krw: number;
  ten_percent_seed_krw: number;
  cash_krw: number;
  cash_ratio_pct: number;
  theme_allocation: {
    theme: string;
    theme_label: string;
    value_krw: number;
    allocation_pct: number;
  }[];
  position_values: {
    ticker: string;
    name: string;
    theme: string;
    theme_label: string;
    value_krw: number;
  }[];
  crypto_values: {
    ticker: string;
    name: string;
    theme: string;
    theme_label: string;
    value_krw: number;
  }[];
};

export type Portfolio = {
  cash_ratio?: number | null;
  cash_krw?: number;
  base_currency?: string;
  positions?: Record<string, unknown>[];
  crypto_holdings?: Record<string, unknown>[];
  analytics?: PortfolioAnalytics;
  [key: string]: unknown;
};

export type Journal = {
  date: string;
  title: string;
  subtitle?: string;
  conversation_count?: number;
  article: string;
  updated_at?: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function formRequest<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createRun(input: {
  user_query: string;
  image_url?: string;
  youtube_url?: string;
}) {
  return request<AgentRun>("/api/runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function createRunWithUpload(input: {
  user_query: string;
  youtube_url?: string;
  image?: File | null;
}) {
  const formData = new FormData();
  formData.append("user_query", input.user_query);
  if (input.youtube_url) {
    formData.append("youtube_url", input.youtube_url);
  }
  if (input.image) {
    formData.append("image", input.image);
  }
  return formRequest<AgentRun>("/api/runs/upload", formData);
}

export function listRuns() {
  return request<{ runs: TraceSummary[] }>("/api/runs");
}

export function getRun(traceId: string) {
  return request<TraceDetail>(`/api/runs/${traceId}`);
}

export function getPortfolio() {
  return request<Portfolio>("/api/portfolio");
}

export function getJournals() {
  return request<{ journals: Journal[] }>("/api/journals");
}

export function formatMs(value?: number | null) {
  if (value === null || value === undefined) return "-";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function formatKrw(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

export function shortText(value?: string | null, max = 120) {
  if (!value) return "-";
  return value.length > max ? `${value.slice(0, max)}...` : value;
}
