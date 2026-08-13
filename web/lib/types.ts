/**
 * Typed shapes returned by the loopback Felix API.
 */

export type headline = {
  baseline_pass_rate: string | null;
  treatment_pass_rate: string | null;
  delta: string | null;
  summary: string | null;
};

export type scan_response = {
  org_id: string;
  scanned_at: string;
  rule_count: number;
  field_count: number;
  apex_count: number;
  error_count: number;
  artifacts: string[];
};

export type artifact_response = {
  name: string;
  content: string;
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
