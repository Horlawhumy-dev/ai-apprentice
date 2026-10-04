"use client";

import { useEffect, useState } from "react";
import { confirmWorkflow, updateStep } from "@/services/api";
import type { WorkMap as Workflow, WorkflowStep as Step } from "@/types/workflow";

export default function WorkMapView({ workflowId }: { workflowId: string }) {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [selected, setSelected] = useState<Step | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${base}/api/workflows/${workflowId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Workflow not found");
        return res.json();
      })
      .then((data) => {
        if (active) setWorkflow(data);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [workflowId]);

  const review = async (step: Step, review_status: string) => {
    const updated = await updateStep(workflowId, step.id, { review_status });
    setWorkflow((wf) =>
      wf ? { ...wf, steps: wf.steps.map((s) => (s.id === step.id ? { ...s, review_status: updated.review_status } : s)) } : wf
    );
    setSelected((s) => (s && s.id === step.id ? { ...s, review_status: updated.review_status } : s));
  };

  const saveReason = async (step: Step, reason: string) => {
    const updated = await updateStep(workflowId, step.id, { reason });
    setWorkflow((wf) => (wf ? { ...wf, steps: wf.steps.map((s) => (s.id === step.id ? { ...s, reason: updated.reason } : s)) } : wf));
    setSelected((s) => (s && s.id === step.id ? { ...s, reason: updated.reason } : s));
  };

  const confirm = async () => {
    await confirmWorkflow(workflowId);
    setWorkflow((wf) => (wf ? { ...wf, status: "confirmed" } : wf));
  };

  if (loading) return <p className="mt-6 text-slate-500">Loading Work Map…</p>;
  if (error) return <p className="mt-6 text-rose-600">{error}</p>;
  if (!workflow) return <p className="mt-6 text-slate-500">No workflow.</p>;

  const statusColor =
    workflow.status === "confirmed" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800";

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]">
      <section className="rounded-xl border bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{workflow.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{workflow.steps.length} steps</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-xs ${statusColor}`}>{workflow.status}</span>
            <button onClick={confirm} className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">
              Confirm workflow
            </button>
          </div>
        </div>

        <div className="mt-6 space-y-3">
          {workflow.steps.map((step) => (
            <button
              key={step.id}
              onClick={() => setSelected(step)}
              className={`w-full rounded-lg border p-4 text-left hover:bg-slate-50 ${
                selected?.id === step.id ? "border-slate-900" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium">{step.action}</span>
                <span className="text-xs text-slate-500">{step.timestamp_ms}ms</span>
              </div>
              {step.reason && <p className="mt-2 text-sm text-slate-600">{step.reason}</p>}
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    step.review_status === "confirmed"
                      ? "bg-emerald-100 text-emerald-800"
                      : step.review_status === "rejected"
                      ? "bg-rose-100 text-rose-800"
                      : step.review_status === "uncertain"
                      ? "bg-amber-100 text-amber-800"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {step.review_status ?? "proposed"}
                </span>
                {typeof step.confidence === "number" && (
                  <span className="text-xs text-slate-400">confidence {Math.round(step.confidence * 100)}%</span>
                )}
              </div>
            </button>
          ))}
        </div>
      </section>

      <aside className="rounded-xl border bg-white p-6">
        <h2 className="text-lg font-semibold">Step detail</h2>
        {!selected ? (
          <p className="mt-2 text-sm text-slate-500">Select a step to review evidence and confirm rules.</p>
        ) : (
          <div className="mt-4 space-y-4 text-sm">
            <div>
              <p className="text-xs uppercase text-slate-500">Action</p>
              <p className="font-medium">{selected.action}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Decision</p>
              <p className="font-medium">{selected.decision ?? "—"}</p>
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Reason</p>
              <textarea
                defaultValue={selected.reason ?? ""}
                onBlur={(e) => selected && e.target.value !== (selected.reason ?? "") && saveReason(selected, e.target.value)}
                rows={3}
                className="mt-1 w-full rounded border px-2 py-1"
                placeholder="Add the expert's reason"
              />
            </div>
            <div>
              <p className="text-xs uppercase text-slate-500">Evidence</p>
              {(selected.evidence?.transcript_excerpts?.length ?? 0) > 0 && (
                <ul className="mt-1 space-y-1">
                  {selected.evidence?.transcript_excerpts?.map((t) => (
                    <li key={t.id} className="rounded border bg-slate-50 p-2 text-xs">
                      <span className="font-medium capitalize">{t.speaker}:</span> {t.text}
                    </li>
                  ))}
                </ul>
              )}
              <pre className="mt-1 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(selected.evidence, null, 2)}</pre>
            </div>
            {(selected.guardrails?.length ?? 0) > 0 && (
              <div>
                <p className="text-xs uppercase text-slate-500">Guardrails</p>
                <ul className="mt-1 space-y-1">
                  {selected.guardrails?.map((g, i) => (
                    <li key={i} className="rounded border p-2">
                      <span className="font-medium">{g.severity}</span>: {g.rule}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <button onClick={() => review(selected, "confirmed")} className="rounded-lg bg-emerald-600 px-3 py-1.5 text-white">
                Confirm
              </button>
              <button onClick={() => review(selected, "rejected")} className="rounded-lg bg-rose-600 px-3 py-1.5 text-white">
                Reject
              </button>
              <button onClick={() => review(selected, "uncertain")} className="rounded-lg border px-3 py-1.5">
                Mark uncertain
              </button>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
