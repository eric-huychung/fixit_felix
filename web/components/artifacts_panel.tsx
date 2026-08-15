/**
 * Tabs for constraints / test cases / agent context / evals.
 */

"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { ChallengesView } from "@/components/challenges_view";
import { ConstraintsView } from "@/components/constraints_view";
import { CopyButton } from "@/components/copy_button";
import { EvalsView } from "@/components/evals_view";
import { NoActiveRulesNotice } from "@/components/no_active_rules";
import { SkeletonLines } from "@/components/loading";
import { objects_in_scan, parse_scan_result } from "@/lib/parse_artifacts";
import type { eval_report } from "@/lib/types";
import { useArtifact } from "@/lib/use_artifact";

const TABS = [
  { id: "constraints", label: "Constraints", artifact: "scan_result.json" },
  { id: "challenges", label: "Test cases", artifact: null },
  { id: "agent_context", label: "Agent context", artifact: "agent_context.md" },
  { id: "evals", label: "Evals", artifact: "evals.jsonl" },
] as const;

type tab_id = (typeof TABS)[number]["id"];

/**
 * Loads artifacts from output/ and shows them in a tabbed panel.
 */
export function ArtifactsPanel() {
  const params = useSearchParams();
  const scanned = params.get("scanned");
  const object_from_query = params.get("object");
  const [active, set_active] = useState<tab_id>("constraints");
  const [live_report, set_live_report] = useState<eval_report | null>(null);
  const tab = TABS.find((item) => item.id === active) ?? TABS[0];
  const loaded = useArtifact(tab.artifact ?? "scan_result.json");
  const scan_meta = useArtifact("scan_result.json");
  const legacy_evals = useArtifact("evals.jsonl");

  const scan = (() => {
    if (!scan_meta.content) return null;
    const parsed = read_parsed(scan_meta.content, parse_scan_result);
    if (!parsed.ok) return null;
    return parsed.value;
  })();

  const objects_from_file = scan ? objects_in_scan(scan) : null;
  const active_rules = scan ? scan.rules.filter((rule) => rule.active).length : null;

  const object_label =
    object_from_query ||
    (objects_from_file?.length === 1 ? objects_from_file[0] : null) ||
    (objects_from_file && objects_from_file.length > 1 ? objects_from_file.join(", ") : null);

  const skip_artifact_error = tab.id === "challenges" || tab.id === "evals";

  return (
    <section>
      {object_label ? (
        <p className="status" role="status">
          Last scan: <strong>{object_label}</strong>
          {scanned ? ` — ${scanned}` : null}
        </p>
      ) : scanned ? (
        <p className="status" role="status">
          Scan complete — {scanned}
        </p>
      ) : null}
      <div className="tabs" role="tablist" aria-label="Scan artifacts">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-controls={`panel-${item.id}`}
            className={active === item.id ? "active" : undefined}
            aria-selected={active === item.id}
            onClick={() => set_active(item.id)}
          >
            {item.label}
          </button>
        ))}
        {tab.id === "agent_context" && loaded.content && active_rules !== 0 ? (
          <CopyButton text={loaded.content} />
        ) : null}
      </div>
      {loaded.error && !skip_artifact_error ? (
        <p className="status error" role="alert">
          {loaded.error}
        </p>
      ) : null}
      <div
        className="panel"
        role="tabpanel"
        id={`panel-${tab.id}`}
        aria-labelledby={`tab-${tab.id}`}
      >
        <TabBody
          tab={tab.id}
          content={loaded.content}
          loading={tab.id === "challenges" || tab.id === "evals" ? false : loaded.loading}
          active_rules={active_rules}
          object_name={object_label}
          legacy_evals={legacy_evals.content}
          live_report={live_report}
          on_eval_complete={(report) => {
            set_live_report(report);
            set_active("evals");
          }}
        />
      </div>
    </section>
  );
}

function TabBody({
  tab,
  content,
  loading,
  active_rules,
  object_name,
  legacy_evals,
  live_report,
  on_eval_complete,
}: {
  tab: tab_id;
  content: string | null;
  loading: boolean;
  active_rules: number | null;
  object_name: string | null;
  legacy_evals: string | null;
  live_report: eval_report | null;
  on_eval_complete: (report: eval_report) => void;
}) {
  if (tab === "challenges") {
    return (
      <ChallengesView
        active_rules={active_rules}
        object_name={object_name}
        on_eval_complete={on_eval_complete}
      />
    );
  }

  if (tab === "evals") {
    return (
      <EvalsView
        active_rules={active_rules}
        object_name={object_name}
        legacy_content={legacy_evals}
        live_report={live_report}
      />
    );
  }

  if (loading) return <SkeletonLines rows={6} />;
  if (content === null) return null;

  if (tab === "agent_context") {
    if (active_rules === 0) {
      return <NoActiveRulesNotice object_name={object_name} />;
    }
    return <pre>{content}</pre>;
  }

  if (tab === "constraints") {
    const parsed = read_parsed(content, parse_scan_result);
    if (!parsed.ok) {
      return (
        <p className="status error" role="alert">
          {parsed.error}
        </p>
      );
    }
    return <ConstraintsView result={parsed.value} />;
  }

  return null;
}

/**
 * Run a parser and turn thrown errors into a display string.
 */
function read_parsed<T>(
  text: string,
  parse: (text: string) => T,
): { ok: true; value: T } | { ok: false; error: string } {
  try {
    return { ok: true, value: parse(text) };
  } catch (err: unknown) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Could not parse artifact",
    };
  }
}
