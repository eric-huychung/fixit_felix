/**
 * Loading primitives: an inline spinner and a content skeleton.
 */

// Fixed widths rather than random ones — a skeleton that differs between the
// server and the client render would itself cause a hydration mismatch.
const SKELETON_WIDTHS = ["100%", "82%", "94%", "68%", "88%", "76%"];

/**
 * Small spinner with a text label, for inline "working on it" states.
 *
 * @param props - Optional label, defaults to "Loading…"
 */
export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <span className="spinner_row" role="status">
      <span className="spinner" aria-hidden />
      {label}
    </span>
  );
}

/**
 * Grey placeholder bars standing in for text that has not arrived.
 *
 * @param props - How many bars to draw
 */
export function SkeletonLines({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton" role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <span
          key={index}
          className="skeleton_line"
          style={{ width: SKELETON_WIDTHS[index % SKELETON_WIDTHS.length] }}
        />
      ))}
    </div>
  );
}
