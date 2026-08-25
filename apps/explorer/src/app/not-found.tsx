import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-slate-600">That Explorer route does not exist.</p>
      <p className="mt-4">
        <Link href="/" className="font-medium text-teal-800 hover:underline">
          Back to home
        </Link>
      </p>
    </div>
  );
}
