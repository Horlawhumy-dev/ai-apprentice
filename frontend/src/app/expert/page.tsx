"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import ScreenSharePreview from "@/components/capture/ScreenSharePreview";
import CaptureControls from "@/components/capture/CaptureControls";
import DebriefPanel from "@/components/capture/DebriefPanel";
import InstrumentationCard from "@/components/capture/InstrumentationCard";
import AgentPanel from "@/components/voice-agent/AgentPanel";
import { useCaptureState } from "@/hooks/useCaptureState";
import {
  setSession as setStoreSession,
  setStatus as setStoreStatus,
  setEventStats,
} from "@/services/captureStore";
import {
  createSession,
  getSession,
  startCapture,
  pauseSession,
  offRecord,
  resumeSession,
  finishSession,
  generateWorkMap,
} from "@/services/api";

interface SessionType {
  session_id: string;
  status: string;
  workflow_title: string;
  expert_name?: string;
}

export default function ExpertPage() {
  const [session, setSession] = useState<SessionType | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const capture = useCaptureState();
  const status = capture.status;
  const canPauseResume = status === "capturing" || status === "paused" || status === "off_record";
  const canFinish = canPauseResume;

  useEffect(() => {
    if (!session) return;
    let active = true;
    const poll = async () => {
      try {
        const s = await getSession(session.session_id);
        if (!active) return;
        if (s.status) setStoreStatus(s.status);
        setEventStats(s.event_count ?? 0, s.latest_event?.timestamp_ms ?? null);
      } catch {
        // ignore transient polling errors
      }
    };
    void poll();
    const timer = setInterval(poll, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [session]);

  const run = async (fn: () => Promise<void>) => {
    if (busy) return;
    try {
      setError(null);
      setBusy(true);
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const handleCreateSession = () =>
    run(async () => {
      const s = await createSession({ workflow_title: "Invoice Processing", expert_name: "Demo Expert" });
      setSession(s);
      setStoreSession(s.session_id);
    });

  const handleStart = () =>
    run(async () => {
      if (!session) return;
      const r = await startCapture(session.session_id);
      setStoreStatus(r.status);
    });

  const handlePause = () =>
    run(async () => {
      if (!session) return;
      const r = await pauseSession(session.session_id);
      setStoreStatus(r.status);
    });

  const handleResume = () =>
    run(async () => {
      if (!session) return;
      const r = await resumeSession(session.session_id);
      setStoreStatus(r.status);
    });

  const handleOffRecord = () =>
    run(async () => {
      if (!session) return;
      const r = await offRecord(session.session_id);
      setStoreStatus(r.status);
    });

  const handleFinish = () =>
    run(async () => {
      if (!session) return;
      await finishSession(session.session_id);
      setStoreStatus("finished");
    });

  const handleGenerate = async () => {
    if (!session) return;
    const wm = await generateWorkMap(session.session_id);
    setWorkflowId(wm.id);
  };

  return (
    <main className="min-h-screen bg-slate-50 p-8 text-slate-900">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">AI Apprentice / Capture</p>
          <h1 className="text-3xl font-semibold">Expert Capture</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm text-emerald-800">
            {capture.sessionId ? `Session ${capture.sessionId.slice(0, 8)}` : "No session"}
          </span>
          <span className="rounded-full bg-slate-200 px-3 py-1 text-sm">Status: {status}</span>
        </div>
      </header>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Expert workspace</h2>
          <p className="mt-1 text-sm text-slate-500">Share your screen and work as you normally would.</p>
          <ScreenSharePreview />
          <CaptureControls eventCount={capture.eventCount} lastEventAt={capture.lastEventAt} />
          <div className="mt-5 flex flex-wrap gap-3">
            {!session && (
              <button onClick={handleCreateSession} className="rounded-lg bg-slate-900 px-4 py-2 text-white">
                Create session
              </button>
            )}
            {session && status === "created" && (
              <button onClick={handleStart} className="rounded-lg bg-slate-900 px-4 py-2 text-white">
                Start capture
              </button>
            )}
            {status === "capturing" && (
              <button onClick={handlePause} disabled={busy} className="rounded-lg border px-4 py-2 disabled:opacity-50">
                Pause capture
              </button>
            )}
            {(status === "paused" || status === "off_record") && (
              <button onClick={handleResume} disabled={busy} className="rounded-lg border px-4 py-2 disabled:opacity-50">
                Resume capture
              </button>
            )}
            {status === "capturing" && (
              <button
                onClick={handleOffRecord}
                disabled={busy}
                className="rounded-lg border border-rose-200 px-4 py-2 text-rose-700 disabled:opacity-50"
              >
                Off Record
              </button>
            )}
            <button
              onClick={handleFinish}
              disabled={busy || !canFinish}
              className="rounded-lg border px-4 py-2 disabled:opacity-50"
            >
              Finish task
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
          <p className="mt-4 text-sm text-slate-500">
            Capture the built-in{" "}
            <Link className="underline" href="/demo-erp" target="_blank">
              Demo ERP
            </Link>
            , or instrument your own system with the snippet below.
          </p>
        </div>

        <aside className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Apprentice interviewer</h2>
          <p className="mt-1 text-sm text-emerald-700">● Agent panel</p>
          <AgentPanel />
        </aside>
      </section>

      {session && status !== "finished" && <InstrumentationCard sessionId={session.session_id} />}

      {status === "finished" && session && !workflowId && (
        <DebriefPanel sessionId={session.session_id} onGenerate={handleGenerate} />
      )}

      <footer className="mt-6 text-sm text-slate-500">
        {workflowId && (
          <>
            <Link className="underline" href={`/work-map/${workflowId}`}>
              View Work Map ({workflowId.slice(0, 8)})
            </Link>
            {" · "}
            <Link className="underline" href={`/apprentice?workflow=${workflowId}`}>
              Train with this map
            </Link>
            {" · "}
          </>
        )}
        <Link className="underline" href="/apprentice">
          Open Apprentice Mode
        </Link>
      </footer>
    </main>
  );
}
