export interface WorkflowStep {
  id: string;
  timestamp: number;
  action: string;
  decision?: string | null;
  reason?: string | null;
  guardrails: string[];
}

export interface WorkMap {
  id: string;
  title: string;
  steps: WorkflowStep[];
}
