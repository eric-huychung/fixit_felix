/**
 * Eval delta strip shown on the Scan home view.
 */

"use client";

import { useEffect, useState } from "react";
import { fetch_headline } from "@/lib/api_client";
import type { headline } from "@/lib/types";

/**
 * Loads and displays baseline vs treatment pass rates from RESULTS.md.
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
        <span className="status">Loading eval headline…</span>
      </div>
    );
  }

  return (
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
      {data.summary ? <span className="status">{data.summary}</span> : null}
    </div>
  );
}
