import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mind Investing AI",
  description: "Personal investing and rebalancing assistant",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <header className="border-b border-line/80 bg-white/88 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
            <Link href="/" className="flex items-center gap-3 font-semibold text-ink">
              <span className="grid h-10 w-10 place-items-center rounded-lg bg-pine text-white">
                MI
              </span>
              Mind Investing AI
            </Link>
            <nav className="flex items-center gap-2 text-sm">
              <Link className="rounded-md px-3 py-2 text-ink hover:bg-mist" href="/">
                Rebalance
              </Link>
              <Link className="rounded-md px-3 py-2 text-ink hover:bg-mist" href="/portfolio">
                Portfolio
              </Link>
              <Link className="rounded-md px-3 py-2 text-ink hover:bg-mist" href="/macro">
                Macro
              </Link>
              <Link className="rounded-md px-3 py-2 text-ink hover:bg-mist" href="/dashboard">
                Dashboard
              </Link>
              <Link className="rounded-md px-3 py-2 text-ink hover:bg-mist" href="/chat">
                Chat
              </Link>
              <Link className="rounded-md px-3 py-2 text-ink hover:bg-mist" href="/dev">
                Dev
              </Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
