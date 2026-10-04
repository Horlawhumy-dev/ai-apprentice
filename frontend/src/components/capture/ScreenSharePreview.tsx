"use client";

import { useRef } from "react";
import { useScreenShare } from "@/hooks/use-screen-share";

export default function ScreenSharePreview() {
  const { isSharing, error, streamRef, startSharing, stopSharing } = useScreenShare();
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const start = async () => {
    await startSharing();
    if (videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  };

  const stop = () => {
    stopSharing();
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  return (
    <div className="mt-6">
      <div className="flex min-h-80 flex-col items-center justify-center rounded-xl border-2 border-dashed bg-slate-50 p-4 text-center">
        {!isSharing && (
          <div>
            <p className="text-lg font-medium">Screen share preview</p>
            <p className="mt-2 text-sm text-slate-500">Start sharing to preview the selected screen.</p>
          </div>
        )}
        <video ref={videoRef} autoPlay muted playsInline className={isSharing ? "max-h-96 w-full" : "hidden"} />
      </div>
      <div className="mt-4 flex gap-3">

        {!isSharing ? (
          <button onClick={start} className="rounded-lg bg-slate-900 px-4 py-2 text-white">
            Start screen share
          </button>
        ) : (
          <button onClick={stop} className="rounded-lg border px-4 py-2">
            Stop screen share
          </button>
        )}
      </div>
      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
    </div>
  );
}
