export type ExampleKind = "quote" | "series" | "fund";

export type HomeExample = {
  kind: ExampleKind;
  title: string;
  identifier: string;
  href: string;
  description: string;
};

export const HOME_EXAMPLES: HomeExample[] = [
  {
    kind: "quote",
    title: "Tesouro",
    identifier: "LTN:2029-01-01",
    href: `/quotes/${encodeURIComponent("LTN:2029-01-01")}`,
    description: "Cotação de título público (tipo + vencimento).",
  },
  {
    kind: "series",
    title: "BCB",
    identifier: "BCB:CDI_DAILY",
    href: `/series/${encodeURIComponent("BCB:CDI_DAILY")}`,
    description: "Observação diária da série de mercado CDI.",
  },
  {
    kind: "fund",
    title: "CVM",
    identifier: "00017024000153",
    href: `/funds/${encodeURIComponent("00017024000153")}`,
    description: "Valor da cota de fundo por CNPJ.",
  },
  {
    kind: "quote",
    title: "Ação B3",
    identifier: "PETR4",
    href: `/quotes/${encodeURIComponent("PETR4")}`,
    description: "Cotação de ação (LAST/fechamento).",
  },
  {
    kind: "quote",
    title: "Futuro B3",
    identifier: "DI1F27",
    href: `/quotes/${encodeURIComponent("DI1F27")}`,
    description: "Ajuste oficial de futuro de DI.",
  },
  {
    kind: "quote",
    title: "Yahoo",
    identifier: "AAPL",
    href: `/quotes/${encodeURIComponent("AAPL")}`,
    description: "Fechamento acionário global não oficial (Yahoo).",
  },
];

export const BRAZIL_HOME_EXAMPLES = HOME_EXAMPLES.filter((item) => item.identifier !== "AAPL");
export const SECONDARY_HOME_EXAMPLES = HOME_EXAMPLES.filter((item) => item.identifier === "AAPL");

/** Default home hero: PETR4 first, then the other Brazilian examples. */
export const DEFAULT_HERO_EXAMPLES: HomeExample[] = [
  ...HOME_EXAMPLES.filter((item) => item.identifier === "PETR4"),
  ...BRAZIL_HOME_EXAMPLES.filter((item) => item.identifier !== "PETR4"),
];
