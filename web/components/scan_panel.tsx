/**
 * Object picker + Run Scan primary action for the home view.
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ObjectPicker } from "@/components/object_picker";
import { Spinner } from "@/components/loading";
import { propose_challenge_cases, run_scan } from "@/lib/api_client";

/**
 * Triggers a Felix scan via the local API and navigates to Artifacts on success.
 */
export function ScanPanel() {
  const router = useRouter();
  const [object_name, set_object_name] = useState("Opportunity");
  const [busy, set_busy] = useState(false);
  const [status, set_status] = useState<string | null>(null);
  const [error, set_error] = useState<string | null>(null);

  /**
   * POST /scan then open the Artifacts view.
   */
  async function on_run() {
    set_busy(true);
    set_error(null);
    set_status(`Scanning ${object_name}…`);
    try {
      const result = await run_scan(object_name);
      const summary =
        `${result.rule_count} rules, ${result.field_count} fields` +
        (result.error_count ? `, ${result.error_count} errors` : "");
      set_status(`Done — ${summary}. Proposing test cases…`);
      try {
        await propose_challenge_cases();
      } catch {
        // Propose is best-effort after scan; Artifacts can retry.
      }
      set_status(`Done — ${summary}. Opening artifacts…`);
      const params = new URLSearchParams({
        scanned: summary,
        object: result.object_name,
      });
      router.push(`/artifacts?${params.toString()}`);
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Scan failed");
      set_status(null);
    } finally {
      set_busy(false);
    }
  }

  return (
    <section>
      <ObjectPicker
        value={object_name}
        on_change={set_object_name}
        disabled={busy}
        actions={
          <button type="button" className="primary" disabled={busy} onClick={on_run}>
            {busy ? <Spinner label="Scanning…" /> : "Run Scan"}
          </button>
        }
      />
      {status && !busy ? (
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
