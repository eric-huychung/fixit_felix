/**
 * Typed shapes returned by the loopback Felix API.
 */

export type headline = {
  baseline_pass_rate: string | null;
  treatment_pass_rate: string | null;
  delta: string | null;
  summary: string | null;
  source?: "live" | "published" | null;
  object_name?: string | null;
  ran_at?: string | null;
};

export type scan_response = {
  org_id: string;
  scanned_at: string;
  object_name: string;
  objects: string[];
  rule_count: number;
  field_count: number;
  apex_count: number;
  error_count: number;
  artifacts: string[];
};

/** Last scan metadata from GET /scan/current. */
export type scan_current = {
  org_id: string;
  scanned_at: string;
  objects: string[];
  object_name: string | null;
  rule_count: number;
  field_count: number;
  apex_count: number;
  error_count: number;
};

export type artifact_response = {
  name: string;
  content: string;
};

export type sobject_summary = {
  name: string;
  label: string;
  custom: boolean;
};

export type field_constraint = {
  object_name: string;
  api_name: string;
  label: string;
  soap_type: string;
  required: boolean;
  picklist_values: string[];
  max_length: number | null;
  reference_to: string[];
};

export type validation_rule_constraint = {
  id: string;
  object_name: string;
  name: string;
  active: boolean;
  namespace_prefix: string | null;
  error_message: string;
  error_display_field: string | null;
  formula: string;
  formula_hash: string;
  plain_english: string | null;
  fields_referenced: string[];
};

export type apex_constraint = {
  source_name: string;
  object_name: string | null;
  error_messages: string[];
  excerpt: string;
  confidence: "high" | "best_effort";
};

export type scan_error = {
  stage: string;
  target: string;
  message: string;
};

/** Shape of scan_result.json — the structured source behind the Constraints tab. */
export type scan_result = {
  org_id: string;
  scanned_at: string;
  fields: field_constraint[];
  rules: validation_rule_constraint[];
  apex: apex_constraint[];
  errors: scan_error[];
};

/** One line of evals.jsonl. */
export type eval_case = {
  id: string;
  object_name: string;
  intent: string;
  seed_payload: Record<string, unknown>;
  target_rule_id: string;
  expected_error_fragment: string;
  seed_provenance: "org_pack" | "derived";
};

export type diagnosis_response = {
  kind: "rule" | "guess" | "escalation";
  instruction: string;
  rule_id: string | null;
  rule_name: string | null;
  field: string | null;
  is_guess: boolean;
  escalation?: {
    why: string;
    human_action: string;
  };
};

export type challenge_status = "proposed" | "approved" | "rejected";

export type challenge_case = {
  id: string;
  object_name: string;
  rule_id: string;
  rule_name: string;
  intent: string;
  payload: Record<string, unknown>;
  expected_error_fragment: string;
  status: challenge_status;
};

export type challenge_propose_source = "llm" | "deterministic";

export type challenge_list_response = {
  count: number;
  approved_count: number;
  cases: challenge_case[];
  /** Present on propose responses: how drafts were produced. */
  source?: challenge_propose_source;
};

export type eval_arm_metrics = {
  arm: string;
  cases: number;
  passes: number;
  pass_rate: number;
  pass_rate_label: string;
  api_calls: number;
  attempts_per_success: number | null;
};

export type eval_case_result = {
  case_id: string;
  arm: string;
  passed: boolean;
  api_calls: number;
  created_id: string | null;
  attempts: Array<{
    success: boolean;
    payload: Record<string, unknown>;
    error_body: unknown;
  }>;
};

export type eval_report = {
  baseline: eval_arm_metrics;
  treatment: eval_arm_metrics;
  delta: number;
  delta_label: string;
  seed_provenance: Record<string, number>;
  results: eval_case_result[];
};
