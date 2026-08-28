"use client";

import type { ReactNode } from "react";

import { copy } from "@/lib/copy";
import { addUtcMonths, addUtcYears, defaultHistoryRange, todayIso } from "@/lib/dates";

export type DateRangeValue = {
  start: string;
  end: string;
};

type DateRangeFormProps = {
  start: string;
  end: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  onSubmit: (range?: DateRangeValue) => void;
  extra?: ReactNode;
  submitLabel?: string;
  disabled?: boolean;
  disabledHint?: string;
  showShortcuts?: boolean;
};

export function DateRangeForm({
  start,
  end,
  onStartChange,
  onEndChange,
  onSubmit,
  extra,
  submitLabel = copy.common.loadHistory,
  disabled = false,
  disabledHint,
  showShortcuts = true,
}: DateRangeFormProps) {
  const today = todayIso();
  const fiveYear = defaultHistoryRange(5);

  function applyRange(nextStart: string, nextEnd: string) {
    onStartChange(nextStart);
    onEndChange(nextEnd);
    onSubmit({ start: nextStart, end: nextEnd });
  }

  return (
    <form
      className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!disabled) {
          onSubmit();
        }
      }}
    >
      {showShortcuts ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-slate-800">{copy.shortcuts.range}</p>
          <div role="group" aria-label={copy.shortcuts.range} className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={disabled}
              onClick={() => applyRange(addUtcMonths(today, -1), today)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
            >
              {copy.shortcuts.oneMonth}
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => applyRange(addUtcYears(today, -1), today)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
            >
              {copy.shortcuts.oneYear}
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => applyRange(fiveYear.start, today)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
            >
              {copy.shortcuts.fiveYears}
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => applyRange("", today)}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
            >
              {copy.shortcuts.max}
            </button>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="start-date" className="text-sm font-medium text-slate-800">
            {copy.common.startDate}
          </label>
          <input
            id="start-date"
            name="start"
            type="date"
            value={start}
            disabled={disabled}
            onChange={(event) => onStartChange(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="end-date" className="text-sm font-medium text-slate-800">
            {copy.common.endDate}
          </label>
          <input
            id="end-date"
            name="end"
            type="date"
            value={end}
            disabled={disabled}
            onChange={(event) => onEndChange(event.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          />
        </div>
        <div className="contents">{extra}</div>
        <div className="flex items-end">
          <button
            type="submit"
            disabled={disabled}
            className="w-full rounded-md bg-teal-700 px-4 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {submitLabel}
          </button>
        </div>
      </div>
      {disabled && disabledHint ? <p className="text-sm text-slate-600">{disabledHint}</p> : null}
    </form>
  );
}
