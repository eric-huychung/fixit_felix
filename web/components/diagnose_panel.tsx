/**
 * Paste Salesforce error JSON and show rule match / guess / escalation.
 */

"use client";

import { useEffect, useState } from "react";
import { ObjectPicker } from "@/components/object_picker";
import { SkeletonLines, Spinner } from "@/components/loading";
import { fetch_scan_current, run_diagnose } from "@/lib/api_client";
import type { diagnosis_response } from "@/lib/types";

const SAMPLE_ERROR = `[
  {
    "message": "Please contact your administrator.",
    "errorCode": "FIELD_CUSTOM_VALIDATION_EXCEPTION",
    "fields": ["Amount"]
  }
]`;

/**
 * Diagnose form: error JSON in, grounded instruction out.
 *
 * Defaults the object picker to the last scan when that scan covered one object.
 */
export function DiagnosePanel() {
  const [error_text, set_error_text] = useState(SAMPLE_ERROR);
  const [payload_text, set_payload_text] = useState("");
  const [object_name, set_object_name] = useState("Opportunity");
  const [scanned_objects, set_scanned_objects] = useState<string[] | null>(null);
  const [scan_error, set_scan_error] = useState<string | null>(null);
  const [busy, set_busy] = useState(false);
  const [result, set_result] = useState<diagnosis_response | null>(null);
  const [error, set_error] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    fetch_scan_current()
      .then((scan) => {
        if (!current) return;
        set_scanned_objects(scan.objects);
        set_scan_error(null);
        if (scan.object_name) set_object_name(scan.object_name);
      })
      .catch((err: unknown) => {
        if (!current) return;
        set_scanned_objects(null);
        set_scan_error(err instanceof Error ? err.message : "No scan result yet");
      });
    return () => {
      current = false;
    };
  }, []);

  const mismatch =
    scanned_objects !== null &&
    scanned_objects.length > 0 &&
    !scanned_objects.includes(object_name);

  /**
   * Parse inputs and POST /diagnose.
   */
  async function on_run() {
    set_busy(true);
    set_error(null);
    set_result(null);
    try {
      const parsed_error = JSON.parse(error_text) as unknown;
      let payload: Record<string, unknown> | undefined;
      if (payload_text.trim()) {
        payload = JSON.parse(payload_text) as Record<string, unknown>;
      }
      const diagnosis = await run_diagnose(parsed_error, object_name, payload);
      set_result(diagnosis);
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Diagnose failed");
    } finally {
      set_busy(false);
    }
  }

  return (
    <section>
      {scanned_objects && scanned_objects.length > 0 ? (
        <p className="status" role="status">
          Last scan covered: <strong>{scanned_objects.join(", ")}</strong>
        </p>
      ) : null}
      {scan_error ? (
        <p className="status" role="status">
          {scan_error.includes("404") || scan_error.toLowerCase().includes("no scan")
            ? "No scan result yet — run a scan before diagnosing."
            : scan_error}
        </p>
      ) : null}
      <ObjectPicker
        value={object_name}
        on_change={set_object_name}
        disabled={busy}
        actions={
          <button type="button" className="primary" disabled={busy} onClick={on_run}>
            {busy ? <Spinner label="Diagnosing…" /> : "Diagnose"}
          </button>
        }
      />
      {mismatch ? (
        <p className="status error" role="alert">
          {object_name} is not in the last scan ({scanned_objects?.join(", ")}). Scan{" "}
          {object_name} first, or pick a scanned object.
        </p>
      ) : null}
      <label className="field" style={{ marginBottom: "1rem" }}>
        Error JSON
        <textarea
          value={error_text}
          onChange={(e) => set_error_text(e.target.value)}
          spellCheck={false}
          disabled={busy}
        />
      </label>
      <label className="field" style={{ marginBottom: "1rem" }}>
        Attempted payload (optional)
        <textarea
          value={payload_text}
          onChange={(e) => set_payload_text(e.target.value)}
          spellCheck={false}
          disabled={busy}
          placeholder='{"Amount": 150000}'
        />
      </label>
      {error ? <p className="status error">{error}</p> : null}
      {busy ? (
        <div className="loading_block">
          <Spinner label="Matching the error to a scanned rule…" />
          <SkeletonLines rows={4} />
        </div>
      ) : null}
      {result ? (
        <div className="diagnosis">
          <div className={`kind ${result.kind}`}>{result.kind}</div>
          {result.rule_name ? (
            <div>
              <strong>Rule</strong> {result.rule_name}
              {result.rule_id ? ` (${result.rule_id})` : ""}
            </div>
          ) : null}
          {result.field ? (
            <div>
              <strong>Field</strong> {result.field}
            </div>
          ) : null}
          <div>
            <strong>Instruction</strong> {result.instruction}
          </div>
          {result.escalation ? (
            <>
              <div>
                <strong>Why</strong> {result.escalation.why}
              </div>
              <div>
                <strong>Human</strong> {result.escalation.human_action}
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
