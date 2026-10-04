"use client";

export type CaptureStatus = "idle" | "created" | "capturing" | "paused" | "off_record" | "finished";

type Listener = () => void;

export interface CaptureState {
  sessionId: string | null;
  status: CaptureStatus;
  eventCount: number;
  lastEventAt: number | null;
}

let state: CaptureState = {
  sessionId: null,
  status: "idle",
  eventCount: 0,
  lastEventAt: null,
};

const listeners = new Set<Listener>();

function emit() {
  listeners.forEach((l) => l());
}

export function getCaptureState(): CaptureState {
  return state;
}

export function subscribe(l: Listener) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

export function setSession(sessionId: string | null) {
  state = {
    sessionId,
    status: sessionId ? "created" : "idle",
    eventCount: 0,
    lastEventAt: null,
  } as CaptureState;
  emit();
}

export function setStatus(status: CaptureStatus) {
  if (state.status === status) return;
  state = { ...state, status };
  emit();
}

export function recordEvent(timestampMs: number) {
  state = { ...state, eventCount: state.eventCount + 1, lastEventAt: timestampMs };
  emit();
}

export function setEventStats(eventCount: number, lastEventAt: number | null) {
  if (state.eventCount === eventCount && state.lastEventAt === lastEventAt) return;
  state = { ...state, eventCount, lastEventAt };
  emit();
}

export function isCapturing() {
  return state.status === "capturing";
}

export function getActiveSessionId() {
  return state.sessionId;
}
