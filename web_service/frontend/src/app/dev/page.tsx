"use client";

import { Suspense, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type TraceSummary = {
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

type TraceStep = {
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

type TraceDetail = TraceSummary & {
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

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function listRuns() {
  return request<{ runs: TraceSummary[] }>("/api/runs");
}

function getRun(traceId: string) {
  return request<TraceDetail>(`/api/runs/${traceId}`);
}

function formatMs(value?: number | null) {
  if (value === null || value === undefined) return "-";
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function shortText(value?: string | null, max = 120) {
  if (!value) return "-";
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[420px] overflow-auto rounded-md bg-ink p-4 text-sm leading-6 text-slate-100">
      {JSON.stringify(value ?? null, null, 2)}
    </pre>
  );
}

function stepTone(step: TraceStep) {
  if (step.error) return "border-coral bg-red-50";
  if (step.type === "tool_call") return "border-pine bg-teal-50";
  if (step.type === "llm") return "border-amber bg-yellow-50";
  return "border-line bg-white";
}

export default function DevTracePage() {
  return (
    <Suspense fallback={<DevLoading />}>
      <DevTraceContent />
    </Suspense>
  );
}

function DevLoading() {
  return (
    <main className="mx-auto max-w-7xl px-5 py-8">
      <div className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
        <p className="text-sm font-medium text-pine">Observability</p>
        <h1 className="mt-1 text-2xl font-semibold text-ink">Trace 화면을 불러오는 중입니다</h1>
      </div>
    </main>
  );
}

function DevTraceContent() {
  const [runs, setRuns] = useState<TraceSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [selectedStep, setSelectedStep] = useState<TraceStep | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshRuns() {
    setError(null);
    const payload = await listRuns();
    setRuns(payload.runs);
    if (!selected && payload.runs[0]) {
      setSelected(payload.runs[0].trace_id);
    }
  }

  useEffect(() => {
    const requestedTrace = new URLSearchParams(window.location.search).get("trace");
    if (requestedTrace) {
      setSelected(requestedTrace);
    }
    refreshRuns().catch((err) => setError(err instanceof Error ? err.message : "Trace list failed"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    getRun(selected)
      .then((payload) => {
        setTrace(payload);
        setSelectedStep(payload.steps.find((step) => step.type === "tool_call") ?? payload.steps[0] ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Trace load failed"))
      .finally(() => setLoading(false));
  }, [selected]);

  const metrics = trace?.metrics;
  const toolSteps = useMemo(() => trace?.steps.filter((step) => step.type === "tool_call") ?? [], [trace]);

  return (
    <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[340px_1fr]">
      <aside className="rounded-lg border border-line bg-white/94 p-4 shadow-soft">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-pine">Observability</p>
            <h1 className="text-2xl font-semibold text-ink">Trace runs</h1>
          </div>
          <button
            type="button"
            onClick={() => refreshRuns().catch((err) => setError(err instanceof Error ? err.message : "Refresh failed"))}
            className="grid h-10 w-10 place-items-center rounded-md border border-line hover:bg-mist"
            aria-label="Refresh traces"
          >
            R
          </button>
        </div>

        <div className="space-y-2">
          {runs.map((run) => (
            <button
              key={run.trace_id}
              type="button"
              onClick={() => setSelected(run.trace_id)}
              className={`w-full rounded-md border px-3 py-3 text-left transition ${
                selected === run.trace_id ? "border-pine bg-teal-50" : "border-line bg-white hover:bg-mist"
              }`}
            >
              <p className="font-mono text-xs text-slate-600">{run.trace_id}</p>
              <p className="mt-2 text-sm font-medium text-ink">{shortText(run.request?.user_query, 74)}</p>
              <p className="mt-2 text-xs text-slate-500">{run.stop_reason ?? "running"} · {formatMs(run.metrics?.total_latency_ms)}</p>
            </button>
          ))}
          {runs.length === 0 ? (
            <div className="rounded-md border border-dashed border-line p-4 text-sm leading-6 text-slate-600">
              저장된 trace가 없습니다. 사용자 페이지에서 Agent를 실행하면 여기에 표시됩니다.
            </div>
          ) : null}
        </div>
      </aside>

      <section className="space-y-5">
        {error ? (
          <div className="rounded-lg border border-coral bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        ) : null}

        <div className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-pine">Selected trace</p>
              <h2 className="mt-1 text-2xl font-semibold text-ink">{trace?.trace_id ?? "Trace를 선택하세요"}</h2>
              <p className="mt-2 max-w-3xl leading-6 text-slate-600">
                {loading ? "Trace를 불러오는 중입니다." : shortText(trace?.request?.user_query, 220)}
              </p>
            </div>
            <div className="rounded-md border border-line bg-mist px-3 py-2 text-sm font-semibold text-ink">
              {trace?.model?.name ?? "-"}
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Total latency" value={formatMs(metrics?.total_latency_ms)} />
            <Metric label="Steps" value={`${metrics?.step_count ?? 0}`} />
            <Metric label="Tool calls" value={`${metrics?.tool_call_count ?? 0}`} />
            <Metric label="Tool errors" value={`${metrics?.tool_error_count ?? 0}`} />
          </div>
        </div>

        {trace ? (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
            <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold text-ink">Step timeline</h2>
                <span className="rounded-md bg-mist px-3 py-1 text-sm text-slate-600">
                  fallback {metrics?.fallback_count ?? 0}
                </span>
              </div>
              <div className="space-y-3">
                {trace.steps.map((step) => (
                  <button
                    key={`${step.step}-${step.name}`}
                    type="button"
                    onClick={() => setSelectedStep(step)}
                    className={`w-full rounded-lg border p-4 text-left ${stepTone(step)} ${
                      selectedStep?.step === step.step ? "ring-2 ring-pine" : ""
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <span className="grid h-8 w-8 place-items-center rounded-md bg-white font-mono text-sm text-ink">
                          {step.step}
                        </span>
                        <div>
                          <p className="font-semibold text-ink">{step.name}</p>
                          <p className="text-sm text-slate-600">{step.type}</p>
                        </div>
                      </div>
                      <span className="text-sm font-medium text-slate-700">{formatMs(step.latency_ms)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
              <div className="mb-4 flex items-center gap-2">
                <h2 className="text-xl font-semibold text-ink">Step detail</h2>
              </div>
              {selectedStep ? (
                <div className="space-y-4">
                  <div className="rounded-md border border-line bg-mist p-3">
                    <p className="font-semibold text-ink">{selectedStep.name}</p>
                    <p className="mt-1 text-sm text-slate-600">
                      {selectedStep.type} · {formatMs(selectedStep.latency_ms)}
                    </p>
                  </div>
                  <DetailBlock title="Arguments" value={selectedStep.arguments} />
                  <DetailBlock title="Result" value={selectedStep.result} />
                  <DetailBlock title="Error" value={selectedStep.error} />
                </div>
              ) : (
                <p className="text-slate-600">Timeline에서 step을 선택하세요.</p>
              )}
            </section>
          </div>
        ) : null}

        {trace ? (
          <section className="grid gap-5 xl:grid-cols-2">
            <article className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-xl font-semibold text-ink">Final answer</h2>
              </div>
              <pre className="leading-7 text-slate-700">{trace.final_answer}</pre>
            </article>
            <article className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
              <h2 className="mb-3 text-xl font-semibold text-ink">Safety policy</h2>
              <JsonBlock value={trace.safety} />
            </article>
          </section>
        ) : null}
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-mist p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
        {label}
      </div>
      <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function DetailBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold uppercase text-slate-500">{title}</h3>
      <JsonBlock value={value} />
    </div>
  );
}
