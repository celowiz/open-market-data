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
      <p className="text-sm font-medium text-slate-800">{label}</p>
      <div role="group" aria-label={label} className="flex flex-wrap gap-2">
        {options.map((option) => {
          const pressed = value === option;
          return (
            <button
              key={option}
              type="button"
              aria-pressed={pressed}
              onClick={() => onChange(option)}
              className={`rounded-md px-3 py-1.5 font-mono text-xs font-medium ${
                pressed
                  ? "bg-teal-700 text-white"
                  : "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}
