export type ReviewStatus = "proposed" | "confirmed" | "rejected" | "uncertain";

export interface Guardrail {
  rule: string;
  severity: "info" | "warn" | "block" | string;
  confirmed_by_expert?: boolean;
  rule_id?: string;
}

export interface Evidence {
  event_ids?: string[];
  transcript_segment_ids?: string[];
  transcript_excerpts?: { id: string; speaker: string; text: string }[];
  frame_id?: string | null;
}

export interface WorkflowStep {
  id: string;
  timestamp_ms: number;
  action: string;
  context?: Record<string, unknown>;
  decision?: string | null;
  reason?: string | null;
  guardrails?: Guardrail[];
  evidence?: Evidence;
  confidence?: number | null;
  review_status?: ReviewStatus | string;
}

export interface WorkMap {
  id: string;
  title: string;
  status: string;
  steps: WorkflowStep[];
}
