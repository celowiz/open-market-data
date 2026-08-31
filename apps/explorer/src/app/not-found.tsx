import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Página não encontrada",
};

export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-foreground">Página não encontrada</h1>
      <p className="mt-2 text-muted">Essa rota do Explorador não existe.</p>
      <p className="mt-4">
        <Link href="/" className="font-medium text-accent hover:underline">
          Voltar ao início
        </Link>
      </p>
    </div>
  );
}
