import { copy } from "@/lib/copy";

export function LoadMoreButton({
  hasMore,
  loading,
  onClick,
  disabled,
}: {
  hasMore: boolean;
  loading: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  if (!hasMore) {
    return null;
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || disabled}
      className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {loading ? copy.common.loading : copy.common.loadMore}
    </button>
  );
}
