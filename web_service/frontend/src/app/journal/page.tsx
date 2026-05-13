"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Journal = {
  date: string;
  title: string;
  subtitle?: string;
  conversation_count?: number;
  article: string;
};

type JournalCard = {
  date: string;
  label: string;
  journal?: Journal;
};

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<T>;
}

function getJournals() {
  return request<{ journals: Journal[] }>("/api/journals");
}

function shortText(value?: string | null, max = 120) {
  if (!value) return "아직 이 날짜에는 저장된 대화 노트가 없습니다.";
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

function toDateKey(date: Date) {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function formatDateLabel(offset: number) {
  if (offset === 0) return "오늘";
  if (offset === -1) return "어제";
  if (offset === 1) return "내일";
  return offset < 0 ? `${Math.abs(offset)}일 전` : `${offset}일 후`;
}

export default function JournalPage() {
  const [journals, setJournals] = useState<Journal[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(() => toDateKey(new Date()));

  useEffect(() => {
    getJournals()
      .then((payload) => setJournals(payload.journals))
      .catch(() => setJournals([]))
      .finally(() => setLoading(false));
  }, []);

  const journalByDate = useMemo(() => {
    return new Map(journals.map((journal) => [journal.date, journal]));
  }, [journals]);

  const cards = useMemo<JournalCard[]>(() => {
    const today = new Date();
    return [-2, -1, 0, 1, 2].map((offset) => {
      const date = addDays(today, offset);
      const dateKey = toDateKey(date);
      return {
        date: dateKey,
        label: formatDateLabel(offset),
        journal: journalByDate.get(dateKey),
      };
    });
  }, [journalByDate]);

  const selectedJournal = journalByDate.get(selectedDate);

  return (
    <main className="mx-auto max-w-6xl px-5 py-8">
      <section className="rounded-lg border border-line bg-white/94 p-5 shadow-soft">
        <p className="text-sm font-medium text-pine">Conversation journal</p>
        <h1 className="mt-1 text-3xl font-semibold text-ink">날짜별 대화 노트</h1>
        <p className="mt-2 max-w-2xl leading-7 text-slate-600">
          Agent와 나눈 대화를 날짜별 글로 모아둔 공간입니다. 가운데 오늘 카드를 기준으로 전후 날짜를 살펴볼 수 있습니다.
        </p>
      </section>

      <section className="mt-6">
        <div className="grid gap-3 md:grid-cols-5">
          {cards.map((card, index) => {
            const isSelected = selectedDate === card.date;
            const isToday = index === 2;
            return (
              <button
                key={card.date}
                type="button"
                onClick={() => setSelectedDate(card.date)}
                className={`min-h-44 rounded-lg border p-4 text-left transition ${
                  isSelected
                    ? "border-pine bg-teal-50 shadow-soft"
                    : isToday
                      ? "border-amber bg-white/94 shadow-soft hover:bg-mist"
                      : "border-line bg-white/90 hover:bg-mist"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold text-pine">{card.label}</p>
                    <p className="mt-1 font-mono text-sm text-slate-600">{card.date}</p>
                  </div>
                  {isToday ? <span className="rounded-md bg-amber/15 px-2 py-1 text-xs font-semibold text-amber">TODAY</span> : null}
                </div>
                <p className="mt-4 font-semibold leading-6 text-ink">{card.journal?.title ?? "빈 노트"}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600">{shortText(card.journal?.subtitle, 82)}</p>
                <p className="mt-3 text-xs font-medium text-slate-500">{card.journal?.conversation_count ?? 0}개 대화</p>
              </button>
            );
          })}
        </div>
      </section>

      <section className="mt-6 rounded-lg border border-line bg-white/94 p-6 shadow-soft">
        {loading ? (
          <p className="text-sm leading-6 text-slate-600">대화 노트를 불러오는 중입니다.</p>
        ) : selectedJournal ? (
          <>
            <div className="border-b border-line pb-4">
              <p className="text-sm font-medium text-pine">{selectedJournal.date}</p>
              <h2 className="mt-1 text-2xl font-semibold text-ink">{selectedJournal.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{selectedJournal.subtitle}</p>
            </div>
            <article className="pt-5">
              <pre className="whitespace-pre-wrap break-words leading-7 text-slate-700">{selectedJournal.article}</pre>
            </article>
          </>
        ) : (
          <div className="py-8 text-center">
            <p className="text-lg font-semibold text-ink">{selectedDate} 노트가 아직 없습니다.</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              해당 날짜에 Agent와 대화하면 이곳에 블로그 글처럼 정리됩니다.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
