import { copy } from "@/lib/copy";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-600">
        <p>{copy.footer}</p>
      </div>
    </footer>
  );
}
