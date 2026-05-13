"use client";

import { AppRouterCacheProvider } from "@wanteddev/wds-nextjs";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return <AppRouterCacheProvider>{children}</AppRouterCacheProvider>;
}
