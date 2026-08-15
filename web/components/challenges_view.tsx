/**
 * Test cases: propose drafts, approve / reject, then run eval.
 */

"use client";

import { useEffect, useState } from "react";
import { CheckIcon } from "@/components/icons";
import { SkeletonLines, Spinner } from "@/components/loading";
import { NoActiveRulesNotice } from "@/components/no_active_rules";
import {
  approve_all_challenge_cases,
  fetch_challenge_cases,
  patch_challenge_case,
  propose_challenge_cases,
  run_eval,
} from "@/lib/api_client";
import type { challenge_case, challenge_status, eval_report } from "@/lib/types";

type loaded = {
  cases: challenge_case[];
  approved_count: number;
  source?: "llm" | "deterministic";
};

type props = {
  active_rules: number | null;
  object_name?: string | null;
  on_eval_complete?: (report: eval_report) => void;
};

/**
 * Review test cases and run eval on the approved set.
 */
export function ChallengesView({ active_rules, object_name, on_eval_complete }: props) {
  const [loaded, set_loaded] = useState<loaded | null>(null);
  const [missing, set_missing] = useState(false);
  const [error, set_error] = useState<string | null>(null);
  const [busy, set_busy] = useState(false);
  const [eval_busy, set_eval_busy] = useState(false);
  const [tick, set_tick] = useState(0);

  useEffect(() => {
    let current = true;
    fetch_challenge_cases()
      .then((listing) => {
        if (!current) return;
        set_loaded({ cases: listing.cases, approved_count: listing.approved_count });
        set_missing(false);
        set_error(null);
      })
      .catch((err: unknown) => {
        if (!current) return;
        set_loaded(null);
        set_missing(true);
        set_error(err instanceof Error ? err.message : "Failed to load test cases");
      });
    return () => {
      current = false;
    };
  }, [tick]);

  async function on_propose() {
    set_busy(true);
    set_error(null);
    try {
      const listing = await propose_challenge_cases();
      set_loaded({
        cases: listing.cases,
        approved_count: listing.approved_count ?? 0,
        source: listing.source,
      });
      set_missing(false);
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Propose failed");
    } finally {
      set_busy(false);
    }
  }

  async function on_status(case_id: string, status: challenge_status) {
    set_busy(true);
    set_error(null);
    try {
      await patch_challenge_case(case_id, { status });
      set_tick((value) => value + 1);
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Update failed");
    } finally {
      set_busy(false);
    }
  }

  async function on_approve_all() {
    set_busy(true);
    set_error(null);
    try {
      const listing = await approve_all_challenge_cases();
      set_loaded({
        cases: listing.cases,
        approved_count: listing.approved_count,
        source: loaded?.source,
      });
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Approve all failed");
    } finally {
      set_busy(false);
    }
  }

  async function on_run_eval() {
    set_eval_busy(true);
    set_error(null);
    try {
      const report = await run_eval();
      on_eval_complete?.(report);
    } catch (err: unknown) {
      set_error(err instanceof Error ? err.message : "Eval failed");
    } finally {
      set_eval_busy(false);
    }
  }

  if (active_rules === 0) {
    return <NoActiveRulesNotice object_name={object_name} />;
  }

  if (loaded === null && !missing) {
    return <SkeletonLines rows={5} />;
  }

  if (missing && loaded === null) {
    return (
      <div className="artifact_view">
        <p className="section_note">Propose failing creates, then approve ones to measure.</p>
        <p className="status">{error}</p>
        <button type="button" className="primary" disabled={busy} onClick={on_propose}>
          {busy ? <Spinner label="Proposing…" /> : "Propose test cases"}
        </button>
      </div>
    );
  }

  const cases = loaded?.cases ?? [];
  const approved_count = loaded?.approved_count ?? 0;
  const blocked = busy || eval_busy;

  return (
    <div className="artifact_view">
      <div className="summary_row">
        <span className="chip">{cases.length} total</span>
        <span className="chip">{approved_count} approved</span>
      </div>
      <p className="section_note">
        Only <strong>approved</strong> cases are measured.
        {loaded?.source === "llm"
          ? " LLM drafts — verify before approving."
          : loaded?.source === "deterministic"
            ? " Offline drafts (no LLM key) — verify before approving."
            : null}
      </p>
      <div className="control_row" style={{ marginBottom: "0.75rem" }}>
        <button type="button" className="ghost" disabled={blocked} onClick={on_propose}>
          {busy ? <Spinner label="Proposing…" /> : "Re-propose"}
        </button>
        <button
          type="button"
          className="primary"
          disabled={blocked || approved_count === 0}
          onClick={on_run_eval}
        >
          {eval_busy ? <Spinner label="Running…" /> : "Run eval"}
        </button>
        <button
          type="button"
          className="icon_button control_row_end"
          disabled={blocked || cases.length === 0 || approved_count === cases.length}
          onClick={on_approve_all}
          aria-label="Approve all"
          title={
            approved_count === cases.length && cases.length > 0
              ? "All already approved"
              : "Approve all"
          }
        >
          <CheckIcon />
        </button>
      </div>
      <p className="section_note">Eval creates/deletes Opportunities in your org.</p>
      {error ? (
        <p className="status error" role="alert">
          {error}
        </p>
      ) : null}
      {cases.map((item) => (
        <article className="card" key={item.id}>
          <header className="card_head">
            <h3>{item.rule_name}</h3>
            <span className={`badge ${item.status === "approved" ? "ok" : "muted"}`}>
              {item.status}
            </span>
          </header>
          <p className="meaning">{item.intent}</p>
          <dl className="meta">
            <div>
              <dt>Expect</dt>
              <dd>{item.expected_error_fragment}</dd>
            </div>
          </dl>
          <p className="payload_label">Payload</p>
          <dl className="payload">
            {Object.entries(item.payload).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>
                  <code>{format_value(value)}</code>
                </dd>
              </div>
            ))}
          </dl>
          <div className="control_row">
            <button
              type="button"
              className="primary"
              disabled={blocked || item.status === "approved"}
              onClick={() => on_status(item.id, "approved")}
            >
              Approve
            </button>
            <button
              type="button"
              className="ghost"
              disabled={blocked || item.status === "rejected"}
              onClick={() => on_status(item.id, "rejected")}
            >
              Reject
            </button>
            {item.status !== "proposed" ? (
              <button
                type="button"
                className="ghost"
                disabled={blocked}
                onClick={() => on_status(item.id, "proposed")}
              >
                Reset
              </button>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function format_value(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
