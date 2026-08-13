/**
 * Tabs for constraints.md / agent_context.md / evals.jsonl with copy on context.
 */

"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetch_artifact } from "@/lib/api_client";

const TABS = [
  { id: "constraints.md", label: "Constraints" },
  { id: "agent_context.md", label: "Agent context" },
  { id: "evals.jsonl", label: "Evals" },
] as const;

type tab_id = (typeof TABS)[number]["id"];

/** The artifact a completed request produced, tagged with the tab it belongs to. */
type loaded_artifact = {
  name: tab_id;
  content: string | null;
  error: string | null;
};

/**
 * Loads artifacts from output/ and shows them in a tabbed panel.
 */
export function ArtifactsPanel() {
  const scanned = useSearchParams().get("scanned");
  const [active, set_active] = useState<tab_id>("constraints.md");
  const [loaded, set_loaded] = useState<loaded_artifact | null>(null);
  const [copy_error, set_copy_error] = useState<string | null>(null);
  const [copied_from, set_copied_from] = useState<tab_id | null>(null);

  useEffect(() => {
    // Tagging the result with the tab it was requested for means a slow response
    // can never overwrite the tab now on screen — it simply stops matching.
    let current = true;

    fetch_artifact(active)
      .then((artifact) => {
        if (current) set_loaded({ name: active, content: artifact.content, error: null });
      })
      .catch((err: unknown) => {
        if (!current) return;
        const message = err instanceof Error ? err.message : "Failed to load artifact";
        set_loaded({ name: active, content: null, error: message });
      });

    return () => {
      current = false;
    };
  }, [active]);

  // Anything loaded for a different tab is stale, so the panel shows nothing yet.
  const showing = loaded?.name === active ? loaded : null;
  const content = showing?.content ?? null;
  const error = showing?.error ?? copy_error;
  const copied = copied_from === active;

  /**
   * Copies agent context to the clipboard when that tab is active.
   *
   * Clipboard access rejects outside a secure context or when the user denies
   * permission, so failure is surfaced rather than swallowed.
   */
  async function on_copy() {
    if (content === null) return;
    try {
      await navigator.clipboard.writeText(content);
      set_copy_error(null);
      set_copied_from(active);
    } catch {
      set_copy_error("Could not copy — your browser blocked clipboard access.");
    }
  }

  return (
    <section>
      {scanned ? (
        <p className="status" role="status">
          Scan complete — {scanned}
        </p>
      ) : null}
      <div className="tabs" role="tablist" aria-label="Scan artifacts">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-controls={`panel-${tab.id}`}
            className={active === tab.id ? "active" : undefined}
            aria-selected={active === tab.id}
            onClick={() => set_active(tab.id)}
          >
            {tab.label}
          </button>
        ))}
        {active === "agent_context.md" && content ? (
          <button type="button" className="ghost" style={{ marginLeft: "auto" }} onClick={on_copy}>
            {copied ? "Copied" : "Copy"}
          </button>
        ) : null}
      </div>
      {error ? (
        <p className="status error" role="alert">
          {error}
        </p>
      ) : null}
      <div
        className="panel"
        role="tabpanel"
        id={`panel-${active}`}
        aria-labelledby={`tab-${active}`}
      >
        <pre>{content ?? (error ? "" : "Loading…")}</pre>
      </div>
    </section>
  );
}
