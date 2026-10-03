import Link from "next/link";

export default function ExpertPage() {
  return (
    <main className="min-h-screen bg-slate-50 p-8 text-slate-900">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">AI Apprentice / Capture</p>
          <h1 className="text-3xl font-semibold">Expert Capture</h1>
        </div>
        <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm text-emerald-800">
          Session ready
        </span>
      </header>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
        <div className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Expert workspace</h2>
          <p className="mt-1 text-sm text-slate-500">
            Share your screen and work as you normally would.
          </p>
          <div className="mt-6 flex min-h-80 flex-col items-center justify-center rounded-xl border-2 border-dashed bg-slate-50 p-8 text-center">
            <p className="text-lg font-medium">Screen share preview</p>
            <p className="mt-2 text-sm text-slate-500">
              Connect screen capture to preview the selected screen here.
            </p>
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <button className="rounded-lg bg-slate-900 px-4 py-2 text-white">
              Start screen share
            </button>
            <button className="rounded-lg border px-4 py-2">
              Pause capture
            </button>
            <button className="rounded-lg border border-rose-200 px-4 py-2 text-rose-700">
              Finish task
            </button>
          </div>
        </div>

        <aside className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Apprentice interviewer</h2>
          <p className="mt-1 text-sm text-emerald-700">● Agent panel placeholder</p>
          <div className="mt-6 rounded-xl bg-slate-50 p-4 text-sm">
            I’ll observe your workflow and ask why at meaningful decision points.
          </div>
          <p className="mt-6 text-sm text-slate-500">
            Voice connection and transcript will appear here.
          </p>
        </aside>
      </section>

      <footer className="mt-6 text-sm text-slate-500">
        <Link className="underline" href="/work-map/demo">
          Preview Work Map
        </Link>
        {" · "}
        <Link className="underline" href="/apprentice">
          Open Apprentice Mode
        </Link>
      </footer>
    </main>
  );
}
