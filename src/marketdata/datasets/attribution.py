ATTRIBUTION_BY_SOURCE: dict[str, str] = {
    "cvm": "data from Portal de Dados Abertos CVM, https://dados.cvm.gov.br/",
    "tesouro": "data from Tesouro Transparente / Tesouro Nacional",
    "bcb": "data from Banco Central do Brasil open data / SGS / PTAX",
}


def attribution_for(source_names: list[str] | tuple[str, ...]) -> list[str]:
    snippets: list[str] = []
    for name in sorted(set(source_names)):
        snippet = ATTRIBUTION_BY_SOURCE.get(name)
        if snippet is not None:
            snippets.append(snippet)
    return snippets


def attribution_for_source(name: str) -> str | None:
    return ATTRIBUTION_BY_SOURCE.get(name)
