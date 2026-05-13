"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type AgentRun = {
  trace_id: string;
  answer_text: string;
  chart_data: Record<string, unknown> | null;
  is_saved: boolean;
  stop_reason: string | null;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  imageName?: string;
  imageUrl?: string;
  traceId?: string;
};

type StoredMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  trace_id?: string | null;
  image_name?: string | null;
};

type ToolStep = {
  tool: string;
  detail: string;
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

async function getStoredMessages() {
  const response = await fetch(`${API_BASE}/api/conversations/rebalance-agent/messages`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Messages failed: ${response.status}`);
  }
  const payload = (await response.json()) as { messages: StoredMessage[] };
  return payload.messages.map((message) => ({
    id: `stored-${message.id}`,
    role: message.role,
    content: message.content,
    imageName: message.image_name ?? undefined,
    traceId: message.trace_id ?? undefined,
  })) satisfies ChatMessage[];
}

async function clearStoredMessages() {
  const response = await fetch(`${API_BASE}/api/conversations/rebalance-agent/messages`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Clear failed: ${response.status}`);
  }
}

const sampleQuestion =
  "포트폴리오 이미지와 시장 상황을 참고해서 지금 리밸런싱할 만한 포인트를 시나리오별로 정리해줘. 단정적인 매수/매도 지시는 하지 말고 판단 기준을 알려줘.";

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "안녕하세요. 포트폴리오 이미지나 YouTube URL을 곁들여 질문하면, 필요한 도구를 차례대로 호출해서 리밸런싱 관점을 정리해드릴게요.",
};

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function buildToolPlan(hasImage: boolean, hasYoutube: boolean, question: string): ToolStep[] {
  const steps: ToolStep[] = [];
  const portfolioRelated = /포트폴리오|리밸런싱|비중|자산|종목|테마|현금|시드|투자/i.test(question);

  if (!hasImage && portfolioRelated) {
    steps.push({
      tool: "portfolio_context",
      detail: "저장된 현재 포트폴리오와 대시보드 계산값을 불러와 기준 자산으로 삼는 중입니다.",
    });
  }

  if (hasImage) {
    steps.push({
      tool: "vision_extractor",
      detail: "첨부한 포트폴리오 이미지에서 종목, 수량, 평가손익을 읽는 중입니다.",
    });
    steps.push({
      tool: "portfolio_allocation_calculator",
      detail: "이미지에서 읽은 자산을 기준으로 비중과 테마 배분을 계산하는 중입니다.",
    });
  }

  if (hasYoutube) {
    steps.push({
      tool: "youtube_sentiment",
      detail: "YouTube 자막을 읽고 투자 관점의 핵심 주장과 분위기를 요약하는 중입니다.",
    });
  }

  if (/거시|매크로|금리|환율|달러|vix|시장|경기|원자재/i.test(question) || hasYoutube) {
    steps.push({
      tool: "market_macro",
      detail: "금리, 환율, VIX, 원자재, 위험자산 심리를 함께 확인하는 중입니다.",
    });
  }

  steps.push({
    tool: "reasoning",
    detail: "수집한 근거를 연결해서 리밸런싱 시나리오와 리스크를 정리하는 중입니다.",
  });

  return steps;
}

export default function RebalanceAgentPage() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState("");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [toolPlan, setToolPlan] = useState<ToolStep[]>([]);
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const selectedImageLabel = useMemo(() => {
    if (!imageFile) return "";
    return `${imageFile.name} · ${formatBytes(imageFile.size)}`;
  }, [imageFile]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, activeStepIndex, loading]);

  useEffect(() => {
    let cancelled = false;
    getStoredMessages()
      .then((storedMessages) => {
        if (!cancelled) {
          setMessages(storedMessages);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMessages([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!loading || !toolPlan.length) return undefined;
    const timer = window.setInterval(() => {
      setActiveStepIndex((current) => Math.min(current + 1, toolPlan.length - 1));
    }, 1500);
    return () => window.clearInterval(timer);
  }, [loading, toolPlan.length]);

  function updateImage(file: File | null) {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setImageFile(file);
    setPreviewUrl(file ? URL.createObjectURL(file) : null);
  }

  async function onClearConversation() {
    if (loading) return;
    try {
      await clearStoredMessages();
      setMessages([]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: makeId(),
          role: "system",
          content: err instanceof Error ? err.message : "대화 기록을 지우지 못했습니다.",
        },
      ]);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = query.trim();
    if (!question || loading) return;

    const imageUrlForMessage = previewUrl;
    const hasYoutube = Boolean(youtubeUrl.trim());
    const nextToolPlan = buildToolPlan(Boolean(imageFile), hasYoutube, question);

    setMessages((current) => [
      ...current,
      {
        id: makeId(),
        role: "user",
        content: hasYoutube ? `${question}\n\nYouTube: ${youtubeUrl.trim()}` : question,
        imageName: imageFile?.name,
        imageUrl: imageUrlForMessage ?? undefined,
      },
    ]);
    setToolPlan(nextToolPlan);
    setActiveStepIndex(0);
    setLoading(true);

    try {
      const run = await createRunWithUpload({
        user_query: question,
        youtube_url: youtubeUrl.trim() || undefined,
        image: imageFile,
      });
      setActiveStepIndex(nextToolPlan.length - 1);
      setMessages((current) => [
        ...current,
        {
          id: makeId(),
          role: "assistant",
          content: run.answer_text || "Agent가 답변을 생성하지 못했습니다.",
          traceId: run.trace_id,
        },
      ]);
      setQuery("");
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: makeId(),
          role: "system",
          content: err instanceof Error ? err.message : "Agent 실행에 실패했습니다.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function onQueryKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  return (
    <main className="mx-auto flex min-h-[calc(100vh-73px)] max-w-5xl flex-col px-5 py-6">
      <section className="mb-5 rounded-lg border border-line bg-white/92 p-5 shadow-soft">
        <p className="text-sm font-medium text-pine">ETF portfolio coach</p>
        <div className="mt-1 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-ink">리밸런싱 AI agent</h1>
            <p className="mt-2 leading-7 text-slate-600">
              질문을 남기면 Agent가 이미지, 영상, 시장 도구를 골라 호출하고 진행 상황을 보여줍니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onClearConversation}
            disabled={loading || historyLoading || messages.length === 0}
            className="rounded-md border border-line px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-mist disabled:cursor-not-allowed disabled:opacity-50"
          >
            대화 비우기
          </button>
        </div>
      </section>

      <section className="flex min-h-[520px] flex-1 flex-col rounded-lg border border-line bg-white/94 shadow-soft">
        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6">
          {historyLoading ? (
            <div className="rounded-lg border border-line bg-mist p-4 text-sm text-slate-600">
              저장된 대화를 불러오는 중입니다.
            </div>
          ) : messages.length === 0 ? (
            <MessageBubble message={welcomeMessage} />
          ) : null}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {loading ? (
            <div className="flex justify-start">
              <div className="max-w-3xl rounded-lg border border-line bg-mist p-4">
                <div className="mb-3 flex items-center gap-2">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-pine" />
                  <p className="font-semibold text-ink">Agent가 생각하고 있습니다</p>
                </div>
                <div className="space-y-2">
                  {toolPlan.map((step, index) => {
                    const state = index < activeStepIndex ? "done" : index === activeStepIndex ? "active" : "waiting";
                    return (
                      <div key={`${step.tool}-${index}`} className="flex gap-3 rounded-md bg-white/80 p-3 text-sm">
                        <span
                          className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${
                            state === "done" ? "bg-pine" : state === "active" ? "animate-pulse bg-amber" : "bg-line"
                          }`}
                        />
                        <div>
                          <p className="font-semibold text-ink">
                            {state === "done" ? "완료" : state === "active" ? "실행 중" : "대기"} · {step.tool}
                          </p>
                          <p className="mt-1 leading-6 text-slate-600">{step.detail}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : null}
          <div ref={scrollRef} />
        </div>

        <form className="border-t border-line bg-white/96 p-4" onSubmit={onSubmit}>
          {imageFile ? (
            <div className="mb-3 flex items-center gap-3 rounded-md border border-line bg-mist p-2">
              {previewUrl ? (
                <img src={previewUrl} alt="선택한 이미지" className="h-12 w-12 rounded-md object-cover" />
              ) : null}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{selectedImageLabel}</p>
                <p className="text-xs text-slate-500">대화에 함께 첨부됩니다.</p>
              </div>
              <button
                type="button"
                onClick={() => updateImage(null)}
                className="grid h-8 w-8 place-items-center rounded-md border border-line bg-white text-slate-600 hover:text-ink"
                aria-label="선택한 이미지 제거"
              >
                X
              </button>
            </div>
          ) : null}

          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="sr-only"
            onChange={(event) => updateImage(event.target.files?.[0] ?? null)}
          />

          <label className="mb-3 block">
            <span className="sr-only">YouTube URL</span>
            <input
              value={youtubeUrl}
              onChange={(event) => setYoutubeUrl(event.target.value)}
              className="w-full rounded-md border border-line bg-mist px-3 py-2 text-sm outline-none focus:border-pine"
              placeholder="YouTube URL을 같이 참고하려면 여기에 붙여넣기"
            />
          </label>

          <div className="flex items-end gap-2 rounded-lg border border-line bg-white p-2 focus-within:border-pine">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-md border border-line bg-mist text-xl font-semibold text-ink hover:bg-white"
              aria-label="이미지 첨부"
              title="이미지 첨부"
            >
              +
            </button>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onQueryKeyDown}
              className="max-h-44 min-h-12 flex-1 resize-none border-0 bg-transparent px-2 py-2 leading-6 outline-none"
              placeholder={sampleQuestion}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className="rounded-md bg-pine px-4 py-2.5 font-semibold text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {loading ? "실행 중" : "전송"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <article
        className={`max-w-3xl rounded-lg border p-4 ${
          isUser
            ? "border-pine bg-teal-50"
            : isSystem
              ? "border-coral/40 bg-red-50 text-red-800"
              : "border-line bg-white"
        }`}
      >
        <p className="mb-2 text-sm font-semibold text-ink">{isUser ? "나" : isSystem ? "시스템" : "리밸런싱 AI agent"}</p>
        {message.imageUrl ? (
          <img src={message.imageUrl} alt={message.imageName ?? "첨부 이미지"} className="mb-3 max-h-48 rounded-md border border-line object-contain" />
        ) : null}
        {message.imageName ? <p className="mb-2 text-xs text-slate-500">첨부 이미지: {message.imageName}</p> : null}
        <pre className="whitespace-pre-wrap break-words leading-7">{message.content}</pre>
        {message.traceId ? (
          <a href={`/dev?trace=${message.traceId}`} className="mt-3 inline-flex rounded-md border border-line px-3 py-2 text-sm font-semibold text-pine hover:bg-mist">
            실행 trace 보기
          </a>
        ) : null}
      </article>
    </div>
  );
}
