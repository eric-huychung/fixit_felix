/**
 * Eval delta strip shown on the Scan home view.
 */

"use client";

import { useEffect, useState } from "react";
import { Spinner } from "@/components/loading";
import { fetch_headline } from "@/lib/api_client";
import type { headline } from "@/lib/types";

/**
 * Shows last local eval when present; otherwise published RESULTS.md.
 */
export function HeadlineStrip() {
  const [data, set_data] = useState<headline | null>(null);
  const [error, set_error] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch_headline()
      .then((h) => {
        if (!cancelled) set_data(h);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          set_error(err instanceof Error ? err.message : "Failed to load headline");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="headline">
        <span className="status error">{error} (is the API running?)</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="headline">
        <Spinner label="Loading RESULTS…" />
      </div>
    );
  }

  const note =
    data.source === "live"
      ? format_live_note(data)
      : "Published RESULTS (not this session).";

  return (
    <div className="headline_block">
      <p className="section_note">{note}</p>
      <div className="headline">
        <div className="metric">
          <strong>Baseline</strong>
          {data.baseline_pass_rate ?? "—"}
        </div>
        <div className="metric">
          <strong>Treatment</strong>
          {data.treatment_pass_rate ?? "—"}
        </div>
        <div className="metric delta">
          <strong>Delta</strong>
          {data.delta ?? "—"}
        </div>
      </div>
    </div>
  );
}

function format_live_note(data: headline): string {
  const parts = ["Last eval"];
  if (data.object_name) parts.push(data.object_name);
  if (data.ran_at) parts.push(format_when(data.ran_at));
  return parts.join(" · ");
}

function format_when(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
