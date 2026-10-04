import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 p-8 text-slate-900">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-4xl font-semibold">AI Apprentice</h1>
        <p className="mt-2 text-slate-600">Capture → Map → Teach</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          <Link className="rounded-xl border bg-white p-6 shadow-sm hover:bg-slate-50" href="/expert">
            <h2 className="text-xl font-semibold">Expert Capture</h2>
            <p className="mt-1 text-sm text-slate-600">Record workflow, answer questions, build Work Map</p>
          </Link>
          <Link className="rounded-xl border bg-white p-6 shadow-sm hover:bg-slate-50" href="/work-map/demo">
            <h2 className="text-xl font-semibold">Work Map</h2>
            <p className="mt-1 text-sm text-slate-600">Review timeline, decisions, guardrails, evidence</p>
          </Link>
          <Link className="rounded-xl border bg-white p-6 shadow-sm hover:bg-slate-50" href="/apprentice">
            <h2 className="text-xl font-semibold">Apprentice</h2>
            <p className="mt-1 text-sm text-slate-600">Practice with guardrails and coaching</p>
          </Link>
        </div>
      </div>
    </main>
  );
}
