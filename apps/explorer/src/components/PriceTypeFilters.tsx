import { cn } from "@/lib/ui";

export function PriceTypeFilters({
  options,
  value,
  onChange,
  label,
}: {
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium text-foreground">{label}</p>
      <div role="group" aria-label={label} className="flex flex-wrap gap-1">
        {options.map((option) => {
          const pressed = value === option;
          return (
            <button
              key={option}
              type="button"
              aria-pressed={pressed}
              onClick={() => onChange(option)}
              className={cn(
                "rounded-full px-3 py-1.5 font-mono text-xs font-medium transition-colors",
                pressed
                  ? "bg-accent text-accent-fg"
                  : "border border-border text-muted hover:bg-elevated hover:text-foreground",
              )}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}
