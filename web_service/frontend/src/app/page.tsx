"use client";

import { FormEvent, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type AgentRun = {
  trace_id: string;
  answer_text: string;
  chart_data: Record<string, unknown> | null;
  is_saved: boolean;
  stop_reason: string | null;
};

async function createRunWithUpload(input: {
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

const sampleQuestion =
  "포트폴리오 이미지에서 현재 자산 비중을 정리하고, YouTube 영상과 시장 상황을 참고해서 ETF 리밸런싱 의견을 알려줘. 마지막에는 오늘 매매 일지로 저장해줘.";

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

export default function UserPage() {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("https://www.youtube.com/watch?v=webDqOfjx8E");
  const [query, setQuery] = useState(sampleQuestion);
  const [result, setResult] = useState<AgentRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const chartSummary = useMemo(() => {
    if (!result?.chart_data) return null;
    return JSON.stringify(result.chart_data, null, 2);
  }, [result]);

  function updateImage(file: File | null) {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setImageFile(file);
    setPreviewUrl(file ? URL.createObjectURL(file) : null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const run = await createRunWithUpload({
        user_query: query,
        youtube_url: youtubeUrl || undefined,
        image: imageFile,
      });
      setResult(run);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 실행에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 lg:grid-cols-[420px_1fr]">
      <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-pine">ETF portfolio coach</p>
            <h1 className="mt-2 text-3xl font-semibold text-ink">리밸런싱 실행</h1>
          </div>
          <span className="grid h-11 w-11 place-items-center rounded-lg bg-coral text-white">
            AI
          </span>
        </div>

        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <span className="text-sm font-medium text-ink">포트폴리오 이미지</span>
            <input
              id="portfolio-image"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={(event) => updateImage(event.target.files?.[0] ?? null)}
            />
            <label
              htmlFor="portfolio-image"
              className="mt-2 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-line bg-white px-4 py-5 text-center transition hover:border-pine hover:bg-mist"
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
                    className="mt-3 max-h-56 w-full rounded-md border border-line object-contain"
                  />
                ) : null}
              </div>
            ) : (
              <p className="mt-2 text-xs leading-5 text-slate-500">파일 없이 실행하면 이미지 분석 도구는 건너뛸 수 있습니다.</p>
            )}
          </div>

          <label className="block">
            <span className="text-sm font-medium text-ink">YouTube URL</span>
            <input
              value={youtubeUrl}
              onChange={(event) => setYoutubeUrl(event.target.value)}
              className="mt-2 w-full rounded-md border border-line bg-white px-3 py-3 outline-none focus:border-pine"
              placeholder="https://www.youtube.com/watch?v=..."
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-ink">요청 내용</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="mt-2 min-h-40 w-full resize-y rounded-md border border-line bg-white px-3 py-3 leading-6 outline-none focus:border-pine"
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-pine px-4 py-3 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {loading ? "분석 중..." : "Agent 실행"}
          </button>
        </form>

        {error ? (
          <div className="mt-4 rounded-md border border-coral/40 bg-red-50 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </section>

      <section className="min-h-[680px] rounded-lg border border-line bg-white/94 p-5 shadow-soft">
        {!result && !loading ? (
          <div className="flex h-full min-h-[560px] flex-col items-center justify-center text-center">
            <span className="mb-5 grid h-16 w-16 place-items-center rounded-lg bg-amber text-white">
              PIE
            </span>
            <h2 className="text-2xl font-semibold text-ink">ETF 리밸런싱 결과가 여기에 표시됩니다</h2>
            <p className="mt-3 max-w-xl leading-7 text-slate-600">
              이미지, YouTube 영상, 요청 내용을 바탕으로 Agent가 필요한 도구를 호출하고 최종 의견을 생성합니다.
            </p>
          </div>
        ) : null}

        {loading ? (
          <div className="flex h-full min-h-[560px] flex-col items-center justify-center text-center">
            <span className="mb-4 text-sm font-bold text-pine">RUNNING</span>
            <h2 className="text-xl font-semibold text-ink">Agent가 포트폴리오를 분석하고 있습니다</h2>
            <p className="mt-2 text-slate-600">실행이 끝나면 trace가 자동으로 저장됩니다.</p>
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
              <div className="rounded-lg border border-line bg-mist p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
                  종료 사유
                </div>
                <p className="mt-2 font-semibold text-ink">{result.stop_reason ?? "final_answer"}</p>
              </div>
              <div className="rounded-lg border border-line bg-mist p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
                  일지 저장
                </div>
                <p className="mt-2 font-semibold text-ink">{result.is_saved ? "저장됨" : "저장 안 됨"}</p>
              </div>
            </div>

            <article className="rounded-lg border border-line bg-white p-5">
              <h2 className="mb-3 text-xl font-semibold text-ink">최종 리밸런싱 의견</h2>
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
