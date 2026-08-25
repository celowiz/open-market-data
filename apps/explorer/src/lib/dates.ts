export function formatLocalIso(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function defaultHistoryRange(years = 5): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  start.setFullYear(start.getFullYear() - years);
  return { start: formatLocalIso(start), end: formatLocalIso(end) };
}

export function todayIso(): string {
  return formatLocalIso(new Date());
}

export function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function routeParam(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return safeDecode(value[0] ?? "");
  }
  return safeDecode(value ?? "");
}
