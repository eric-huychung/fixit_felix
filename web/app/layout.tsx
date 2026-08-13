/**
 * Root layout: theme provider, header, global styles.
 */

import type { Metadata } from "next";
import { SiteHeader } from "@/components/site_header";
import { ThemeProviderClient } from "@/components/theme_provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Felix",
  description: "Local thin UI over Felix scan / diagnose / artifacts",
};

/**
 * @param props - App Router children
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProviderClient>
          <SiteHeader />
          {children}
        </ThemeProviderClient>
      </body>
    </html>
  );
}
