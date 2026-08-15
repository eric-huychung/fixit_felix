/**
 * Root layout: theme bootstrap, header, global styles.
 */

import type { Metadata } from "next";
import { SiteHeader } from "@/components/site_header";
import { THEME_BOOTSTRAP } from "@/lib/theme";
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
      <head>
        {/* Server-rendered so React only ever hydrates this tag, never creates
            it on the client — which is what makes it run at all. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
