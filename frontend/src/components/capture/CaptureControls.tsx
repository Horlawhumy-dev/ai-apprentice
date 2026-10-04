"use client";

import { useCaptureState } from "@/hooks/useCaptureState";

export default function CaptureControls({ eventCount, lastEventAt }: { eventCount: number; lastEventAt: number | null }) {
  const { status } = useCaptureState();
  return (
    <div className="mt-5 grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border bg-white p-3">
        <p className="text-xs uppercase text-slate-500">Status</p>
        <p className="mt-1 font-medium">{status}</p>
      </div>
      <div className="rounded-lg border bg-white p-3">
        <p className="text-xs uppercase text-slate-500">Events</p>
        <p className="mt-1 font-medium">{eventCount}</p>
      </div>
      <div className="rounded-lg border bg-white p-3">
        <p className="text-xs uppercase text-slate-500">Latest event</p>
        <p className="mt-1 font-medium">{lastEventAt ? new Date(lastEventAt).toLocaleTimeString() : "—"}</p>
      </div>
    </div>
  );
}
