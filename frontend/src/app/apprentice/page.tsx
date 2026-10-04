"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  createApprenticeSession,
  evaluateAction,
  finishApprenticeSession,
} from "@/services/api";

interface TutorResult {
  allowed: boolean;
  matched_rule_id?: string | null;
  severity: string;
  explanation: string;
  evidence_step_id?: string | null;
  evidence?: {
    action: string;
    reason: string | null;
    timestamp_ms: number;
    guardrails: unknown[];
  } | null;
  next_question?: string | null;
  attempt_id?: string;
}

interface CaseData {
  case_id: string;
  title: string;
  supplier: string;
  amount: number;
  proposed_cost_center: string;
  required_asset_number: boolean;
  note: string;
}

export default function ApprenticePage() {
  const [workflowId, setWorkflowId] = useState("");
  const [caseData, setCaseData] = useState<CaseData | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [costCenter, setCostCenter] = useState("CAPEX");
  const [assetNumber, setAssetNumber] = useState("");
  const [result, setResult] = useState<TutorResult | null>(null);
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const wf = params.get("workflow");
      if (wf) setWorkflowId(wf);
    }, 0);
    return () => clearTimeout(t);
  }, []);

  const startCase = async (wfId: string) => {
    try {
      setError(null);
      const created = await createApprenticeSession(wfId, "case_alpha");
      setSessionId(created.id);
      setCaseData(created.case);
      setCostCenter(created.case.proposed_cost_center);
      setAssetNumber("");
      setResult(null);
      setSummary(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start case. Is the workflow confirmed?");
    }
  };

  const save = async () => {
    if (!sessionId || !caseData) return;
    const res = await evaluateAction(sessionId, "save_attempted", {
      cost_center: costCenter,
      amount: caseData.amount,
      asset_number: assetNumber,
    });
    setResult(res);
  };

  const finish = async () => {
    if (!sessionId) return;
    const res = await finishApprenticeSession(sessionId);
    setSummary(res.summary);
  };

  return (
    <main className="min-h-screen bg-slate-50 p-8 text-slate-900">
      <h1 className="text-3xl font-semibold">Apprentice Training</h1>
      <p className="mt-2 text-slate-600">
        Practice a different case and receive guidance based on the expert Work Map.
      </p>

      {!sessionId && (
        <section className="mt-6 max-w-xl rounded-xl border bg-white p-6">
          <label className="text-sm text-slate-700">Confirmed workflow ID</label>
          <input
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
            placeholder="Paste the workflow UUID from the Work Map"
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
          <button
            onClick={() => startCase(workflowId)}
            disabled={!workflowId}
            className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          >
            Start training case
          </button>
          {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
        </section>
      )}

      {caseData && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <section className="rounded-xl border bg-white p-6">
            <h2 className="text-lg font-semibold">{caseData.title}</h2>
            <p className="mt-1 text-sm text-slate-500">
              Supplier: {caseData.supplier} • Amount: ${caseData.amount.toLocaleString()}
            </p>
            <p className="mt-1 text-xs text-slate-400">{caseData.note}</p>

            <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-slate-500">Cost center</dt>
                <dd className="mt-1">
                  <select
                    value={costCenter}
                    onChange={(e) => setCostCenter(e.target.value)}
                    className="rounded border px-2 py-1"
                  >
                    <option value="OPEX">OPEX</option>
                    <option value="CAPEX">CAPEX</option>
                  </select>
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Asset number</dt>
                <dd className="mt-1">
                  <input
                    value={assetNumber}
                    onChange={(e) => setAssetNumber(e.target.value)}
                    placeholder="A-1001"
                    className="rounded border px-2 py-1"
                  />
                </dd>
              </div>
            </dl>

            <div className="mt-6 flex gap-3">
              <button onClick={save} className="rounded-lg bg-slate-900 px-4 py-2 text-white">
                Save
              </button>
              <button onClick={finish} className="rounded-lg border px-4 py-2">
                Finish case
              </button>
            </div>

            {result && (
              <div
                className={`mt-4 rounded-lg border p-4 ${
                  result.allowed ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50"
                }`}
              >
                <p className="font-medium">
                  {result.allowed ? "Allowed" : result.severity === "warn" ? "Please reconsider" : "Blocked"}
                </p>
                <p className="mt-2 text-sm">{result.explanation}</p>
                {result.next_question && <p className="mt-2 text-sm italic">{result.next_question}</p>}
                {result.evidence && (
                  <div className="mt-3 rounded border border-slate-200 bg-white p-3 text-xs">
                    <p className="font-medium">Expert evidence: {result.evidence.action}</p>
                    {result.evidence.reason && <p className="mt-1 text-slate-600">{result.evidence.reason}</p>}
                    <p className="mt-1 text-slate-400">at {result.evidence.timestamp_ms}ms</p>
                    {workflowId && (
                      <Link className="mt-2 inline-block underline" href={`/work-map/${workflowId}`}>
                        Open Work Map
                      </Link>
                    )}
                  </div>
                )}
              </div>
            )}

            {summary && (
              <div className="mt-4 rounded-lg border bg-slate-50 p-4 text-sm">
                <p className="font-medium">Session summary</p>
                <p className="mt-1">Attempts: {summary.attempts} • Blocked: {summary.blocked} • Allowed: {summary.allowed}</p>
              </div>
            )}
          </section>

          <aside className="rounded-xl border bg-white p-6">
            <h2 className="text-lg font-semibold">Tutor</h2>
            <p className="mt-2 text-sm text-slate-600">
              The tutor uses only expert-confirmed rules. If you see a risk, it links back to the evidence moment.
            </p>
          </aside>
        </div>
      )}
    </main>
  );
}
