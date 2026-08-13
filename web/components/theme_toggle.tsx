/**
 * Sun/moon toggle that persists theme via next-themes (localStorage).
 */

"use client";

import { useTheme } from "next-themes";

/**
 * Renders a light/dark toggle.
 *
 * `resolvedTheme` is undefined until next-themes has read localStorage on the
 * client, which doubles as the mount signal — rendering a placeholder until
 * then avoids a hydration mismatch without tracking mounted state ourselves.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  if (resolvedTheme === undefined) {
    return (
      <button type="button" className="ghost" disabled tabIndex={-1} aria-hidden>
        Theme
      </button>
    );
  }

  const is_dark = resolvedTheme === "dark";
  return (
    <button
      type="button"
      className="ghost"
      aria-label={is_dark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={() => setTheme(is_dark ? "light" : "dark")}
    >
      {is_dark ? "Light" : "Dark"}
    </button>
  );
}
