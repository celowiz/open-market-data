import { formatPctChange, type WindowDelta } from "@/lib/window-delta";
import { cn } from "@/lib/ui";

export function DeltaBadge({ delta }: { delta: WindowDelta }) {
  const color =
    delta.direction === "up"
      ? "text-up"
      : delta.direction === "down"
        ? "text-down"
        : "text-muted";
  const label = delta.pctChange === null ? "—" : formatPctChange(delta.pctChange);
  return (
    <span
      className={cn("font-mono text-sm tabular-nums", color)}
      title={`${delta.firstDate} → ${delta.lastDate}`}
    >
      {label}
    </span>
  );
}
