"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function InstrumentationCard({ sessionId }: { sessionId: string }) {
  const [copied, setCopied] = useState(false);
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const snippet = `<!-- AI Apprentice instrumentation -->
<script src="${origin}/sdk/ai-apprentice-capture.js"
        data-api-url="${API_URL}"
        data-session-id="${sessionId}"
        data-source="my_real_app"
        data-auto-track="true"></script>`;

  const copy = async () => {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="mt-6 rounded-2xl border bg-white p-6 shadow-sm">
      <h2 className="text-lg font-semibold">Capture your own system</h2>
      <p className="mt-1 text-sm text-slate-500">
        Add this snippet to the app you want to capture. It streams clicks, field changes and submits while this
        session is capturing, and stops automatically on Pause or Off Record.
      </p>
      <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
        <code suppressHydrationWarning>{snippet}</code>
      </pre>
      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={copy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
        >
          {copied ? "Copied" : "Copy snippet"}
        </button>
        <span className="text-xs text-slate-500">
          Or use <code className="rounded bg-slate-100 px-1">AIApprentice.init({"{"} sessionId, apiUrl {"}"})</code>.
        </span>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Mark specific controls with <code className="rounded bg-slate-100 px-1">data-ai-apprentice=&quot;type&quot;</code>,
        keep sensitive fields out of scope with{" "}
        <code className="rounded bg-slate-100 px-1">data-ai-apprentice-ignore</code>, and log reasoning with{" "}
        <code className="rounded bg-slate-100 px-1">AIApprentice.decision(&quot;why...&quot;)</code>.
      </p>
    </div>
  );
}
