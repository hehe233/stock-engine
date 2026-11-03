import { request } from './http';

export type ResearchKind = 'ladder' | 'dragon' | 'seats' | 'flow' | 'notices' | 'history';
export interface ResearchQuery {
  kind: ResearchKind;
  date: string;
  symbol?: string;
  case_id?: string;
}
export interface ResearchRow {
  id: string;
  symbol?: string;
  name?: string;
  date?: string;
  close?: number;
  boards?: number | null;
  sector?: string;
  seal_yuan?: number | null;
  amount_yuan?: number | null;
  break_count?: number | null;
  first_seal?: string;
  last_seal?: string;
  buy_yuan?: number | null;
  sell_yuan?: number | null;
  net_yuan?: number | null;
  reason?: string;
  seat?: string;
  side?: string;
  main_yuan?: number | null;
  main_pct?: number | null;
  super_yuan?: number | null;
  change_since_previous_yuan?: number | null;
  large_yuan?: number | null;
  medium_yuan?: number | null;
  small_yuan?: number | null;
  title?: string;
  category?: string;
  url?: string | null;
}
export interface DataRequest {
  id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  error: string | null;
  snapshot_id: string | null;
  updated_at: string;
}
export interface ResearchSnapshot {
  id: string;
  kind: ResearchKind;
  source: string;
  is_demo: boolean;
  query_date: string;
  data_date: string | null;
  observed_at: string;
  total: number;
  rows: ResearchRow[];
  stale: boolean;
  details: {
    warnings: string[];
    rejected_count: number;
    coverage_verified: boolean;
    published_at?: string | null;
  };
}
export interface Dataset {
  page: number;
  page_size: number;
  snapshot: ResearchSnapshot | null;
  request: DataRequest | null;
  total: number;
  summary: {
    tiers?: { boards: number; count: number }[];
    sectors?: {
      sector: string;
      count: number;
      max_boards: number;
      previous_count: number | null;
      count_change: number | null;
    }[];
    leaders?: string[];
    comparison_date?: string | null;
    previous_observed_at?: string | null;
  };
}
export interface WindowStats {
  start: string;
  end: string;
  return_pct: number;
  drawdown_pct: number;
}
export interface HistoryCase {
  id: string;
  year: number;
  symbol: string;
  name: string;
  selection: string;
  start: string;
  end: string;
  request: DataRequest | null;
  snapshot: ResearchSnapshot | null;
  statistics: {
    bars: number;
    window_count: number;
    positive_count: number;
    negative_count: number;
    strong: WindowStats | null;
    failure: WindowStats | null;
    first_date: string | null;
    last_date: string | null;
  } | null;
}
export const shanghaiToday = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
const post = <T>(path: string, payload: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(payload) });
export const researchApi = {
  data: (query: ResearchQuery, search = '', page = 1) =>
    request<Dataset>(
      '/research/data?' +
        new URLSearchParams({
          ...query,
          search,
          page: String(page),
          page_size: '50',
        }),
    ),
  refresh: (query: ResearchQuery) => post<DataRequest>('/research/refresh', query),
  history: () => request<{ items: HistoryCase[]; warnings: string[] }>('/research/history'),
};
