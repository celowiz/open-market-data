"use client";

import type { ReactNode } from "react";

type DateRangeFormProps = {
  start: string;
  end: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  onSubmit: () => void;
  extra?: ReactNode;
  submitLabel?: string;
};

export function DateRangeForm({
  start,
  end,
  onStartChange,
  onEndChange,
  onSubmit,
  extra,
  submitLabel = "Load history",
}: DateRangeFormProps) {
  return (
    <form
      className="grid gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor="start-date" className="text-sm font-medium text-slate-800">
          Start date
        </label>
        <input
          id="start-date"
          name="start"
          type="date"
          value={start}
          onChange={(event) => onStartChange(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="end-date" className="text-sm font-medium text-slate-800">
          End date
        </label>
        <input
          id="end-date"
          name="end"
          type="date"
          value={end}
          onChange={(event) => onEndChange(event.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>
      <div className="contents">{extra}</div>
      <div className="flex items-end">
        <button
          type="submit"
          className="w-full rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800"
        >
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
