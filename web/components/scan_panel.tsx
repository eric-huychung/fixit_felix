/**
 * Object picker + Run Scan primary action for the home view.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { run_scan } from "@/lib/api_client";

/**
 * Triggers a Felix scan via the local API and navigates to Artifacts on success.
 */
export function ScanPanel() {
  const router = useRouter();
  const [object_name, set_object_name] = useState("Opportunity");
  const [use_fixtures, set_use_fixtures] = useState(false);
  const [busy, set_busy] = useState(false);
  const [status, set_status] = useState<string | null>(null);
  const [error, set_error] = useState<string | null>(null);

  /**
   * POST /scan then open the Artifacts view.
   */
  async function on_run() {
    set_busy(true);
    set_error(null);
    set_status("Scanning…");
    try {
      const result = await run_scan(object_name, use_fixtures);
      const summary =
        `${result.rule_count} rules, ${result.field_count} fields` +
        (result.error_count ? `, ${result.error_count} errors` : "");
      set_status(`Done — ${summary}. Opening artifacts…`);
      // Carry the summary across so the Artifacts view can confirm what just ran,
      // rather than flashing a message the user never gets to read.
      router.push(`/artifacts?scanned=${encodeURIComponent(summary)}`);
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Scan failed");
      set_status(null);
    } finally {
      set_busy(false);
    }
  }

  return (
    <section>
      <div className="row" style={{ marginBottom: "1rem" }}>
        <label className="field">
          Object
          <select
            value={object_name}
            onChange={(e) => set_object_name(e.target.value)}
            disabled={busy}
          >
            <option value="Opportunity">Opportunity</option>
          </select>
        </label>
        <label className="field" style={{ flexDirection: "row", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={use_fixtures}
            onChange={(e) => set_use_fixtures(e.target.checked)}
            disabled={busy}
          />
          Use fixtures (offline)
        </label>
        <button type="button" className="primary" disabled={busy} onClick={on_run}>
          {busy ? "Scanning…" : "Run Scan"}
        </button>
      </div>
      {status ? (
        <p className="status" role="status">
          {status}
        </p>
      ) : null}
      {error ? (
        <p className="status error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
