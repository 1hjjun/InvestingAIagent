"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type AgentRun = {
  trace_id: string;
  answer_text: string;
  chart_data: Record<string, unknown> | null;
  is_saved: boolean;
  stop_reason: string | null;
};

type Portfolio = {
  analytics?: {
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
  };
};

async function createRunWithUpload(input: { user_query: string; image?: File | null }) {
  const formData = new FormData();
  formData.append("user_query", input.user_query);
  if (input.image) {
    formData.append("image", input.image);
  }

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

async function getPortfolio() {
  const response = await fetch(`${API_BASE}/api/portfolio`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<Portfolio>;
}

const imageAnalysisQuery =
  "첨부한 포트폴리오 이미지에서 보이는 종목, 수량, 평가손익, 수익률을 정리하고 현재 포트폴리오의 테마 비중과 리스크를 설명해줘.";

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatKrw(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

export default function PortfolioPage() {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [lastTraceId, setLastTraceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getPortfolio().then(setPortfolio).catch(() => setPortfolio(null));
  }, []);

  const analytics = portfolio?.analytics;
  const themeAllocation = analytics?.theme_allocation ?? [];
  const conicGradient = useMemo(() => buildConicGradient(themeAllocation), [themeAllocation]);

  function updateImage(file: File | null) {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setImageFile(file);
    setPreviewUrl(file ? URL.createObjectURL(file) : null);
  }

  async function runImageAnalysis() {
    setError(null);

    if (!imageFile) {
      setError("먼저 포트폴리오 이미지를 선택하세요.");
      return;
    }

    setLoading(true);
    try {
      const runResult = await createRunWithUpload({
        user_query: imageAnalysisQuery,
        image: imageFile,
      });
      setLastTraceId(runResult.trace_id || null);
      getPortfolio().then(setPortfolio).catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 실행에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[440px_1fr]">
      <section className="space-y-5">
        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <p className="text-sm font-medium text-pine">Portfolio workspace</p>
          <h1 className="mt-1 text-3xl font-semibold text-ink">포트폴리오 입력</h1>
          <p className="mt-2 leading-7 text-slate-600">
            포트폴리오 이미지를 넣으면 보유 종목과 비중, 테마, 리스크를 분석합니다.
          </p>
        </section>

        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">포트폴리오 이미지</h2>
            <button
              type="button"
              onClick={runImageAnalysis}
              disabled={loading}
              className="rounded-md bg-pine px-3 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:bg-slate-400"
            >
              {loading ? "분석 중..." : "이미지 분석"}
            </button>
          </div>

          <input
            id="portfolio-image"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="sr-only"
            onChange={(event) => updateImage(event.target.files?.[0] ?? null)}
          />
          <label
            htmlFor="portfolio-image"
            className="mt-4 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-line bg-white px-4 py-5 text-center transition hover:border-pine hover:bg-mist"
          >
            <span className="mb-3 text-sm font-bold text-pine">UPLOAD</span>
            <span className="font-semibold text-ink">이미지 파일 선택</span>
            <span className="mt-1 text-sm leading-6 text-slate-600">PNG, JPG, JPEG, WEBP 파일을 사용할 수 있습니다.</span>
          </label>

          {imageFile ? (
            <div className="mt-3 rounded-md border border-line bg-mist p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="shrink-0 text-xs font-bold text-pine">IMG</span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{imageFile.name}</p>
                    <p className="text-xs text-slate-600">{formatBytes(imageFile.size)}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => updateImage(null)}
                  className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-line bg-white text-slate-600 hover:text-ink"
                  aria-label="선택한 이미지 제거"
                >
                  X
                </button>
              </div>
              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt="선택한 포트폴리오 이미지 미리보기"
                  className="mt-3 max-h-64 w-full rounded-md border border-line object-contain"
                />
              ) : null}
            </div>
          ) : null}
        </section>

        {error ? (
          <div className="rounded-md border border-coral/40 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </section>

      <section className="space-y-5">
        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-pine">Latest portfolio</p>
              <h2 className="mt-1 text-2xl font-semibold text-ink">최근 포트폴리오 대시보드</h2>
            </div>
            <a href="/journal" className="rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink hover:bg-mist">
              대화 노트
            </a>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-4">
            <Metric label="전체 시드" value={formatKrw(analytics?.total_seed_krw)} />
            <Metric label="시드 10%" value={formatKrw(analytics?.ten_percent_seed_krw)} />
            <Metric label="현금" value={formatKrw(analytics?.cash_krw)} />
            <Metric label="현금 비중" value={`${analytics?.cash_ratio_pct?.toFixed(2) ?? "-"}%`} />
          </div>

          {themeAllocation.length ? (
            <div className="mt-6 grid gap-6 xl:grid-cols-[240px_1fr]">
              <div className="grid place-items-center">
                <div className="grid h-52 w-52 place-items-center rounded-full" style={{ background: conicGradient }}>
                  <div className="grid h-28 w-28 place-items-center rounded-full bg-white text-center">
                    <span className="text-sm font-bold text-pine">테마</span>
                    <span className="text-xs font-semibold text-ink">비중</span>
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                {themeAllocation.slice(0, 8).map((item) => (
                  <div key={item.theme}>
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate text-slate-700">{item.theme_label}</span>
                      <span className="shrink-0 font-semibold text-ink">{item.allocation_pct.toFixed(2)}%</span>
                    </div>
                    <div className="mt-1 h-2 rounded-full bg-mist">
                      <div className="h-2 rounded-full bg-pine" style={{ width: `${Math.min(item.allocation_pct, 100)}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{formatKrw(item.value_krw)}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {loading || lastTraceId ? (
            <div className="mt-5 rounded-md border border-line bg-mist p-3 text-sm text-slate-700">
              {loading ? (
                <p className="font-semibold text-ink">이미지를 분석하는 중입니다.</p>
              ) : (
                <a
                  href={`/dev?trace=${lastTraceId}`}
                  className="font-semibold text-pine hover:underline"
                >
                  최근 분석 trace 보기
                </a>
              )}
            </div>
          ) : null}
        </section>
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

function buildConicGradient(items: { allocation_pct: number }[]) {
  if (!items.length) return "#e5e7eb";
  const colors = ["#0f766e", "#d99121", "#df6757", "#2563eb", "#7c3aed", "#16a34a", "#0891b2", "#db2777", "#64748b", "#ea580c"];
  let cursor = 0;
  const stops = items.map((item, index) => {
    const start = cursor;
    cursor += item.allocation_pct;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}
