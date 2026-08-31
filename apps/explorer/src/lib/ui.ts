export const fieldClass =
  "min-h-11 rounded-xl border border-border bg-elevated px-3 py-2 text-sm text-foreground placeholder:text-muted transition-colors disabled:cursor-not-allowed disabled:opacity-50";

export const cardClass = "rounded-2xl border border-border bg-surface";

export const btnGhost =
  "rounded-xl border border-border bg-transparent px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-elevated disabled:cursor-not-allowed disabled:opacity-50";

export const btnAccent =
  "rounded-xl bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition-colors hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50";

export const linkClass = "font-medium text-accent hover:underline";

export const tableWrapClass = "max-w-full overflow-x-auto rounded-2xl border border-border bg-surface";

export const thClass = "px-3 py-2.5 text-xs font-medium uppercase tracking-wide text-muted";

export const tdClass = "px-3 py-2.5";

export const trClass = "border-t border-border/80 transition-colors hover:bg-elevated/70";

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
