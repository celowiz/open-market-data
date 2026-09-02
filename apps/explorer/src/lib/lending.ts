import type { LendingSnapshotResponse } from "@/lib/types";

export function latestLendingSnapshot(
  snapshots: LendingSnapshotResponse[],
  snapshotType: string,
): LendingSnapshotResponse | null {
  const match = snapshots.filter((row) => row.snapshot_type === snapshotType);
  if (match.length === 0) {
    return null;
  }
  return match.reduce((best, row) => (row.date > best.date ? row : best));
}

export function hasLendingData(snapshots: LendingSnapshotResponse[]): boolean {
  return snapshots.some(
    (row) => row.qty != null || row.avg_rate != null || row.contracts != null,
  );
}
