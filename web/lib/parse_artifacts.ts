/**
 * Parse scan artifacts into the shapes the artifact views render.
 */

import type { eval_case, scan_result } from "@/lib/types";

/**
 * Parse scan_result.json. Throws if the file is not a scan result.
 *
 * @param text - Artifact body
 * @returns Structured scan result
 */
export function parse_scan_result(text: string): scan_result {
  const parsed: unknown = JSON.parse(text);
  if (
    !is_record(parsed) ||
    !Array.isArray(parsed.fields) ||
    !Array.isArray(parsed.rules) ||
    !Array.isArray(parsed.apex) ||
    !Array.isArray(parsed.errors)
  ) {
    throw new Error("scan_result.json is not a scan result.");
  }
  return parsed as scan_result;
}

/**
 * Parse evals.jsonl into one case per line. Throws on the first bad line.
 *
 * @param text - Artifact body
 * @returns Eval cases in file order
 */
export function parse_eval_cases(text: string): eval_case[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const parsed: unknown = JSON.parse(line);
      if (!is_record(parsed) || typeof parsed.intent !== "string") {
        throw new Error(`evals.jsonl line ${index + 1} is not an eval case.`);
      }
      return parsed as eval_case;
    });
}

/**
 * Strip SOAP prefixes so field types read as `string` rather than `xsd:string`.
 *
 * @param soap_type - Salesforce soapType from describe
 * @returns Short type label
 */
export function short_soap_type(soap_type: string): string {
  return soap_type.replace(/^xsd:/, "").replace(/^tns:/, "");
}

function is_record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Object API names present in a scan result.
 *
 * @param result - Parsed scan_result.json
 * @returns Sorted unique object names
 */
export function objects_in_scan(result: scan_result): string[] {
  const names = new Set<string>();
  for (const field of result.fields) names.add(field.object_name);
  for (const rule of result.rules) names.add(rule.object_name);
  for (const item of result.apex) {
    if (item.object_name) names.add(item.object_name);
  }
  return [...names].sort();
}
