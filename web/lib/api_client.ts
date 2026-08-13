/**
 * Browser client for the loopback Felix API (scan / diagnose / artifacts).
 */

import type {
  artifact_response,
  diagnosis_response,
  headline,
  scan_response,
} from "@/lib/types";

const DEFAULT_API = "http://127.0.0.1:8787";

/**
 * Resolves the loopback API base URL from env or the default port.
 *
 * @returns Absolute origin for API calls
 */
export function api_base(): string {
  return process.env.NEXT_PUBLIC_FELIX_API_URL ?? DEFAULT_API;
}

/**
 * Fetches the eval headline strip from RESULTS.md via the API.
 *
 * @returns Parsed baseline / treatment / delta
 */
export async function fetch_headline(): Promise<headline> {
  const res = await fetch(`${api_base()}/headline`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`headline failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Runs a scan against the org (or fixtures) and writes output artifacts.
 *
 * @param object_name - Salesforce sObject API name
 * @param use_fixtures - When true, use recorded fixtures (offline demo)
 * @returns Scan summary counts
 */
export async function run_scan(
  object_name: string,
  use_fixtures: boolean,
): Promise<scan_response> {
  const res = await fetch(`${api_base()}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_name, use_fixtures }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `scan failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Loads one artifact from the output directory.
 *
 * @param name - Artifact basename (e.g. agent_context.md)
 * @returns Artifact name + text content
 */
export async function fetch_artifact(name: string): Promise<artifact_response> {
  const res = await fetch(`${api_base()}/artifacts/${encodeURIComponent(name)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`artifact ${name} failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Diagnoses a Salesforce write error using the last scan result.
 *
 * @param error - Parsed Salesforce error JSON (array or object)
 * @param object_name - sObject API name
 * @param payload - Optional attempted payload (display only)
 * @returns Matched rule, guess, or escalation
 */
export async function run_diagnose(
  error: unknown,
  object_name: string,
  payload?: Record<string, unknown>,
): Promise<diagnosis_response> {
  const res = await fetch(`${api_base()}/diagnose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ error, object_name, payload }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `diagnose failed: ${res.status}`);
  }
  return res.json();
}
