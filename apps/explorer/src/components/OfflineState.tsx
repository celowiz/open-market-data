import { copy } from "@/lib/copy";

export function OfflineState({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return <p className="text-sm text-slate-600">{copy.offline.compact}</p>;
  }
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-700">
      <p>{copy.offline.block}</p>
    </div>
  );
}
