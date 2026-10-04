"use client";

import { useState } from "react";
import { useCaptureState } from "@/hooks/useCaptureState";
import { addTranscript } from "@/services/api";

interface Line {
  speaker: string;
  text: string;
  timestamp_ms: number;
}

export default function AgentPanel() {
  const capture = useCaptureState();
  const [lines, setLines] = useState<Line[]>([]);
  const [text, setText] = useState("");

  const agentState =
    capture.status === "capturing"
      ? "Listening"
      : capture.status === "paused"
      ? "Paused"
      : capture.status === "off_record"
      ? "Off record"
      : capture.status === "finished"
      ? "Disconnected"
      : "Connecting";

  const send = async () => {
    if (!text.trim()) return;
    const line: Line = { speaker: "expert", text: text.trim(), timestamp_ms: Date.now() };
    setLines((l) => [...l, line]);
    setText("");
    if (capture.sessionId && capture.status === "capturing") {
      try {
        await addTranscript(capture.sessionId, {
          segment_id: crypto.randomUUID(),
          timestamp_ms: line.timestamp_ms,
          speaker: "expert",
          text: line.text,
          source: "prototype_transcript",
        });
      } catch {
        // ignore demo errors
      }
    }
  };

  return (
    <div className="mt-6">
      <div className="rounded-xl bg-slate-50 p-4 text-sm">
        <span className="font-medium">Agent state:</span> {agentState}
        <p className="mt-1 text-slate-600">
          Prototype transcript mode. Add a rationale while working so it is captured in the Work Map.
        </p>
      </div>

      <div className="mt-4 max-h-64 space-y-2 overflow-auto text-sm">
        {lines.length === 0 && <p className="text-slate-400">No transcript yet.</p>}
        {lines.map((l, i) => (
          <div key={i} className="rounded-lg border bg-white p-2">
            <span className="font-medium capitalize">{l.speaker}:</span> {l.text}
          </div>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="e.g., This compressor exceeds our capitalization threshold"
          className="flex-1 rounded border px-2 py-1 text-sm"
        />
        <button onClick={send} className="rounded bg-slate-900 px-3 py-1 text-sm text-white">
          Add
        </button>
      </div>
    </div>
  );
}
