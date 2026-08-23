# MASTER PROMPT — Open-Source Financial Market Data Platform

## 1. Papel do agente

Você atuará como principal engenheiro de software e arquiteto deste projeto.

Trabalhe em modo agêntico e com autonomia. Antes de implementar, investigue as fontes de dados, projetos open-source de referência, licenças, formatos e limitações técnicas.

O projeto deve priorizar:

- simplicidade;
- robustez;
- auditabilidade;
- baixo custo operacional;
- facilidade de contribuição;
- independência de fornecedores;
- fontes oficiais e públicas;
- arquitetura extensível;
- documentação de alta qualidade;
- reprodutibilidade.

Não implemente abstrações sofisticadas sem necessidade.

Não construa funcionalidades fora do escopo inicial antes de termos o pipeline principal funcionando end-to-end.

---



# 2. Visão do projeto

Queremos construir uma plataforma **open-source de market data financeiro**, inicialmente focada no mercado brasileiro, mas arquitetada para suportar ativos e fontes globais.

O projeto nascerá de uma POC cujo objetivo original era verificar se seria possível substituir o Bloomberg Terminal para obtenção de cotações diárias utilizando dados públicos e gratuitos.

A partir de agora, porém, o projeto deve ser tratado como um produto open-source independente.

Os três produtos principais são:

```text
1. Data ingestion platform
2. Public financial datasets
3. Public market data API
```

A plataforma deverá:

- coletar dados financeiros automaticamente;
- buscar prioritariamente fontes oficiais;
- normalizar diferentes fontes em um modelo comum;
- armazenar histórico;
- preservar os arquivos originais;
- permitir auditoria completa;
- publicar datasets estruturados;
- disponibilizar API pública;
- permitir que qualquer desenvolvedor consulte os dados;
- aceitar contribuições externas;
- ser facilmente executável por terceiros;
- possuir documentação pública;
- ser apresentada futuramente no meu portfólio pessoal.

---



# 3. Repositório

O projeto ficará hospedado em meu GitHub pessoal.

Será um repositório:

```text
PUBLIC
```

O nome definitivo ainda pode mudar.

Caso seja necessário utilizar um nome temporário durante a implementação, use:

```text
open-market-data
```

Não acople branding ao código.

O projeto deve ser fácil de renomear futuramente.

---



# 4. Objetivo principal da primeira versão

A primeira versão precisa responder com dados reais:

> Qual percentual de um universo arbitrário de instrumentos financeiros pode ser precificado diariamente utilizando fontes públicas e gratuitas?

Ao mesmo tempo, devemos criar a infraestrutura necessária para que o resultado da coleta possa ser disponibilizado publicamente.

Exemplo de output:

```text
Market Data Coverage — 2026-08-21

Source          Instruments     Found     Missing
-------------------------------------------------
B3                   428          425          3
CVM                   96           94          2
Tesouro               31           31          0
BCB                    12           12          0
Yahoo                 182          179          3
-------------------------------------------------
TOTAL                 749          741          8

Coverage: 98.93%
```

---



# 5. O que NÃO estamos construindo inicialmente

Não estamos construindo:

- Bloomberg clone;
- trading terminal;
- order management system;
- real-time market data platform;
- portfolio management system;
- custodian reconciliation;
- portfolio accounting;
- frontend sofisticado;
- charting platform;
- user authentication;
- paid API;
- streaming data;
- WebSocket market data;
- tick database.

A prioridade inicial é:

```text
Daily / EOD market data
```

---



# 6. Filosofia de fontes

Prioridade conceitual:

```text
1. Government / official open data
2. Exchange / market infrastructure
3. Official regulatory datasets
4. Other public sources
5. Open-source adapters
6. Non-official aggregators
```

Para cada informação deve ficar explícito:

```text
source
price_type
reference_date
retrieved_at
is_official
redistribution_policy
```

Não ocultar a origem de nenhum dado.

---



# 7. Fontes iniciais

Os primeiros Providers devem ser:

```text
CVM
B3
Tesouro Nacional
Banco Central do Brasil
Yahoo Finance
```

Criar também interface para:

```text
ANBIMA
```

mas mantê-la inicialmente desabilitada.

---



# 8. Preços de custodiantes

NÃO consumir preços dos custodiantes nesta fase.

Já existe outra base independente com preços de custodiantes que poderá futuramente ser utilizada para validação.

Não implementar integração com custodiantes na primeira versão.

---



# 9. Projetos open-source que devem ser investigados

Antes de desenvolver os Providers, analise os seguintes projetos públicos:

```text
PythonicCafe/mercados
crdcj/PYield
wilsonfreitas/python-bcb
eduresser/cvm-sqlite
securo-finance/securo
hugorteixeira/brfutures
ranaroussi/yfinance
OpenBB-finance/OpenBB
rafa-rod/pyettj
joaopm33/fundspy
thobiast/fundosbr
amgsnt/cvm
```

Para cada projeto:

1. leia README;
2. examine documentação;
3. examine os arquivos relevantes;
4. verifique licença;
5. verifique atividade recente;
6. identifique arquitetura;
7. identifique endpoints utilizados;
8. identifique bibliotecas utilizadas;
9. identifique testes úteis;
10. avalie o que pode ser usado como dependência;
11. avalie o que deve ser apenas referência;
12. identifique código potencialmente obsoleto;
13. não copie código sem avaliar licença.

Crie:

```text
docs/OPEN_SOURCE_REVIEW.md
```

contendo uma tabela:

```text
Project
Purpose
Language
License
Active?
Useful components
Use as dependency?
Use as reference?
Risks
```

---



# 10. Projeto de referência principal

Analise especialmente:

```text
PythonicCafe/mercados
```

A biblioteca já possui suporte para dados públicos de:

- CVM;
- B3;
- BCB;
- Tesouro Nacional;
- IBGE;
- FundosNet.

Ela deve ser considerada uma das principais dependências potenciais.

Porém:

> nosso domínio nunca deve depender diretamente das classes dessa biblioteca.

Criar adapters próprios.

Exemplo:

```text
Our B3Provider
      ↓
mercados.B3
```

e nunca espalhar:

```python
from mercados.b3 import B3
```

pelo restante da aplicação.

---



# 11. PYield

Avaliar fortemente:

```text
crdcj/PYield
```

para:

- DI futuro;
- futuros de juros;
- títulos públicos;
- calendário brasileiro;
- Selic;
- IPCA;
- PTAX;
- curvas;
- validações de PU;
- convenções de renda fixa.

O PYield pode ser utilizado como dependência quando fizer sentido.

Não precisamos reimplementar cálculos financeiros já resolvidos corretamente.

---



# 12. Stack tecnológica escolhida

Stack principal:

```text
Python 3.12+
uv
Polars
Pydantic
FastAPI
SQLAlchemy 2
Alembic
PostgreSQL
httpx
tenacity
Typer
pytest
Ruff
Pyright or mypy
```

Avaliar também:

```text
structlog
orjson
psycopg
boto3
s3fs
duckdb
pyarrow
```

Não usar Pandas como dependência principal se Polars resolver adequadamente.

Pandas pode aparecer indiretamente por bibliotecas externas.

---



# 13. Infraestrutura escolhida

Arquitetura alvo:

```text
                  GitHub Public Repository
                           │
                           │
                    GitHub Actions
                           │
                           ▼
                    Python Ingestion
                           │
          ┌────────────────┴────────────────┐
          │                                 │
          ▼                                 ▼
 Cloudflare R2                      Neon PostgreSQL
 Raw + Parquet                      Serving database
          │                                 │
          │                                 ▼
          │                              FastAPI
          │                                 │
          │                              Railway
          │                                 │
          └────────────────┬────────────────┘
                           │
                      Cloudflare
                  cache / CDN / WAF
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
     api.example.com             data.example.com
```

Documentação:

```text
GitHub Pages
+
MkDocs
```

Frontend exploratório futuro:

```text
Next.js
+
Vercel
```

Vercel NÃO será inicialmente responsável pelo backend Python.

---



# 14. Banco de dados

Banco principal:

```text
PostgreSQL
```

Produção:

```text
Neon
```

PostgreSQL deve ser tratado como tecnologia padrão.

Não introduzir funcionalidades proprietárias do Neon no domínio.

A aplicação deve funcionar também com qualquer PostgreSQL convencional.

Isso é importante para:

- open source;
- self-hosting;
- portabilidade;
- contribuições;
- evitar vendor lock-in.

---



# 15. Desenvolvimento local

Permitir pelo menos duas opções:

```text
DATABASE_URL=<local PostgreSQL>
```

ou:

```text
DATABASE_URL=<Neon development branch>
```

Pode existir `docker-compose.yml` opcional oferecendo PostgreSQL local.

Docker não deve ser obrigatório para executar ferramentas puramente locais.

DuckDB poderá ser utilizado para:

- analytics;
- inspeção de Parquet;
- backfills;
- relatórios;
- testes;
- desenvolvimento exploratório.

Mas DuckDB NÃO será o serving database da API.

---



# 16. Object Storage

Utilizar:

```text
Cloudflare R2
```

compatível com S3.

Guardar lá:

```text
raw artifacts
normalized parquet
public datasets
manifests
snapshots
```

Nunca guardar arquivos grandes diretamente dentro do PostgreSQL.

---



# 17. Arquitetura de armazenamento

Ter três camadas conceituais:

```text
RAW
CURATED
SERVING
```



## RAW

Arquivo exatamente como veio da fonte.

Exemplos:

```text
CSV
ZIP
XML
JSON
TXT
```

Nenhuma modificação.

## CURATED

Dados normalizados em formatos analíticos.

Preferencialmente:

```text
Parquet
```



## SERVING

Dados necessários para API e consultas rápidas.

Armazenados em:

```text
PostgreSQL
```

---



# 18. Organização no R2

Estrutura sugerida:

```text
raw/
    b3/
        year=2026/
            month=08/
                day=21/

    cvm/
        year=2026/
            month=08/

    tesouro/
    bcb/
    yahoo/

curated/
    quotes/
        source=b3/
            year=2026/
                month=08/

    instruments/
    funds/
    rates/

public/
    datasets/
    manifests/
    snapshots/
```

Não assumir que essa estrutura é definitiva se outra estratégia de particionamento for claramente superior.

---



# 19. Public datasets

Um dos produtos centrais será permitir que qualquer pessoa baixe datasets diretamente.

Formato principal:

```text
Parquet
```

Formato secundário quando útil:

```text
CSV
```

Exemplo conceitual:

```text
https://data.example.com/quotes/source=b3/year=2026/month=08/...
```

Usuários deverão poder fazer:

```python
import polars as pl

df = pl.read_parquet("...")
```

ou:

```sql
SELECT *
FROM read_parquet('https://data.example.com/...');
```

via DuckDB.

---



# 20. Dataset manifest

Criar manifests públicos contendo:

```text
dataset_name
version
generated_at
source
reference_period
row_count
files
sha256
schema_version
license
redistribution_policy
```

Exemplo:

```text
public/manifests/quotes-b3-latest.json
```

Isso facilita uso por terceiros.

---



# 21. PostgreSQL Schema

Criar inicialmente tabelas equivalentes a:

```text
sources
instruments
instrument_identifiers
quotes
raw_artifacts
ingestion_runs
quality_events
provider_status
dataset_publications
```

Avaliar nomes finais.

Usar migrations com:

```text
Alembic
```

---



# 22. Instruments

Criar um Instrument Master canônico.

Modelo conceitual:

```text
instrument_id
asset_class
instrument_type
name
ticker
isin
cnpj
cnpj_fundo_classe
exchange
mic
currency
issuer
maturity_date
active_from
active_until
metadata
```

Nem todos obrigatórios.

Não usar ticker como chave universal.

---



# 23. Identificadores

Criar tabela separada:

```text
instrument_identifiers
```

Exemplo:

```text
instrument_id
identifier_type
identifier_value
source
valid_from
valid_until
```

Tipos:

```text
TICKER
ISIN
CUSIP
CNPJ
CNPJ_FUNDO_CLASSE
B3_SECURITY_ID
YAHOO_SYMBOL
SOURCE_ID
```

Um instrumento poderá possuir múltiplos identifiers.

---



# 24. Quote model

Modelo normalizado:

```text
quote_id
instrument_id
reference_date
price
currency
price_type
source_id
source_instrument_id
is_official
source_published_at
retrieved_at
raw_artifact_id
revision
quality_status
metadata
```

Preço monetário deve utilizar:

```text
Decimal / PostgreSQL NUMERIC
```

Nunca `float` para persistência monetária.

---



# 25. Semântica dos preços

Criar enum explícito.

Inicialmente:

```text
CLOSE
LAST
OFFICIAL_SETTLEMENT
ADJUSTMENT
PU_BASE
FUND_NAV
INDICATIVE
LAST_TRADE
REFERENCE
YIELD
```

Não converter silenciosamente entre tipos.

Exemplo:

```text
DI future settlement
```

não é:

```text
CLOSE
```

É:

```text
OFFICIAL_SETTLEMENT
```

---



# 26. Source model

Cada source deve possuir metadata:

```text
name
display_name
official
homepage
documentation_url
provider_status
redistribution_policy
data_license
notes
```

---



# 27. Política de redistribuição

Essa é uma exigência crítica.

A licença do client open-source NÃO implica direito de redistribuir o dado consumido.

Criar enum:

```text
PUBLIC
PUBLIC_WITH_ATTRIBUTION
API_ONLY
INTERNAL_ONLY
NO_REDISTRIBUTION
UNKNOWN
```

Cada source deve possuir explicitamente:

```text
redistribution_policy
```

Nunca publicar no R2 ou API um dataset cuja política não permita redistribuição.

---



# 28. DATA_LICENSES.md

Criar:

```text
DATA_LICENSES.md
```

Separado de:

```text
LICENSE
```

O primeiro descreve os dados.

O segundo descreve nosso código.

Para cada source registrar:

```text
Source
Data owner
Official?
Terms URL
Data license
Automated access allowed?
Redistribution allowed?
Commercial reuse allowed?
Attribution required?
Public API allowed?
Bulk dataset redistribution allowed?
Status
Last reviewed
```

Se não houver certeza:

```text
UNKNOWN
```

e desabilitar redistribuição pública até esclarecer.

---



# 29. Licença do nosso código

Utilizar inicialmente:

```text
Apache License 2.0
```

A menos que durante o discovery surja uma incompatibilidade relevante com dependências obrigatórias.

Documentar a decisão em ADR.

---



# 30. Provider architecture

Cada fonte deve ficar isolada atrás de Provider próprio.

Criar contrato conceitualmente semelhante:

```python
class MarketDataProvider(Protocol):
    name: str

    async def fetch(...) -> RawArtifact:
        ...

    def parse(...) -> Iterable[RawRecord]:
        ...

    def normalize(...) -> Iterable[DomainRecord]:
        ...
```

Pode adaptar a interface.

Separar obrigatoriamente:

```text
fetch
parse
normalize
persist
publish
```

---



# 31. Não permitir dependência de Provider no domínio

Código de domínio não deve saber que existe:

```text
yfinance
mercados
PYield
python-bcb
```

Somente Providers/adapters sabem.

Isso permitirá substituir:

```text
YahooProvider
```

por:

```text
FutureLicensedGlobalEquityProvider
```

sem alterar a API.

---



# 32. Raw Artifact

Todo download deve produzir RawArtifact.

Campos:

```text
id
source
source_url
reference_date
retrieved_at
content_type
encoding
filename
http_status
etag
last_modified
sha256
size_bytes
storage_uri
ingestion_run_id
```

Se dois arquivos forem idênticos:

```text
same SHA256
```

não duplicar storage sem necessidade.

---



# 33. Idempotência

Toda ingestão deve ser idempotente.

Executar duas vezes:

```bash
marketdata ingest b3 --date 2026-08-21
```

não deve criar duplicatas.

Porém, se a fonte republicar dados revisados:

```text
same source/date
different SHA
```

registrar nova versão.

Nunca apagar o raw anterior.

---



# 34. Provider CVM

Objetivo inicial:

```text
Investment Fund NAV / quota
```

Fonte:

```text
CVM Dados Abertos
Informe Diário de Fundos
```

Extrair:

```text
CNPJ
CNPJ_FUNDO_CLASSE
reference_date
VL_QUOTA
VL_PATRIM_LIQ
captacoes
resgates
numero_cotistas
```

O campo essencial é:

```text
VL_QUOTA
```

---



# 35. Mudanças de schema CVM

O sistema deve suportar campos novos e antigos.

Especialmente:

```text
CNPJ_FUNDO
```

versus:

```text
CNPJ_FUNDO_CLASSE
```

Não hardcodar permanentemente apenas um schema.

Criar compatibilidade/versionamento.

Consultar os arquivos META publicados pela CVM quando disponíveis.

---



# 36. Revisões da CVM

A CVM pode revisar informações.

Por isso, ingestão diária não deve buscar apenas exatamente D-1.

Utilizar uma janela configurável, por exemplo:

```text
recent_reprocess_days
```

para reprocessar períodos recentes.

Não assumir que observações históricas são sempre imutáveis.

---



# 37. Provider B3

Cobrir inicialmente:

```text
ações
BDRs
ETFs
FIIs
opções
DI futuro
dólar futuro
índice futuro
demais futuros relevantes
```

Investigar arquivos oficiais atuais, especialmente:

```text
BVBG.186
BVBG.187
BVBG.028
```

Não confiar em endpoints antigos apenas porque aparecem em projetos históricos.

Sempre validar contra a fonte oficial atual.

---



# 38. B3 Equities

Guardar quando disponível:

```text
open
high
low
close
last
volume
trades
```

Para valuation:

```text
CLOSE
```

quando semanticamente apropriado.

Não utilizar `Adjusted Close` para valuation diário.

Corporate actions serão tratados separadamente no futuro.

---



# 39. B3 derivatives

Derivativos precisam preservar settlement.

Especialmente:

```text
DI1
DOL
WDO
IND
WIN
```

Usar:

```text
OFFICIAL_SETTLEMENT
```

quando a B3 publicar ajuste oficial.

Nunca usar último negócio silenciosamente como substituto.

Guardar também quando possível:

```text
open
high
low
last
settlement
previous_settlement
open_interest
volume
```

---



# 40. Crédito privado brasileiro

Investigar dados públicos disponíveis para:

```text
Debêntures
CRI
CRA
```

Inicialmente via:

```text
B3
```

e outras fontes públicas legitimamente disponíveis.

Não assumir:

```text
LAST_TRADE = FAIR_VALUE
```

Se o único dado for negócio:

```text
price_type = LAST_TRADE
```

Se não houver negociação:

```text
NO_PUBLIC_PRICE
```

Não carregar silenciosamente último preço indefinidamente.

---



# 41. ANBIMA

Criar:

```text
AnbimaProvider
```

mas iniciar:

```text
enabled = false
```

Não criar scraper agressivo.

Não contornar mecanismos de acesso.

Antes de habilitar publicamente, documentar:

- termos;
- licença;
- automação permitida;
- redistribuição.

Pode existir futuramente:

```text
ManualAnbimaImportProvider
```

para arquivos obtidos legitimamente.

---



# 42. Provider Tesouro

Fonte:

```text
Tesouro Transparente
```

Obter preços oficiais dos títulos públicos.

Identidade do instrumento deve considerar:

```text
title_type
+
maturity_date
```

Não depender de ticker artificial.

Preservar:

```text
PU
rate
reference date
maturity
title type
```

Quando usar PU Base:

```text
price_type = PU_BASE
```

---



# 43. Tesouro implementation references

Estudar:

```text
PYield
```

e:

```text
securo-finance/securo
```

Não copiar código AGPL diretamente sem avaliação.

Usar as ideias arquiteturais:

- cache;
- normalização;
- matching por vencimento;
- Decimal;
- batch;
- parsing tolerante;
- testes.

---



# 44. Provider BCB

Utilizar preferencialmente:

```text
python-bcb
```

Cobrir inicialmente:

```text
PTAX
Selic
CDI
SGS
```

Adicionar outras séries futuramente.

Não construir client HTTP manual se `python-bcb` resolver robustamente.

---



# 45. Yahoo Provider

Usar:

```text
yfinance
```

apenas para a POC e desenvolvimento inicialmente.

Objetivo:

```text
US equities
European equities
global ETFs
```

Exemplo:

```text
AAPL
MSFT
NVDA
SPY
QQQ
ASML.AS
AIR.PA
```

Para valuation EOD utilizar:

```text
Close
```

e não `Adjusted Close`.

---



# 46. Yahoo licensing restriction

Muito importante:

`yfinance` possuir licença open-source NÃO significa que os dados Yahoo podem ser redistribuídos.

Portanto:

```text
source = YAHOO
is_official = false
redistribution_policy = UNKNOWN
```

até revisão jurídica/licenciamento.

A arquitetura deve permitir:

```text
Yahoo usable locally
```

mas:

```text
Yahoo disabled from public dataset/API
```

se redistribuição não estiver autorizada.

Implementar essa restrição programaticamente.

Não depender apenas de documentação.

---



# 47. Public API

Construir API com:

```text
FastAPI
```

A API deve consumir SOMENTE o banco normalizado.

Nunca:

```text
HTTP request
→ Provider
→ external website
```

durante uma consulta pública.

Fluxo correto:

```text
external source
      ↓
scheduled ingestion
      ↓
PostgreSQL
      ↓
FastAPI
      ↓
user
```

---



# 48. API versioning

Toda API pública deve começar versionada:

```text
/v1/
```

Nunca publicar endpoints sem versão.

---



# 49. Endpoints iniciais

Implementar ou preparar:

```text
GET /v1/health
GET /v1/sources
GET /v1/instruments
GET /v1/instruments/{identifier}
GET /v1/quotes/{identifier}
GET /v1/quotes/{identifier}/latest
GET /v1/quotes/{identifier}/history
GET /v1/funds/{identifier}/quotes
GET /v1/coverage
GET /v1/datasets
```

Permitir parâmetros:

```text
start
end
date
source
price_type
currency
limit
cursor
```

Utilizar paginação apropriada.

---



# 50. Identifier resolution

API não pode depender apenas de ticker.

Precisamos permitir buscas como:

```text
PETR4
BRPETRACNOR9
CNPJ
B3 identifier
```

Construir resolver central:

```text
InstrumentResolver
```

---



# 51. API responses

Resposta deve mostrar claramente provenance.

Exemplo conceitual:

```json
{
  "instrument": {
    "id": "...",
    "ticker": "PETR4",
    "isin": "BRPETRACNOR9"
  },
  "quote": {
    "date": "2026-08-21",
    "price": "32.51",
    "currency": "BRL",
    "price_type": "CLOSE",
    "source": "B3",
    "official": true
  }
}
```

Evitar floats binários em JSON quando precisão for relevante.

---



# 52. API documentation

FastAPI deve publicar:

```text
/docs
/redoc
/openapi.json
```

Adicionar exemplos.

Criar documentação adicional ensinando:

```text
Python
curl
JavaScript
R
```

para consumir a API.

---



# 53. API authentication

Inicialmente:

```text
NO API KEY
```

API pública e anônima.

Não criar sistema de usuários nesta etapa.

---



# 54. Rate limiting

Apesar de pública, API precisa de proteção.

Implementar rate limiting no edge ou aplicação.

Exemplo inicial:

```text
60 requests/minute/IP
```

Deixar configurável.

Preferencialmente utilizar Cloudflare para:

```text
rate limiting
WAF
bot protection
cache
```

---



# 55. Cloudflare caching

Como grande parte dos dados é histórica e imutável, usar cache agressivamente.

Por exemplo:

```text
/v1/quotes/PETR4?date=2025-01-02
```

pode possuir TTL muito alto.

Latest quote deve possuir TTL menor.

Criar estratégia de cache documentada.

---



# 56. API hosting

Deploy principal:

```text
Railway
```

Rodando FastAPI como serviço convencional.

Utilizar Dockerfile.

Não depender de runtime específico do Railway.

Aplicação deve poder ser executada:

```bash
uvicorn ...
```

em qualquer ambiente.

---



# 57. Vercel

Vercel NÃO será backend principal.

Poderá ser utilizado futuramente para:

```text
Next.js data explorer
```

Exemplo:

```text
marketdata.example.com
```

com:

- busca de instrumentos;
- histórico;
- fonte;
- documentação;
- snippets da API;
- download.

Isso é roadmap futuro.

---



# 58. Supabase

Não utilizar Supabase inicialmente.

A arquitetura escolheu:

```text
Neon + FastAPI
```

porque precisamos essencialmente de:

```text
PostgreSQL + public data API
```

e não necessitamos inicialmente de:

- Auth;
- Realtime;
- Supabase Storage;
- user management.

Não criar dependências específicas do Supabase.

---



# 59. GitHub Actions

Toda ingestão diária inicial deverá rodar através de:

```text
GitHub Actions
```

Como o repositório será público, aproveitar runners públicos padrão.

Criar workflows separados ou bem modularizados.

Por exemplo:

```text
.github/workflows/
    ci.yml
    ingest-b3.yml
    ingest-cvm.yml
    ingest-tesouro.yml
    ingest-bcb.yml
    publish-datasets.yml
    backfill.yml
```

Pode consolidar workflows quando isso reduzir duplicação.

---



# 60. Scheduling

Os horários devem considerar a publicação de cada fonte.

Não inventar um único horário universal.

Documentar por Provider:

```text
expected publication time
safe ingestion time
retry strategy
```

Utilizar timezone explicitamente:

```text
America/Sao_Paulo
```

quando relevante.

GitHub Actions cron usa UTC.

Documentar conversão.

---



# 61. Manual workflow dispatch

Todo workflow de ingestão deve permitir:

```text
workflow_dispatch
```

quando apropriado.

Isso permitirá:

```text
manual rerun
specific date
backfill
```

---



# 62. Backfills

Criar pipeline específico para históricos.

Exemplo:

```bash
marketdata backfill cvm --start 2024-01-01 --end 2024-12-31
```

Não executar centenas de downloads em paralelo sem respeitar as fontes.

Aplicar:

- concurrency control;
- retries;
- rate limiting;
- checkpointing.

---



# 63. CLI

Criar CLI com Typer.

Exemplos:

```bash
marketdata ingest cvm --date 2026-08-21
marketdata ingest b3 --date 2026-08-21
marketdata ingest tesouro --date 2026-08-21
marketdata ingest bcb --date 2026-08-21

marketdata ingest all --date 2026-08-21

marketdata backfill cvm --start ... --end ...

marketdata coverage --date 2026-08-21

marketdata latest PETR4

marketdata explain PETR4 --date 2026-08-21

marketdata providers

marketdata publish datasets --date 2026-08-21
```

Sintaxe pode ser refinada.

---



# 64. Provenance

Qualquer observação deve responder:

> De onde esse número veio?

Criar:

```bash
marketdata explain PETR4 --date 2026-08-21
```

Output aproximado:

```text
Instrument       PETR4
Reference date   2026-08-21
Price            32.51
Currency         BRL
Price type       CLOSE
Source           B3
Official         yes

Raw artifact
-------------
File             ...
SHA256           ...
Retrieved at     ...
Source URL       ...
Ingestion run    ...
```

---



# 65. Coverage engine

Criar componente que avalia um universo de ativos.

Input inicial poderá ser CSV.

Exemplo:

```text
config/instruments.csv
```

Campos:

```text
instrument_id
asset_class
ticker
isin
cnpj_fundo_classe
title_type
maturity_date
exchange
currency
preferred_provider
```

---



# 66. Coverage result

Para cada ativo:

```text
instrument
asset_class
provider
reference_date
price
price_type
status
staleness
missing_reason
```

Missing reasons:

```text
UNSUPPORTED
NO_DATA
NO_TRADE
MAPPING_ERROR
SOURCE_UNAVAILABLE
STALE
INVALID_VALUE
NOT_PUBLISHED_YET
REDISTRIBUTION_RESTRICTED
```

---



# 67. Quality engine

Implementar validações:

- price not null;
- valid numeric;
- positive quando aplicável;
- valid reference date;
- valid currency;
- duplicate detection;
- stale data;
- invalid identifier;
- unexpected schema;
- missing instrument mapping;
- future date;
- invalid price type.

Falha de um ativo não pode derrubar todo pipeline.

---



# 68. Quality events

Persistir:

```text
quality_events
```

Campos conceituais:

```text
event_id
ingestion_run_id
instrument_id
source
severity
event_type
message
metadata
created_at
```

Severities:

```text
INFO
WARNING
ERROR
CRITICAL
```

---



# 69. Ingestion runs

Cada execução deve possuir:

```text
ingestion_run_id
```

Registrar:

```text
provider
started_at
finished_at
requested_reference_date
status
artifacts_downloaded
records_parsed
records_normalized
records_inserted
records_updated
records_rejected
warnings
errors
duration
git_sha
```

---



# 70. Provider health

Tabela:

```text
provider_status
```

para indicar:

```text
last_success
last_failure
last_reference_date
consecutive_failures
latest_error
```

Preparar futuramente health dashboard.

---



# 71. Observabilidade

Inicialmente usar:

```text
structured logging
```

Não precisamos de stack completa de observabilidade.

Mas logs devem permitir troubleshooting.

Adicionar correlation IDs:

```text
ingestion_run_id
request_id
```

---



# 72. HTTP Client

Padronizar:

```text
timeout
retry
backoff
User-Agent
redirects
encoding
rate limit
conditional GET
```

Utilizar:

```text
httpx
tenacity
```

quando adequado.

Nenhum request sem timeout.

---



# 73. User-Agent

Criar User-Agent claro:

```text
open-market-data/<version> (+GitHub repository URL)
```

Isso é importante para consumo responsável de APIs públicas.

---



# 74. Conditional HTTP

Quando fonte oferecer:

```text
ETag
Last-Modified
```

utilizar:

```text
If-None-Match
If-Modified-Since
```

para evitar downloads desnecessários.

---



# 75. PostgreSQL performance

Criar índices apenas com justificativa.

Inicialmente considerar:

```text
quotes(instrument_id, reference_date DESC)

quotes(reference_date)

quotes(source_id, reference_date)

instrument_identifiers(identifier_type, identifier_value)
```

Não criar dezenas de índices prematuramente.

---



# 76. Partitioning

Não particionar `quotes` antecipadamente sem necessidade.

Documentar um threshold.

Exemplo:

> avaliar particionamento após dezenas de milhões de rows.

PostgreSQL simples deve ser suficiente inicialmente.

---



# 77. Future scalability

Se o projeto crescer enormemente:

```text
Postgres
```

pode manter:

```text
instrument master
latest quotes
metadata
```

e histórico completo migrar futuramente para:

```text
ClickHouse
or
lakehouse
```

Não implementar isso agora.

---



# 78. Public database

Apesar dos dados serem públicos:

NÃO expor conexão PostgreSQL diretamente para usuários externos.

Consultas públicas devem ocorrer via:

```text
API
```

ou:

```text
Parquet datasets
```

Isso reduz superfície de ataque e protege infraestrutura.

---



# 79. GitHub Pages

Documentação será publicada em:

```text
GitHub Pages
```

Preferencialmente com:

```text
MkDocs Material
```

ou solução equivalente open-source.

A documentação deve poder ser construída automaticamente pelo GitHub Actions.

---



# 80. Site de documentação

Idealmente conter:

```text
Home
Getting Started
API
Datasets
Data Sources
Price Semantics
Providers
Architecture
Contributing
FAQ
```

---



# 81. Portfolio

O projeto futuramente será adicionado ao meu portfólio pessoal hospedado via GitHub Pages.

Por isso:

- README precisa ser visualmente bom;
- arquitetura precisa estar clara;
- ter screenshots ou diagramas futuramente;
- badges devem ser úteis, não excessivos;
- mostrar dados reais;
- documentação precisa transmitir qualidade profissional.

Não transformar README em marketing vazio.

---



# 82. README

README inicial deve conter:

```text
What is this?
Why does it exist?
Features
Architecture
Available sources
Quickstart
API example
Dataset example
Local setup
Contributing
License
Data licensing
Roadmap
```

Adicionar exemplos reais assim que Providers funcionarem.

---



# 83. Contribuições

O projeto deve ser pensado para receber contribuições.

Criar:

```text
CONTRIBUTING.md
CODE_OF_CONDUCT.md
SECURITY.md
CHANGELOG.md
DATA_LICENSES.md
```

E:

```text
.github/
    ISSUE_TEMPLATE/
    PULL_REQUEST_TEMPLATE.md
```

---



# 84. [CONTRIBUTING.md](http://CONTRIBUTING.md)

Explicar:

```text
development setup
uv commands
tests
lint
typing
database migrations
adding provider
adding source
adding dataset
documentation
PR process
```

---



# 85. Adding a Provider

Criar documentação específica:

```text
docs/contributing/adding-a-provider.md
```

Passos aproximados:

```text
1. Create Provider
2. Define source metadata
3. Implement fetch
4. Implement parse
5. Normalize
6. Add fixtures
7. Add tests
8. Document licensing
9. Add provider docs
10. Add ingestion workflow if needed
```

Isso facilitará contribuições externas.

---



# 86. Provider plugin design

Evitar arquitetura de plugins excessivamente sofisticada.

Mas Providers devem ser registráveis em um registry.

Exemplo:

```python
provider_registry.register(B3Provider())
```

ou mecanismo equivalente.

Adicionar novo Provider não deve exigir alterar dezenas de `if/elif`.

---



# 87. CI

Criar CI no GitHub Actions executando:

```text
uv sync
ruff check
ruff format --check
type checking
pytest
```

Se possível:

```text
coverage report
```

Não exigir acesso à internet para unit tests.

---



# 88. Testes

Ter:

```text
unit
integration
contract
```

Unit tests devem usar fixtures.

Integration tests podem acessar fontes reais e devem estar marcados:

```python
@pytest.mark.integration
```

Não executá-los obrigatoriamente em todos os commits se isso puder abusar das fontes.

---



# 89. Provider contract tests

Todos Providers devem passar conjunto mínimo:

```text
valid provider metadata
valid RawArtifact
valid normalized model
invalid data handling
idempotency
```

---



# 90. Fixtures

Guardar pequenos samples reais de:

```text
B3 equities
B3 derivatives
CVM informe diário
Tesouro
BCB
Yahoo
```

Respeitar redistribuição/licença inclusive para fixtures.

Quando necessário, criar fixture sintética estruturalmente equivalente.

---



# 91. Security

Nunca commitar:

```text
DATABASE_URL
R2 credentials
Railway credentials
Neon credentials
Cloudflare tokens
```

Criar:

```text
.env.example
```

Utilizar GitHub Secrets.

---



# 92. Public repository security

Adicionar:

```text
Dependabot
```

quando apropriado.

Avaliar:

```text
GitHub secret scanning
CodeQL
```

sem criar complexidade desnecessária.

---



# 93. API SQL safety

API nunca deve receber SQL arbitrário.

Não criar endpoint:

```text
/query?sql=...
```

Consultas públicas devem passar por endpoints controlados.

---



# 94. API pagination

Não permitir endpoint devolver milhões de rows inadvertidamente.

Implementar:

```text
default limit
max limit
cursor pagination
```

quando necessário.

Bulk data deve ser obtido por Parquet.

---



# 95. API vs Bulk Data

Regra:

```text
small queries → API

large historical datasets → Parquet
```

Documentar essa recomendação.

---



# 96. Dataset versioning

Criar:

```text
schema_version
dataset_version
```

Alterações breaking precisam ser documentadas.

API terá versionamento próprio:

```text
/v1
```

---



# 97. Semantic Versioning

Utilizar:

```text
SemVer
```

para releases do software.

Exemplo:

```text
0.1.0
0.2.0
1.0.0
```

Antes de 1.0 APIs podem evoluir, mas breaking changes devem ser documentadas.

---



# 98. Release automation

Não precisa automatizar publicação em PyPI imediatamente.

Mas estruturar projeto como pacote Python apropriado.

Futuramente poderemos publicar:

```text
pip install open-market-data
```

Não fazer isso antes de API Python estar minimamente estável.

---



# 99. Public API deployment

Pipeline conceitual:

```text
push main
    ↓
GitHub CI
    ↓
tests
    ↓
Railway deploy
```

Migrations precisam ser seguras.

Não executar migrations destrutivas automaticamente sem proteção.

---



# 100. Cloudflare

Preparar custom domains conceituais:

```text
api.<domain>
data.<domain>
```

O domínio definitivo ainda não precisa ser definido.

Configuração deve ser documentada, não hardcoded.

---



# 101. R2 publication

Dataset Publisher deve:

1. gerar Parquet;
2. validar schema;
3. contar rows;
4. calcular SHA256;
5. subir arquivo;
6. publicar manifest;
7. somente então marcar dataset como publicado.

Evitar datasets parcialmente publicados.

---



# 102. Atomic publication

Idealmente:

```text
upload versioned file
        ↓
validation
        ↓
update latest manifest
```

Assim `latest` sempre aponta para versão completa.

---



# 103. Public data restrictions

Pipeline de publicação deve verificar:

```text
source.redistribution_policy
```

antes de gerar dataset público.

Exemplo:

```python
if source.redistribution_policy not in ALLOWED_PUBLIC_POLICIES:
    raise RedistributionNotAllowed(...)
```

Não depender do desenvolvedor lembrar manualmente.

---



# 104. Architecture documents

Criar:

```text
docs/ARCHITECTURE.md
docs/DATA_SOURCES.md
docs/PRICE_SEMANTICS.md
docs/OPEN_SOURCE_REVIEW.md
docs/DATA_MODEL.md
docs/API.md
docs/DATASETS.md
docs/DEPLOYMENT.md
docs/LICENSING.md
docs/ROADMAP.md
```

---



# 105. ADRs

Criar:

```text
docs/adr/
```

Inicialmente documentar decisões como:

```text
ADR-001 PostgreSQL as serving database
ADR-002 Neon as initial managed Postgres
ADR-003 Cloudflare R2 for object storage
ADR-004 FastAPI for public API
ADR-005 Railway for API hosting
ADR-006 GitHub Actions for ingestion
ADR-007 Parquet for bulk datasets
ADR-008 Apache-2.0 for source code
```

Cada ADR deve explicar:

```text
Context
Decision
Alternatives
Consequences
```

---



# 106. Supabase / Vercel decision

Documentar explicitamente que foram considerados.

Supabase não será usado inicialmente porque:

- Auth não é necessário;
- Realtime não é necessário;
- PostgREST automático não substitui nossa API de domínio;
- queremos provider-independent backend;
- Neon possui bom modelo para workload serverless PostgreSQL.

Vercel não será usado para FastAPI porque:

- projeto é backend Python/data-heavy;
- Railway fornece runtime mais natural;
- Vercel permanece excelente opção para frontend Next.js futuro.

Não tratar essas decisões como irreversíveis.

---



# 107. Suggested project structure

Estrutura inicial sugerida:

```text
open-market-data/
│
├── pyproject.toml
├── uv.lock
├── README.md
├── LICENSE
├── DATA_LICENSES.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── CHANGELOG.md
├── AGENTS.md
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
│
├── config/
│   ├── sources.yaml
│   └── instruments.example.csv
│
├── docs/
│   ├── index.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── DATA_SOURCES.md
│   ├── PRICE_SEMANTICS.md
│   ├── DATASETS.md
│   ├── API.md
│   ├── LICENSING.md
│   ├── OPEN_SOURCE_REVIEW.md
│   ├── DEPLOYMENT.md
│   ├── ROADMAP.md
│   │
│   ├── providers/
│   │   ├── cvm.md
│   │   ├── b3.md
│   │   ├── tesouro.md
│   │   ├── bcb.md
│   │   └── yahoo.md
│   │
│   ├── contributing/
│   │   └── adding-a-provider.md
│   │
│   └── adr/
│
├── migrations/
│
├── src/
│   └── marketdata/
│       │
│       ├── __init__.py
│       ├── config.py
│       │
│       ├── domain/
│       │   ├── instrument.py
│       │   ├── quote.py
│       │   ├── source.py
│       │   ├── artifact.py
│       │   ├── enums.py
│       │   └── errors.py
│       │
│       ├── providers/
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── cvm.py
│       │   ├── b3.py
│       │   ├── tesouro.py
│       │   ├── bcb.py
│       │   ├── yahoo.py
│       │   └── anbima.py
│       │
│       ├── ingestion/
│       │   ├── pipeline.py
│       │   ├── downloader.py
│       │   ├── raw_store.py
│       │   └── runs.py
│       │
│       ├── normalization/
│       │
│       ├── quality/
│       │
│       ├── storage/
│       │   ├── database.py
│       │   ├── repositories.py
│       │   └── object_store.py
│       │
│       ├── datasets/
│       │   ├── parquet.py
│       │   ├── manifest.py
│       │   └── publisher.py
│       │
│       ├── coverage/
│       │
│       ├── api/
│       │   ├── main.py
│       │   ├── dependencies.py
│       │   ├── schemas.py
│       │   └── routes/
│       │
│       └── cli/
│
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── contract/
│   └── integration/
│
└── .github/
    ├── workflows/
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

Adapte se encontrar estrutura mais simples e coerente.

---



# 108. MVP order

Executar em fases.

## Phase 0 — Discovery

Antes de código relevante:

- analisar projetos open-source;
- validar fontes oficiais;
- revisar licenças;
- escrever arquitetura;
- escrever ADRs;
- definir schemas.



## Phase 1 — Foundation

Criar:

- package Python;
- configuration;
- domain models;
- PostgreSQL;
- migrations;
- Provider interface;
- raw artifact abstraction;
- R2 abstraction;
- ingestion runs;
- CLI;
- tests;
- CI.



## Phase 2 — CVM

Primeiro Provider completo.

Conseguir:

```text
fund → date → NAV
```

fim a fim:

```text
CVM
→ raw
→ normalized
→ Postgres
→ API
```



## Phase 3 — Tesouro

Implementar títulos públicos.

## Phase 4 — BCB

Implementar PTAX/Selic/CDI.

## Phase 5 — B3 Equities

Implementar ações, BDRs, ETFs, FIIs e opções.

## Phase 6 — B3 Derivatives

Settlement de DI/DOL/IND etc.

## Phase 7 — Yahoo

Somente para POC/local inicialmente.

## Phase 8 — Credit

Debêntures, CRIs e CRAs.

## Phase 9 — Public datasets

Publicar Parquet apenas das fontes legalmente redistribuíveis.

## Phase 10 — Public API

Expor dados autorizados.

## Phase 11 — Coverage Report

Rodar universo heterogêneo.

---



# 109. Não antecipar frontend

NÃO criar Next.js agora.

Somente após:

```text
Providers working
API working
datasets working
```

poderemos criar Data Explorer.

---



# 110. Success criteria MVP

Considerar MVP funcional quando:

1. repo público puder ser clonado;
2. `uv sync` funcionar;
3. PostgreSQL puder ser configurado;
4. migrations funcionarem;
5. CVM funcionar end-to-end;
6. Tesouro funcionar end-to-end;
7. BCB funcionar end-to-end;
8. B3 equities funcionar;
9. B3 derivatives funcionar;
10. Yahoo funcionar localmente;
11. raw artifacts forem preservados;
12. quotes forem normalizados;
13. API pública funcionar;
14. API OpenAPI existir;
15. Parquet puder ser gerado;
16. public datasets respeitarem licensing policy;
17. coverage report funcionar;
18. pipeline for idempotent;
19. lineage for auditável;
20. CI estiver verde;
21. documentação estiver publicada;
22. novo contribuidor conseguir executar localmente seguindo README.

---



# 111. Qualidade de engenharia

Priorizar:

```text
boring technology
explicit code
strong typing
small functions
clear boundaries
tests
good naming
documentation
```

Evitar:

```text
massive base classes
magic
deep inheritance
unnecessary dependency injection frameworks
microservices
Kafka
Airflow
Kubernetes
Celery
Redis
```

a menos que exista necessidade comprovada.

---



# 112. Custo operacional

Objetivo:

```text
≈ zero cost initially
```

Utilizando:

```text
GitHub Actions
Neon Free
Cloudflare R2 Free
Railway Free/low-cost
Cloudflare Free
GitHub Pages
```

Infraestrutura deve permitir crescimento gradual.

Não adicionar serviços pagos sem justificar.

---



# 113. Self-hosting

Como projeto open-source, qualquer usuário deve conseguir self-host.

Adicionar documentação futura:

```text
docs/SELF_HOSTING.md
```

Self-hosting não deve exigir:

```text
Neon
Railway
Cloudflare
```

Esses são apenas providers de infraestrutura escolhidos para nossa instância oficial.

O software deve funcionar com:

```text
PostgreSQL
S3-compatible object storage
Docker-capable host
```

---



# 114. Configuração cloud-neutral

Criar abstrações e environment variables:

```text
DATABASE_URL
OBJECT_STORAGE_ENDPOINT
OBJECT_STORAGE_BUCKET
OBJECT_STORAGE_ACCESS_KEY
OBJECT_STORAGE_SECRET_KEY
OBJECT_STORAGE_REGION
```

Não utilizar chamadas específicas de R2 fora do adapter de object storage.

---



# 115. Environment configuration

Usar Pydantic Settings ou alternativa simples.

Diferenciar:

```text
development
test
production
```

Nunca definir production credentials em arquivo.

---



# 116. Data provenance public API

Quando apropriado, API deve retornar:

```text
source
official
reference_date
retrieved_at
price_type
```

Isso diferencia o projeto de APIs financeiras opacas.

---



# 117. API philosophy

Objetivo da API:

> usuários pedem informação financeira canônica, não detalhes internos do fornecedor.

Por exemplo:

```text
GET /v1/quotes/PETR4/latest
```

não:

```text
GET /v1/b3/BVBG186/PETR4
```

Endpoints source-specific podem existir futuramente para debug.

---



# 118. Public tables concept

As "tabelas públicas" serão representadas por:

```text
API resources
+
Parquet datasets
```

Não por acesso SQL direto.

Principais datasets públicos desejados:

```text
instruments
quotes
fund_nav
rates
sources
```

quando permitido pelas respectivas licenças.

---



# 119. API source filtering

Permitir:

```text
?source=B3
```

e:

```text
?price_type=OFFICIAL_SETTLEMENT
```

mas também oferecer default inteligente.

---



# 120. Canonical quote selection

Não implementar escolha complexa silenciosamente.

Se houver múltiplas fontes:

```text
B3 CLOSE
Yahoo CLOSE
```

API deve poder retornar ambas.

Futuramente poderemos criar:

```text
canonical_quote
```

com uma política explícita de prioridade.

Não implementar heurística obscura.

---



# 121. Instrument mapping

Mapping será um dos maiores problemas do projeto.

Criar domínio adequado desde o começo.

Nunca depender apenas de string matching pelo nome.

Utilizar quando possível:

```text
ISIN
CNPJ
exchange ID
ticker + venue
maturity
```

Registrar mappings manuais explicitamente.

---



# 122. Staleness

Não retornar preço velho como se fosse atual.

Quote deve possuir:

```text
reference_date
```

e a API deve permitir verificar:

```text
staleness_days
```

---



# 123. Calendar awareness

Usar calendário de mercado quando possível.

Não marcar ausência em sábado/domingo como erro.

PYield pode ajudar no calendário brasileiro.

---



# 124. Documentation language

Código, nomes de classes e API:

```text
English
```

Documentação principal preferencialmente:

```text
English
```

para maximizar participação internacional.

Podemos adicionar versão em português futuramente.

Comentários de código devem ser em inglês.

---



# 125. Naming conventions

Evitar abreviações pouco claras.

Preferir:

```text
reference_date
```

a:

```text
dt_ref
```

na API e domínio público.

Internamente manter naming consistente.

---



# 126. Database naming

Preferir nomes em inglês.

Isso é um projeto público, independente de sistemas internos existentes.

---



# 127. API datetime

Utilizar ISO-8601.

Datas:

```text
YYYY-MM-DD
```

Timestamps:

```text
UTC
```

com timezone explícita.

Reference date deve ser date, não datetime.

---



# 128. Money precision

Nunca armazenar:

```text
REAL/FLOAT
```

para preços.

Usar:

```text
NUMERIC
```

com precisão definida conscientemente.

---



# 129. Performance targets

MVP não precisa performance extrema.

Meta razoável para endpoints simples:

```text
p95 < 500ms
```

sem cache, quando banco está ativo.

Com cache, melhor.

Não fazer otimizações prematuras.

---



# 130. Documentation examples

Após Providers reais funcionarem, adicionar exemplos:

```python
import httpx

response = httpx.get(
    "https://api.example.com/v1/quotes/PETR4/latest"
)

print(response.json())
```

e:

```python
import polars as pl

df = pl.read_parquet(...)
```

---



# 131. Future roadmap

Registrar mas NÃO implementar agora:

```text
licensed global equity provider
global futures
US Treasury individual securities
corporate bonds
FINRA TRACE
Euronext
ICE
CME
fundamental data
corporate actions
data explorer
API keys
usage dashboard
webhooks
Python SDK
R SDK
MCP server
```

---



# 132. Potential future MCP integration

Como projeto de dados públicos, futuramente pode ser interessante expor:

```text
MCP server
```

para agentes de IA consultarem market data.

Apenas registrar no roadmap.

Não implementar agora.

---



# 133. Agent behavior

Trabalhe autonomamente.

Não interrompa pedindo confirmação para decisões pequenas.

Quando encontrar duas boas opções:

1. pesquise;
2. compare;
3. escolha;
4. documente em ADR;
5. continue.

Pergunte somente se a decisão for realmente impossível de inferir e bloquear o projeto.

---



# 134. Do not fake completion

Não considerar Provider funcional se:

- usa mocks;
- endpoint real não foi testado;
- parser funciona apenas com fixture;
- dado normalizado não chegou ao banco;
- API não consegue consultá-lo.

Mocks são testes.

Não são prova de funcionamento.

---



# 135. Validate with real data

Para cada Provider finalizado:

1. executar endpoint real;
2. preservar artifact;
3. parsear;
4. normalizar;
5. persistir;
6. consultar no PostgreSQL;
7. consultar através da API;
8. executar novamente para provar idempotência.

Documentar exemplo real.

---



# 136. Licensing before publishing

Um Provider pode ser considerado:

```text
INGESTION READY
```

antes de ser:

```text
PUBLICATION READY
```

Separar esses status.

Exemplo:

```text
Yahoo:
ingestion = enabled
public_api = disabled
public_dataset = disabled
```

até resolver licensing.

---



# 137. Provider capability metadata

Considerar configuração:

```text
provider:
  ingestion_enabled: true
  public_api_enabled: true
  public_dataset_enabled: true
```

dependendo de licensing.

---



# 138. Initial official-source priorities

Priorizar desenvolvimento:

```text
CVM
Tesouro
BCB
B3
```

porque são os datasets mais importantes para demonstrar valor público e possuem melhor perspectiva de uso oficial.

Yahoo é complemento.

---



# 139. First agent deliverable

Antes de implementar Providers completos, quero que o primeiro ciclo produza:

```text
1. repository scaffold
2. OPEN_SOURCE_REVIEW.md
3. DATA_SOURCES.md
4. LICENSING.md
5. DATA_LICENSES.md
6. ARCHITECTURE.md
7. DATA_MODEL.md
8. ADRs iniciais
9. pyproject.toml
10. CI
11. domain models
12. Provider interface
13. database schema proposal
14. initial migrations
15. minimal FastAPI skeleton
16. CLI skeleton
```

Somente depois começar o primeiro Provider.

---



# 140. First functional Provider

O primeiro Provider deve ser:

```text
CVM Fund NAV
```

Porque:

- fonte oficial;
- dado estruturado;
- caso de uso claro;
- bom teste para pipeline inteiro.

Objetivo:

```text
CVM
→ Raw Artifact
→ R2/local object store
→ Parse
→ Normalize
→ PostgreSQL
→ FastAPI
→ JSON
```

---



# 141. Definition of done for CVM

Precisamos conseguir:

```text
GET /v1/funds/{cnpj}/quotes
```

e retornar cotas reais.

Também:

```bash
marketdata explain <fund> --date ...
```

deve apontar para artifact original.

---



# 142. Continue autonomously

Após CVM funcionar, não pare.

Continue na sequência:

```text
Tesouro
BCB
B3 equities
B3 derivatives
Yahoo
coverage
public Parquet
```

A cada fase:

```text
tests
lint
typing
docs
```

antes de avançar.

---



# 143. Final objective

O projeto deve evoluir para uma plataforma em que qualquer pessoa possa fazer:

```text
GET /v1/quotes/PETR4/latest
```

ou baixar:

```text
B3 historical quotes in Parquet
```

e sempre saber:

```text
where the data came from
what the price means
when it was published
whether it is official
whether it can be redistributed
```

A principal vantagem competitiva do projeto não deve ser simplesmente "mais uma API de cotação".

Deve ser:

> uma camada open-source, transparente, auditável e extensível sobre dados financeiros públicos.

Construa a fundação pensando nisso.