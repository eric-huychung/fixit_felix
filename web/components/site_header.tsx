/**
 * Top chrome: brand, Scan / Artifacts / Diagnose nav, theme toggle.
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme_toggle";

const LINKS = [
  { href: "/", label: "Scan" },
  { href: "/artifacts", label: "Artifacts" },
  { href: "/diagnose", label: "Diagnose" },
] as const;

/**
 * Sticky header for the local UI shell.
 */
export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="site_header">
      <div className="site_header_inner">
        <Link href="/" className="brand">
          Felix
        </Link>
        <nav className="nav" aria-label="Primary">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              aria-current={pathname === link.href ? "page" : undefined}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
