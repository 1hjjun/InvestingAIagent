"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

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

type Journal = {
  date: string;
  title: string;
  subtitle?: string;
  conversation_count?: number;
  article: string;
};

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function getPortfolio() {
  return request<Portfolio>("/api/portfolio");
}

function getJournals() {
  return request<{ journals: Journal[] }>("/api/journals");
}

function formatKrw(value?: number | null) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value).toLocaleString("ko-KR")}원`;
}

function shortText(value?: string | null, max = 120) {
  if (!value) return "-";
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

export default function DashboardPage() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [journals, setJournals] = useState<Journal[]>([]);
  const [selectedJournal, setSelectedJournal] = useState(0);

  useEffect(() => {
    getPortfolio().then(setPortfolio).catch(() => setPortfolio(null));
    getJournals().then((payload) => setJournals(payload.journals)).catch(() => setJournals([]));
  }, []);

  const analytics = portfolio?.analytics;
  const themeAllocation = analytics?.theme_allocation ?? [];
  const conicGradient = useMemo(() => buildConicGradient(themeAllocation), [themeAllocation]);

  return (
    <main className="mx-auto grid max-w-7xl gap-6 px-5 py-8 xl:grid-cols-[380px_1fr]">
      <aside className="space-y-5">
        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-md bg-pine text-white">PF</span>
            <div>
              <p className="text-sm font-medium text-pine">Portfolio dashboard</p>
              <h1 className="text-2xl font-semibold text-ink">내 투자 현황</h1>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <Metric label="전체 시드" value={formatKrw(analytics?.total_seed_krw)} />
            <Metric label="시드 10%" value={formatKrw(analytics?.ten_percent_seed_krw)} />
            <Metric label="현금" value={formatKrw(analytics?.cash_krw)} />
            <Metric label="현금 비중" value={`${analytics?.cash_ratio_pct?.toFixed(2) ?? "-"}%`} />
          </div>

          {themeAllocation.length ? (
            <div className="mt-6">
              <div className="mx-auto grid h-52 w-52 place-items-center rounded-full" style={{ background: conicGradient }}>
                <div className="grid h-28 w-28 place-items-center rounded-full bg-white text-center">
                  <span className="text-sm font-bold text-pine">테마</span>
                  <span className="text-xs font-semibold text-ink">비중</span>
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">테마별 배분</h2>
          <div className="mt-4 space-y-3">
            {themeAllocation.map((item) => (
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
        </section>
      </aside>

      <section className="space-y-5">
        <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
          <p className="text-sm font-medium text-pine">Conversation journal</p>
          <h2 className="mt-1 text-2xl font-semibold text-ink">날짜별 대화 노트</h2>
          <p className="mt-2 max-w-2xl leading-7 text-slate-600">
            질문과 답변을 날짜별 글로 모아둔 공간입니다. 카드를 선택하면 블로그 글처럼 펼쳐집니다.
          </p>
        </section>

        {journals.length ? (
          <section className="grid gap-4 lg:grid-cols-[300px_1fr]">
            <div className="space-y-2">
              {journals.slice(0, 10).map((journal, index) => (
                <button
                  key={journal.date}
                  type="button"
                  onClick={() => setSelectedJournal(index)}
                  className={`w-full rounded-md border px-3 py-3 text-left transition ${
                    selectedJournal === index ? "border-pine bg-teal-50" : "border-line bg-white/94 hover:bg-mist"
                  }`}
                >
                  <p className="text-xs font-medium text-pine">{journal.date} · {journal.conversation_count ?? 0}개 대화</p>
                  <p className="mt-2 font-semibold leading-6 text-ink">{journal.title}</p>
                  <p className="mt-1 text-sm leading-5 text-slate-600">{shortText(journal.subtitle, 88)}</p>
                </button>
              ))}
            </div>
            <article className="rounded-lg border border-line bg-white/94 p-6 shadow-soft">
              <pre className="whitespace-pre-wrap break-words leading-7 text-slate-700">
                {journals[Math.min(selectedJournal, journals.length - 1)]?.article}
              </pre>
            </article>
          </section>
        ) : (
          <section className="rounded-lg border border-dashed border-line bg-white/94 p-6 text-sm leading-6 text-slate-600">
            아직 저장된 대화 노트가 없습니다. Agent 실행 결과가 저장되면 날짜별 글이 만들어집니다.
          </section>
        )}
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
