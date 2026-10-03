export default async function WorkMapPage({
  params,
}: {
  params: Promise<{ workflowId: string }>;
}) {
  const { workflowId } = await params;

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <h1 className="text-3xl font-semibold">Work Map</h1>
      <p className="mt-2 text-slate-600">
        Workflow: {workflowId}
      </p>
      <p className="mt-6 rounded-xl border bg-white p-6">
        Workflow steps, decision reasons, guardrails, and source moments will
        appear here.
      </p>
    </main>
  );
}
