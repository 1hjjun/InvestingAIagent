"use client";

import { useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type AgentRun = {
  trace_id: string;
  answer_text: string;
  chart_data: Record<string, unknown> | null;
  is_saved: boolean;
  stop_reason: string | null;
};

async function createMacroRun(urls: string[]) {
  const userQuery = [
    "아래 YouTube 영상들을 참고해서 현재 매크로 경제 상황을 분석해줘.",
    "금리, 달러, 환율, 원자재, VIX, 경기 사이클, 위험자산 심리, 미국 ETF/성장주/반도체/배당주에 주는 영향을 나눠서 설명해줘.",
    "각 영상의 핵심 주장과 서로 같은 점/다른 점을 비교하고, 마지막에는 내 포트폴리오 관점에서 체크해야 할 리스크와 관찰 지표를 정리해줘.",
    "",
    ...urls.map((url, index) => `YouTube URL ${index + 1}: ${url}`),
  ].join("\n");

  const formData = new FormData();
  formData.append("user_query", userQuery);
  formData.append("youtube_url", urls.join("\n"));

  const response = await fetch(`${API_BASE}/api/runs/upload`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<AgentRun>;
}

export default function MacroPage() {
  const [urls, setUrls] = useState(["", "", ""]);
  const [result, setResult] = useState<AgentRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const activeUrls = useMemo(() => urls.map((url) => url.trim()).filter(Boolean), [urls]);
  const chartSummary = useMemo(() => {
    if (!result?.chart_data) return null;
    return JSON.stringify(result.chart_data, null, 2);
  }, [result]);

  function updateUrl(index: number, value: string) {
    setUrls((current) => current.map((url, itemIndex) => (itemIndex === index ? value : url)));
  }

  async function runMacroAnalysis() {
    setError(null);
    if (!activeUrls.length) {
      setError("YouTube URL을 1개 이상 입력하세요.");
      return;
    }

    setLoading(true);
    try {
      const run = await createMacroRun(activeUrls.slice(0, 3));
      setResult(run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "매크로 분석에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[440px_1fr]">
      <section className="space-y-5">
        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <p className="text-sm font-medium text-pine">Macro workspace</p>
          <h1 className="mt-1 text-3xl font-semibold text-ink">매크로 분석</h1>
          <p className="mt-2 leading-7 text-slate-600">
            YouTube 영상 최대 3개를 넣고 금리, 환율, 심리, 섹터 영향을 한 번에 비교합니다.
          </p>
        </section>

        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">YouTube URL</h2>
            <button
              type="button"
              onClick={runMacroAnalysis}
              disabled={loading}
              className="rounded-md bg-pine px-3 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:bg-slate-400"
            >
              {loading ? "분석 중..." : "매크로 분석"}
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {urls.map((url, index) => (
              <label key={index} className="block">
                <span className="text-sm font-medium text-slate-600">영상 {index + 1}</span>
                <input
                  value={url}
                  onChange={(event) => updateUrl(index, event.target.value)}
                  className="mt-2 w-full rounded-md border border-line bg-white px-3 py-3 outline-none focus:border-pine"
                  placeholder="https://www.youtube.com/watch?v=..."
                />
              </label>
            ))}
          </div>
        </section>

        {error ? (
          <div className="rounded-md border border-coral/40 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </section>

      <section className="min-h-[640px] rounded-lg border border-line bg-white/94 p-5 shadow-soft">
        {!result && !loading ? (
          <div className="flex min-h-[560px] flex-col items-center justify-center text-center">
            <span className="mb-5 grid h-16 w-16 place-items-center rounded-lg bg-amber text-white">MAC</span>
            <h2 className="text-2xl font-semibold text-ink">매크로 분석 결과가 여기에 표시됩니다</h2>
            <p className="mt-3 max-w-xl leading-7 text-slate-600">
              영상 URL을 입력하면 각 영상의 주장과 현재 시장환경을 연결해서 정리합니다.
            </p>
          </div>
        ) : null}

        {loading ? (
          <div className="flex min-h-[560px] flex-col items-center justify-center text-center">
            <span className="mb-4 text-sm font-bold text-pine">RUNNING</span>
            <h2 className="text-xl font-semibold text-ink">매크로 자료를 분석하고 있습니다</h2>
            <p className="mt-2 text-slate-600">영상 자막과 시장 지표를 함께 확인합니다.</p>
          </div>
        ) : null}

        {result ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
              <div>
                <p className="text-sm font-medium text-pine">Trace ID</p>
                <p className="font-mono text-sm text-slate-700">{result.trace_id}</p>
              </div>
              <a
                href={`/dev?trace=${result.trace_id}`}
                className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:bg-mist"
              >
                개발자 trace 보기
              </a>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Metric label="종료 사유" value={result.stop_reason ?? "final_answer"} />
              <Metric label="분석 영상" value={`${activeUrls.length}개`} />
            </div>

            <article className="rounded-lg border border-line bg-white p-5">
              <h2 className="mb-3 text-xl font-semibold text-ink">매크로 분석 결과</h2>
              <pre className="whitespace-pre-wrap break-words leading-7 text-slate-700">{result.answer_text}</pre>
            </article>

            {chartSummary ? (
              <article className="rounded-lg border border-line bg-ink p-5 text-white">
                <h2 className="mb-3 text-lg font-semibold">Chart data</h2>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-100">
                  {chartSummary}
                </pre>
              </article>
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-mist p-3">
      <p className="text-xs font-medium text-slate-600">{label}</p>
      <p className="mt-1 text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}
