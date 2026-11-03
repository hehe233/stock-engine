import { request } from './http';

export interface DatasetAudit {
  level2?: boolean;
  snapshot_ids?: string[];
  rows: number;
  symbol_count: number;
  days: number;
  first: string;
  last: string;
  adjustment: 'raw' | 'qfq';
  selection: 'manual' | 'historical_universe';
  executable_rows: number;
  missing_available_at: number;
  coverage_verified: boolean;
  warnings: string[];
  symbols: {
    symbol: string;
    rows: number;
    first: string;
    last: string;
    listed_on: string | null;
    delisted_on: string | null;
  }[];
}
export interface QuantDataset {
  id: string;
  name: string;
  source: string;
  checksum: string;
  is_demo: boolean;
  created_at: string;
  details: DatasetAudit;
}
export interface DatasetInput {
  name: string;
  source: string;
  adjustment: 'raw' | 'qfq';
  selection: 'manual' | 'historical_universe';
  content: string;
}
export interface ExperimentInput {
  horizon?: 5;
  event_return?: 0.2;
  seed?: number;
  dataset_id: string;
  train_days: number;
  calibration_days: number;
  test_days: number;
  folds: number;
  probability_threshold: number;
  initial_cash: number;
  max_positions: number;
  commission_bps: number;
  slippage_bps: number;
  participation: number;
}
export interface Metrics {
  count: number;
  positives: number;
  event_rate: number;
  brier: number;
  log_loss: number;
  auc: number | null;
  ece: number;
  bins: { lower: number; upper: number; count: number; predicted: number; observed: number }[];
}
export interface QuantFold {
  fold: number;
  train_start: string;
  train_end: string;
  train_label_end: string;
  calibration_start: string;
  calibration_end: string;
  calibration_label_end: string;
  test_start: string;
  test_end: string;
  train_count: number;
  calibration_count: number;
  metrics: Metrics;
  raw_metrics: Metrics;
}
export interface QuantTrade {
  symbol: string;
  signal_date: string;
  buy_date: string;
  sell_date: string;
  quantity: number;
  buy_price: number;
  sell_price: number;
  gross_pnl: number;
  fees: number;
  net_pnl: number;
}
export interface Backtest {
  enabled: boolean;
  reason?: string;
  curve?: { date: string; equity: number; cash: number; stale: boolean }[];
  trades?: QuantTrade[];
  rejected?: Record<string, number>;
  open_positions?: { symbol: string; quantity: number; buy_date: string }[];
  attribution?: {
    symbol: string;
    trades: number;
    gross_pnl: number;
    fees: number;
    net_pnl: number;
  }[];
  valuation_complete?: boolean;
  trade_count?: number;
  ending_cash?: number;
  return_pct?: number | null;
  max_drawdown_pct?: number | null;
  fees?: number;
  warnings?: string[];
}
export interface QuantResult {
  artifacts?: Record<string, string>;
  evaluation_end?: string;
  research_only?: boolean;
  stage?: string;
  target?: string;
  metrics?: Metrics;
  raw_metrics?: Metrics;
  baseline_metrics?: Metrics;
  folds?: QuantFold[];
  skipped_folds?: { fold: number; reason: string }[];
  requested_folds?: number;
  monthly_errors?: ({ month: string } & Metrics)[];
  importance?: Record<string, number>;
  backtest?: Backtest;
  dataset_checksum?: string;
  code_sha256?: string;
  engine_version?: string;
  feature_version?: string;
  dependencies?: Record<string, string>;
  warnings?: string[];
  usable_samples?: number;
  excluded_rows?: number;
}
export interface QuantRun {
  id: string;
  dataset_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  params: Required<ExperimentInput>;
  result: QuantResult;
  error: string | null;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  cancel_requested: boolean;
}
export interface Prediction {
  baseline_probability?: number;
  symbol: string;
  date: string;
  label_end: string;
  label: number;
  future_return: number;
  probability: number;
  raw_probability: number;
  fold: number;
}
const post = <T>(path: string, payload: unknown = {}) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(payload) });
export const quantApi = {
  datasets: () => request<{ items: QuantDataset[] }>('/quant/datasets'),
  preview: (payload: DatasetInput) => post<DatasetAudit>('/quant/datasets/preview', payload),
  import: (payload: DatasetInput) => post<QuantDataset>('/quant/datasets', payload),
  history: () => post<QuantDataset>('/quant/datasets/history'),
  demo: () => post<QuantDataset>('/quant/datasets/demo'),
  runs: () => request<{ items: QuantRun[] }>('/quant/runs'),
  create: (payload: ExperimentInput) => post<QuantRun>('/quant/runs', payload),
  run: (id: string) => request<QuantRun>(`/quant/runs/${encodeURIComponent(id)}`),
  cancel: (id: string) => post<QuantRun>(`/quant/runs/${encodeURIComponent(id)}/cancel`),
  predictions: (id: string, page: number) =>
    request<{ total: number; items: Prediction[] }>(
      `/quant/runs/${encodeURIComponent(id)}/predictions?page=${page}`,
    ),
};
