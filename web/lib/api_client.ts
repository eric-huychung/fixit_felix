/**
 * Browser client for the loopback Felix API (scan / diagnose / artifacts).
 */

import type {
  artifact_response,
  diagnosis_response,
  headline,
  scan_response,
  challenge_case,
  challenge_list_response,
  challenge_status,
  eval_report,
  scan_current,
  sobject_summary,
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
 * Lists the sObjects in the org that are worth scanning.
 *
 * @returns Objects sorted standard-first, then by label
 */
export async function fetch_objects(): Promise<sobject_summary[]> {
  const res = await fetch(`${api_base()}/objects`, { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `objects failed: ${res.status}`);
  }
  const body = (await res.json()) as { objects: sobject_summary[] };
  return body.objects;
}

/**
 * Runs a scan against the org and writes output artifacts.
 *
 * @param object_name - Salesforce sObject API name
 * @returns Scan summary counts
 */
export async function run_scan(object_name: string): Promise<scan_response> {
  const res = await fetch(`${api_base()}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ object_name }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `scan failed: ${res.status}`);
  }
  return res.json();
}

/**
 * Loads metadata for the last scan written to output/.
 *
 * @returns Scanned object names and counts
 */
export async function fetch_scan_current(): Promise<scan_current> {
  const res = await fetch(`${api_base()}/scan/current`, { cache: "no-store" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `scan/current failed: ${res.status}`);
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
    throw new Error(await read_error(res, `diagnose failed: ${res.status}`));
  }
  return res.json();
}

/** Prefer FastAPI JSON `detail` when present. */
async function read_error(res: Response, fallback: string): Promise<string> {
  const text = await res.text();
  try {
    const body = JSON.parse(text) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // not JSON
  }
  return text || fallback;
}

/**
 * List challenge cases from output/challenge_cases.json.
 */
export async function fetch_challenge_cases(): Promise<challenge_list_response> {
  const res = await fetch(`${api_base()}/challenge-cases`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(await read_error(res, `challenge-cases failed: ${res.status}`));
  }
  return res.json();
}

/**
 * Draft challenge cases from the last scan (status=proposed).
 */
export async function propose_challenge_cases(): Promise<challenge_list_response> {
  const res = await fetch(`${api_base()}/challenge-cases/propose`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await read_error(res, `propose failed: ${res.status}`));
  }
  return res.json();
}

/**
 * Approve, reject, or edit one challenge case.
 */
export async function patch_challenge_case(
  case_id: string,
  body: { status?: challenge_status; payload?: Record<string, unknown> },
): Promise<challenge_case> {
  const res = await fetch(`${api_base()}/challenge-cases/${encodeURIComponent(case_id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await read_error(res, `patch challenge failed: ${res.status}`));
  }
  return res.json();
}

/**
 * Approve every test case.
 */
export async function approve_all_challenge_cases(): Promise<challenge_list_response> {
  const res = await fetch(`${api_base()}/challenge-cases/batch/approve`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await read_error(res, `approve-all failed: ${res.status}`));
  }
  return res.json();
}

/**
 * Run baseline vs treatment on approved test cases (writes Opportunities).
 */
export async function run_eval(): Promise<eval_report> {
  const res = await fetch(`${api_base()}/eval`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await read_error(res, `eval failed: ${res.status}`));
  }
  return res.json();
}

/**
 * Load the last persisted eval report, if any.
 */
export async function fetch_latest_eval(): Promise<eval_report | null> {
  const res = await fetch(`${api_base()}/eval/latest`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(await read_error(res, `eval/latest failed: ${res.status}`));
  }
  return res.json();
}
