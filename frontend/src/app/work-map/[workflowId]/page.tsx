import WorkMapView from "@/components/work-map/WorkMapView";

export default async function WorkMapPage({
  params,
}: {
  params: Promise<{ workflowId: string }>;
}) {
  const { workflowId } = await params;

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <h1 className="text-3xl font-semibold">Work Map</h1>
      <p className="mt-2 text-slate-600">Review workflow steps, confirm rules, and inspect evidence.</p>
      <WorkMapView workflowId={workflowId} />
    </main>
  );
}
