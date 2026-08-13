/**
 * Paste Salesforce error JSON and show rule match / guess / escalation.
 */

"use client";

import { useState } from "react";
import { run_diagnose } from "@/lib/api_client";
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
 */
export function DiagnosePanel() {
  const [error_text, set_error_text] = useState(SAMPLE_ERROR);
  const [payload_text, set_payload_text] = useState("");
  const [object_name, set_object_name] = useState("Opportunity");
  const [busy, set_busy] = useState(false);
  const [result, set_result] = useState<diagnosis_response | null>(null);
  const [error, set_error] = useState<string | null>(null);

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
        <button type="button" className="primary" disabled={busy} onClick={on_run}>
          {busy ? "Diagnosing…" : "Diagnose"}
        </button>
      </div>
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
