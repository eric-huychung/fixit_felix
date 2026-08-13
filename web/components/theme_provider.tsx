/**
 * next-themes provider wrapper for light/dark mode.
 */

"use client";

import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

/**
 * @param props - Children to wrap with theme context
 */
export function ThemeProviderClient({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      {children}
    </ThemeProvider>
  );
}
