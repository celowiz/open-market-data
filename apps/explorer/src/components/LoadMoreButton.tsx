import { copy } from "@/lib/copy";
import { btnGhost } from "@/lib/ui";

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
    <button type="button" onClick={onClick} disabled={loading || disabled} className={btnGhost}>
      {loading ? copy.common.loading : copy.common.loadMore}
    </button>
  );
}
