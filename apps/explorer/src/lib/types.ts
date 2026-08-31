export type InstrumentSearchItem = {
  instrument_id: string;
  name: string;
  asset_class: string;
  identifiers: string[];
  sources?: string[];
  first_quote_date?: string | null;
  last_quote_date?: string | null;
  quote_count?: number | null;
};

export type InstrumentsResponse = {
  instruments: InstrumentSearchItem[];
  next_cursor?: string | null;
};

export type QuoteResponse = {
  date: string;
  price: string;
  currency: string | null;
  price_type: string;
  source: string;
  official: boolean;
  revision: number;
  retrieved_at: string | null;
  raw_artifact_sha256: string | null;
  unit: string | null;
};

export type QuotesResponse = {
  instrument_id: string;
  identifier: string;
  quotes: QuoteResponse[];
  next_cursor: string | null;
  first_quote_date?: string | null;
  last_quote_date?: string | null;
  quote_count?: number | null;
};

export type SeriesObservationResponse = {
  series: string;
  date: string;
  value: string;
  unit: string;
  source: string;
  revision: number;
};

export type SeriesHistoryResponse = {
  series: string;
  unit: string;
  observations: SeriesObservationResponse[];
  next_cursor: string | null;
};

export type FundQuotesResponse = {
  instrument_id: string;
  identifier: string;
  quotes: QuoteResponse[];
  next_cursor: string | null;
};

export type SourceResponse = {
  name: string;
  display_name: string;
  official: boolean;
  redistribution_policy: string;
  ingestion_enabled: boolean;
  public_api_enabled: boolean;
  public_dataset_enabled: boolean;
  data_license: string | null;
};

export type DatasetListing = {
  dataset_name: string;
  schema_version: string;
  snapshot_date: string;
  generated_at: string;
  sources: string[];
  reference_period: { start: string | null; end: string | null };
  row_count: number;
  object_key: string;
  sha256: string;
  license: string;
  redistribution_policy: string;
  attribution: string[];
  url: string | null;
};

export type CoverageItemResponse = {
  instrument: string;
  asset_class: string;
  provider: string | null;
  reference_date: string;
  price: string | null;
  price_type: string | null;
  status: string;
  staleness: number | null;
  missing_reason: string | null;
};

export type CoverageResponse = {
  date: string;
  universe: string;
  mode: string;
  universe_size: number;
  priced: number;
  priced_pct: string;
  missing_reason_counts: Record<string, number>;
  results: CoverageItemResponse[];
  next_cursor: number | null;
};

export type HistoryQuery = {
  start?: string;
  end?: string;
  limit?: number;
  cursor?: string;
  price_type?: string;
  source?: string;
};

export type HealthResponse = {
  status: string;
};

export type CoverageUniverse = "scratch" | "example" | "operator";

export type CoverageQuery = {
  date: string;
  universe?: CoverageUniverse;
  limit?: number;
  cursor?: number;
};

export type CoverageSpanItem = {
  ticker: string;
  instrument_id: string | null;
  source: string | null;
  min_date: string | null;
  max_date: string | null;
  quote_count: number;
};

export type CoverageSpanResponse = {
  universe: string;
  universe_size: number;
  instruments_with_quotes: number;
  min_date: string | null;
  max_date: string | null;
  quote_count: number;
  source?: string | null;
  results: CoverageSpanItem[];
};

export type CoverageSpanQuery = {
  universe?: CoverageUniverse;
  source?: string;
};
