"use client";

import { FormEvent, useState } from "react";

const answerStyles = ["해석/코칭 모드", "자료 엄격 모드", "아이디어 확장 모드"];
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ReferenceChunk = {
  chunk_id: string;
  text: string;
  metadata: Record<string, unknown>;
  distance?: number | null;
};

type ChatResponse = {
  answer: string;
  chunks: ReferenceChunk[];
  image_review?: string;
  memory?: Record<string, unknown> | null;
};

async function askPdfAssistant(input: {
  question: string;
  top_k: number;
  answer_style: string;
  pdf_only: boolean;
  include_portfolio: boolean;
  conservative_view: boolean;
  use_vision: boolean;
  max_images: number;
  conversation_history: ChatMessage[];
}) {
  const response = await fetch(`${API_BASE}/api/pdf-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
    cache: "no-store",
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<ChatResponse>;
}

export default function RagPage() {
  const [question, setQuestion] = useState("내 포트폴리오를 중장기 관점에서 평가해줘");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topK, setTopK] = useState(3);
  const [answerStyle, setAnswerStyle] = useState(answerStyles[0]);
  const [pdfOnly, setPdfOnly] = useState(false);
  const [includePortfolio, setIncludePortfolio] = useState(true);
  const [conservativeView, setConservativeView] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) return;

    const userMessage: ChatMessage = { role: "user", content: question.trim() };
    const history = messages.slice(-8);
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);

    try {
      const response = await askPdfAssistant({
        question: userMessage.content,
        top_k: topK,
        answer_style: answerStyle,
        pdf_only: pdfOnly,
        include_portfolio: includePortfolio,
        conservative_view: conservativeView,
        use_vision: false,
        max_images: 2,
        conversation_history: history,
      });
      setResult(response);
      setMessages((prev) => [...prev, { role: "assistant", content: response.answer }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "답변 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 xl:grid-cols-[340px_1fr]">
      <aside className="space-y-5">
        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <p className="text-sm font-medium text-pine">Investment RAG</p>
          <h1 className="mt-1 text-2xl font-semibold text-ink">투자 RAG</h1>
          <p className="mt-2 leading-7 text-slate-600">
            투자 PDF 근거, 현재 포트폴리오, 대화 메모리를 함께 넣어 답변합니다.
          </p>
        </section>

        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">답변 설정</h2>

          <label className="mt-5 block text-sm font-medium text-ink">
            검색할 주제 수
            <input
              className="mt-2 w-full accent-pine"
              type="range"
              min={1}
              max={5}
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
            <span className="text-slate-600">{topK}개</span>
          </label>

          <label className="mt-4 block text-sm font-medium text-ink">
            답변 스타일
            <select
              className="mt-2 w-full rounded-md border border-line bg-white px-3 py-2 outline-none focus:border-pine"
              value={answerStyle}
              onChange={(event) => setAnswerStyle(event.target.value)}
            >
              {answerStyles.map((style) => (
                <option key={style}>{style}</option>
              ))}
            </select>
          </label>

          <Toggle label="PDF 근거만 사용" value={pdfOnly} onChange={setPdfOnly} />
          <Toggle label="포트폴리오 관점 포함" value={includePortfolio} onChange={setIncludePortfolio} />
          <Toggle label="보수적 관점으로 답변" value={conservativeView} onChange={setConservativeView} />
        </section>
      </aside>

      <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
        <form className="space-y-3" onSubmit={onSubmit}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            className="min-h-28 w-full resize-y rounded-md border border-line bg-white px-4 py-3 leading-7 outline-none focus:border-pine"
            placeholder="예: 내 포트폴리오를 중장기 관점에서 평가해줘"
          />
          <button
            type="submit"
            disabled={loading}
            className="inline-flex w-full items-center justify-center rounded-md bg-pine px-4 py-3 font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {loading ? "자료 검색과 답변 생성 중..." : "질문하기"}
          </button>
        </form>

        {error ? (
          <div className="mt-4 rounded-md border border-coral/40 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        ) : null}

        <div className="mt-6 space-y-4">
          {messages.length === 0 ? (
            <div className="rounded-lg border border-dashed border-line bg-mist p-6 text-center">
              <p className="font-semibold text-ink">질문을 입력하면 PDF 근거와 포트폴리오를 함께 분석합니다.</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">답변에는 참고 페이지와 검색된 chunk가 함께 표시됩니다.</p>
            </div>
          ) : (
            messages.slice(-8).map((message, index) => (
              <article
                key={`${message.role}-${index}`}
                className={`rounded-lg border p-4 ${
                  message.role === "user" ? "border-line bg-mist" : "border-pine/30 bg-teal-50"
                }`}
              >
                <div className="mb-2 text-sm font-semibold text-ink">{message.role === "user" ? "나" : "AI 파트너"}</div>
                <pre className="whitespace-pre-wrap break-words leading-7 text-slate-700">{message.content}</pre>
              </article>
            ))
          )}
        </div>

        {result?.chunks?.length ? <ReferenceList chunks={result.chunks} /> : null}
      </section>
    </main>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (next: boolean) => void }) {
  return (
    <label className="mt-4 flex items-center justify-between gap-3 rounded-md border border-line bg-mist px-3 py-2 text-sm font-medium text-ink">
      {label}
      <input className="accent-pine" type="checkbox" checked={value} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function ReferenceList({ chunks }: { chunks: ReferenceChunk[] }) {
  return (
    <div className="mt-6 rounded-lg border border-line bg-white p-4">
      <h2 className="mb-3 text-lg font-semibold text-ink">참고 자료</h2>
      <div className="space-y-3">
        {chunks.map((chunk, index) => (
          <details key={chunk.chunk_id ?? index} className="rounded-md border border-line bg-mist p-3">
            <summary className="cursor-pointer font-semibold text-ink">
              {index + 1}. page {String(chunk.metadata?.pages ?? chunk.metadata?.page ?? "-")} · {String(chunk.metadata?.topic ?? "")}
            </summary>
            <p className="mt-2 text-xs text-slate-500">{String(chunk.metadata?.source_path ?? chunk.metadata?.source_paths ?? "")}</p>
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">
              {chunk.text}
            </pre>
          </details>
        ))}
      </div>
    </div>
  );
}
