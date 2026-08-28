export const copy = {
  productName: "Open Market Data",
  defaultTitle: "Início · Open Market Data",
  titleTemplate: "%s · Open Market Data",
  description:
    "Explorador somente leitura da API pública FastAPI /v1: cotações, séries, fundos, fontes, conjuntos de dados e cobertura.",
  nav: {
    home: "Início",
    series: "Séries",
    compare: "Comparar",
    sources: "Fontes",
    datasets: "Conjuntos de dados",
    coverage: "Cobertura",
    main: "Principal",
  },
  header: {
    subtitlePublic: "Explorador somente leitura da API pública /v1",
    subtitleLocal: "Explorador somente leitura de",
    statusOk: "API disponível",
    statusDown: "API indisponível",
    statusChecking: "Verificando API",
  },
  api: {
    publicUnavailable:
      "A API pública ainda não está disponível. Cotações, séries e fundos não podem ser carregados até que o FastAPI seja hospedado.",
    publicBanner:
      "API pública fora do ar / ainda não hospedada. Cotações, séries e fundos não podem ser carregados até que o FastAPI público esteja disponível.",
    localUnreachable: (base: string) =>
      `Não foi possível alcançar ${base}. Inicie o FastAPI (uvicorn na porta 8000) e defina CORS_ALLOWED_ORIGINS para incluir esta origem do Explorador (http://localhost:3000).`,
    unknown: "Erro desconhecido",
    errorHeading: "Erro da API",
  },
  offline: {
    compact: "Indisponível enquanto a API pública estiver fora do ar.",
    block: "Dados indisponíveis enquanto a API pública estiver fora do ar.",
    formHint: "O envio fica desativado até a API pública responder.",
    searchHint: "A busca não funciona enquanto a API pública estiver indisponível.",
  },
  footer:
    "Este Explorador de Dados lê apenas a API pública FastAPI /v1. Ele nunca se conecta ao PostgreSQL, nunca inventa preços ausentes e não oferece downloads em lote da B3 ou do Yahoo.",
  common: {
    loading: "Carregando…",
    loadMore: "Carregar mais",
    loadHistory: "Carregar histórico",
    retry: "Tentar novamente",
    startDate: "Data inicial",
    endDate: "Data final",
    priceType: "Tipo de preço",
    source: "Fonte",
    noSynthetic: "sem preço sintético",
    backfillSecondary: "Operadores: rode marketdata backfill se esperava histórico neste identificador.",
    openHistory: "Abrir histórico",
  },
  shortcuts: {
    oneMonth: "1M",
    oneYear: "1A",
    fiveYears: "5A",
    max: "máx",
    range: "Atalhos de período",
  },
} as const;
