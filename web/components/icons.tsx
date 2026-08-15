/**
 * Inline 16px stroke icons.
 *
 * Hand-rolled rather than pulled from an icon package: the UI needs six glyphs,
 * and they inherit `currentColor` so both themes are handled by the stylesheet.
 */

type icon_props = {
  className?: string;
};

/**
 * @param props - Optional class applied to the svg root
 */
function Glyph({ className, children }: icon_props & { children: React.ReactNode }) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Shown in dark mode — clicking it returns to light. */
export function SunIcon({ className }: icon_props) {
  return (
    <Glyph className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Glyph>
  );
}

/** Shown in light mode — clicking it switches to dark. */
export function MoonIcon({ className }: icon_props) {
  return (
    <Glyph className={className}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </Glyph>
  );
}

export function CopyIcon({ className }: icon_props) {
  return (
    <Glyph className={className}>
      <rect x="9" y="9" width="12" height="12" rx="2" />
      <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </Glyph>
  );
}

export function CheckIcon({ className }: icon_props) {
  return (
    <Glyph className={className}>
      <path d="M20 6 9 17l-5-5" />
    </Glyph>
  );
}

export function SearchIcon({ className }: icon_props) {
  return (
    <Glyph className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Glyph>
  );
}

export function AlertIcon({ className }: icon_props) {
  return (
    <Glyph className={className}>
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4M12 17h.01" />
    </Glyph>
  );
}
