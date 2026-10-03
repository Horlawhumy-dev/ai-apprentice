"use client";

import { useEffect, useRef, useState } from "react";

export function useScreenShare() {
  const [isSharing, setIsSharing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  async function startSharing() {
    try {
      setError(null);

      if (!navigator.mediaDevices?.getDisplayMedia) {
        throw new Error("Screen sharing is not supported in this browser.");
      }

      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });

      streamRef.current = stream;
      setIsSharing(true);

      stream.getVideoTracks()[0]?.addEventListener("ended", stopSharing);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to share screen.");
    }
  }

  function stopSharing() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setIsSharing(false);
  }

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return { isSharing, error, streamRef, startSharing, stopSharing };
}
