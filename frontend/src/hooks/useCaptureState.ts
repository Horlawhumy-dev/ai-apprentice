"use client";

import { useSyncExternalStore } from "react";
import { getCaptureState, subscribe } from "@/services/captureStore";

export function useCaptureState() {
  return useSyncExternalStore(subscribe, getCaptureState, getCaptureState);
}
