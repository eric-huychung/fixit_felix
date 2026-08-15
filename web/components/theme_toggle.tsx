/**
 * Sun/moon toggle for light and dark mode.
 */

"use client";

import { MoonIcon, SunIcon } from "@/components/icons";
import { toggle_theme } from "@/lib/theme";

/**
 * Renders a light/dark toggle.
 *
 * Both icons are always in the markup and the stylesheet reveals whichever one
 * matches `html.dark`. That keeps this component's output independent of the
 * current theme, so the server and the client render the same thing and there
 * is nothing to mismatch during hydration — no mounted flag, no placeholder.
 */
export function ThemeToggle() {
  return (
    <button
      type="button"
      className="icon_button"
      title="Toggle theme"
      aria-label="Toggle light and dark mode"
      onClick={() => toggle_theme()}
    >
      <MoonIcon className="when_light" />
      <SunIcon className="when_dark" />
    </button>
  );
}
