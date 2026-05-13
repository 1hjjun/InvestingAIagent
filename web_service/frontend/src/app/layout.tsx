import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "@wanteddev/wds/global.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Mind Investing AI",
  description: "Personal investing and rebalancing assistant",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" />
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-jp-dynamic-subset.min.css"
        />
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.min.css"
        />
      </head>
      <body>
        <Providers>
        <header className="sticky top-0 z-30 border-b border-line/70 bg-white/85 backdrop-blur-xl">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
            <Link href="/" className="flex items-center gap-3 text-[15px] font-bold text-ink">
              <span className="grid h-9 w-9 place-items-center rounded-md bg-ink text-sm text-white shadow-sm">
                MI
              </span>
              Mind Investing AI
            </Link>
            <nav className="flex items-center gap-1 rounded-md border border-line/80 bg-white/70 p-1 text-sm font-semibold text-slate-600 shadow-sm">
              <Link className="rounded px-3 py-2 hover:bg-mist hover:text-ink" href="/">
                Rebalance
              </Link>
              <Link className="rounded px-3 py-2 hover:bg-mist hover:text-ink" href="/portfolio">
                Portfolio
              </Link>
              <Link className="rounded px-3 py-2 hover:bg-mist hover:text-ink" href="/macro">
                Macro
              </Link>
              <Link className="rounded px-3 py-2 hover:bg-mist hover:text-ink" href="/RAG">
                RAG
              </Link>
              <Link className="rounded px-3 py-2 hover:bg-mist hover:text-ink" href="/journal">
                Journal
              </Link>
              <Link className="rounded px-3 py-2 hover:bg-mist hover:text-ink" href="/dev">
                Dev
              </Link>
            </nav>
          </div>
        </header>
        {children}
        </Providers>
      </body>
    </html>
  );
}
