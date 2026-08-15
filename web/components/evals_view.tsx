/**
 * Evals: last full report (baseline / treatment / cases), plus approved input set.
 */

"use client";

import { useEffect, useState } from "react";
import { NoActiveRulesNotice } from "@/components/no_active_rules";
import { SkeletonLines } from "@/components/loading";
import { fetch_challenge_cases, fetch_latest_eval } from "@/lib/api_client";
import { parse_eval_cases } from "@/lib/parse_artifacts";
import type { challenge_case, eval_case, eval_case_result, eval_report } from "@/lib/types";

type props = {
  active_rules: number | null;
  object_name?: string | null;
  legacy_content: string | null;
  /** Fresh report from a Run eval click (takes precedence until reload). */
  live_report?: eval_report | null;
};

type loaded_cases = {
  cases: challenge_case[];
  approved_count: number;
};

/**
 * Shows the latest eval report when present; otherwise the approved input set.
 */
export function EvalsView({
  active_rules,
  object_name,
  legacy_content,
  live_report = null,
}: props) {
  const [report, set_report] = useState<eval_report | null>(live_report);
  const [loaded, set_loaded] = useState<loaded_cases | null>(null);
  const [missing, set_missing] = useState(false);
  const [error, set_error] = useState<string | null>(null);
  const [loading, set_loading] = useState(true);

  useEffect(() => {
    if (live_report) set_report(live_report);
  }, [live_report]);

  useEffect(() => {
    let current = true;
    set_loading(true);
    Promise.all([
      fetch_latest_eval().catch(() => null),
      fetch_challenge_cases()
        .then((listing) => ({ ok: true as const, listing }))
        .catch((err: unknown) => ({
          ok: false as const,
          error: err instanceof Error ? err.message : "Failed to load test cases",
        })),
    ]).then(([latest, challenges]) => {
      if (!current) return;
      if (!live_report && latest) set_report(latest);
      if (challenges.ok) {
        set_loaded({
          cases: challenges.listing.cases,
          approved_count: challenges.listing.approved_count,
        });
        set_missing(false);
        set_error(null);
      } else {
        set_loaded(null);
        set_missing(true);
        set_error(challenges.error);
      }
      set_loading(false);
    });
    return () => {
      current = false;
    };
  }, [live_report]);

  if (active_rules === 0) {
    return <NoActiveRulesNotice object_name={object_name} />;
  }

  if (loading && !report) {
    return <SkeletonLines rows={5} />;
  }

  if (report) {
    return <EvalReportView report={report} />;
  }

  if (missing) {
    return <LegacyEvalsFallback content={legacy_content} load_error={error} />;
  }

  const cases = loaded?.cases ?? [];
  const approved = cases.filter((item) => item.status === "approved");
  const proposed = cases.filter((item) => item.status === "proposed").length;
  const rejected = cases.filter((item) => item.status === "rejected").length;

  return (
    <div className="artifact_view">
      <div className="summary_row">
        <span className="chip">{approved.length} approved</span>
        <span className="chip">{proposed} proposed</span>
        {rejected ? <span className="chip">{rejected} rejected</span> : null}
      </div>
      <p className="section_note">
        No eval run yet. Approve cases on Test cases, then click Run eval.
      </p>
      {approved.length === 0 ? (
        <p className="status error" role="alert">
          Nothing approved yet.
        </p>
      ) : (
        approved.map((item) => <ApprovedCard key={item.id} item={item} />)
      )}
    </div>
  );
}

function EvalReportView({ report }: { report: eval_report }) {
  const by_case = group_results(report.results);

  return (
    <div className="artifact_view">
      <div className="summary_row">
        <span className="chip">Baseline {report.baseline.pass_rate_label}</span>
        <span className="chip">Treatment {report.treatment.pass_rate_label}</span>
        <span className="chip">Delta {report.delta_label}</span>
      </div>
      <p className="section_note">
        Full eval: {report.baseline.passes}/{report.baseline.cases} baseline ·{" "}
        {report.treatment.passes}/{report.treatment.cases} treatment ·{" "}
        {report.baseline.api_calls + report.treatment.api_calls} API calls
      </p>
      {by_case.map(([case_id, arms]) => (
        <article className="card" key={case_id}>
          <header className="card_head">
            <h3>{case_id}</h3>
          </header>
          <dl className="meta">
            {arms.map((arm) => (
              <div key={arm.arm}>
                <dt>{arm.arm}</dt>
                <dd>
                  <span className={`badge ${arm.passed ? "ok" : "muted"}`}>
                    {arm.passed ? "pass" : "fail"}
                  </span>{" "}
                  · {arm.attempts.length} attempt{arm.attempts.length === 1 ? "" : "s"} ·{" "}
                  {arm.api_calls} API
                </dd>
              </div>
            ))}
          </dl>
        </article>
      ))}
    </div>
  );
}

function group_results(results: eval_case_result[]): Array<[string, eval_case_result[]]> {
  const map = new Map<string, eval_case_result[]>();
  for (const item of results) {
    const list = map.get(item.case_id) ?? [];
    list.push(item);
    map.set(item.case_id, list);
  }
  return [...map.entries()];
}

function ApprovedCard({ item }: { item: challenge_case }) {
  return (
    <article className="card">
      <header className="card_head">
        <h3>{item.rule_name}</h3>
        <span className="badge ok">approved</span>
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
    </article>
  );
}

function LegacyEvalsFallback({
  content,
  load_error,
}: {
  content: string | null;
  load_error: string | null;
}) {
  let cases: eval_case[] = [];
  let parse_error: string | null = null;
  if (content) {
    try {
      cases = parse_eval_cases(content);
    } catch (err: unknown) {
      parse_error = err instanceof Error ? err.message : "Could not parse evals.jsonl";
    }
  }

  return (
    <div className="artifact_view">
      <p className="status error" role="alert">
        No test cases yet. Propose and approve them first.
      </p>
      {load_error ? <p className="section_note">{load_error}</p> : null}
      {parse_error ? (
        <p className="status error" role="alert">
          {parse_error}
        </p>
      ) : null}
      {cases.length === 0 ? (
        <p className="status">No legacy evals either.</p>
      ) : (
        <>
          <p className="section_note">Legacy scan seeds ({cases.length}) — ignored once test cases exist.</p>
          {cases.map((item) => (
            <article className="card" key={item.id}>
              <header className="card_head">
                <h3>{rule_name(item)}</h3>
                <span className={`badge ${item.seed_provenance === "org_pack" ? "ok" : "muted"}`}>
                  {item.seed_provenance === "org_pack" ? "fitted" : "inferred"}
                </span>
              </header>
              <p className="meaning">{item.intent}</p>
            </article>
          ))}
        </>
      )}
    </div>
  );
}

function rule_name(item: eval_case): string {
  const match = item.intent.match(/'([^']+)'/);
  return match?.[1] ?? item.id;
}

function format_value(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
