export interface Session {
  session_id: string;
  workflow_title: string;
  expert_name?: string;
  status: string;
}

export interface EventPayload {
  client_event_id: string;
  timestamp_ms: number;
  source: string;
  type: string;
  data: Record<string, unknown>;
  frame_id?: string;
}

export interface TranscriptPayload {
  segment_id: string;
  timestamp_ms: number;
  speaker: string;
  text: string;
  source: string;
}

export interface ApiResponse<T = unknown> {
  data?: T;
}
