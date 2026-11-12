/** Temporary stand-in for screens not built yet. Each one names the roadmap tasks that replace it. */
export function Placeholder({
  title,
  detail,
  tasks,
}: {
  title: string;
  detail?: string;
  tasks: string;
}) {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {detail && <p className="opacity-70">{detail}</p>}
      <p className="text-sm opacity-50">Roadmap: {tasks}</p>
    </main>
  );
}
