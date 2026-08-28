import { LoadingState } from "@/components/Status";

export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <LoadingState label="Carregando…" />
    </div>
  );
}
