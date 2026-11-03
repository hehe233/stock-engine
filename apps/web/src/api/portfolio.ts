import { request } from './http';
export interface PositionInput {
  symbol: string;
  name: string;
  asset_type: 'stock' | 'etf';
  quantity: number;
  cost_price: string;
  acquired_on: string;
  settlement: 'T0' | 'T1' | 'unknown';
  note: string;
}
export interface Position extends PositionInput {
  updated_at: string;
  id: string;
  price: number | null;
  value_yuan: number | null;
  cost_yuan: number;
  pnl_yuan: number | null;
  pnl_pct: number | null;
  sellable: number | null;
  conditions: string[];
  quote_snapshot_id: string | null;
  quote_time: string | null;
  fetched_at: string | null;
  weight_pct: number | null;
}
export interface Portfolio {
  items: Position[];
  is_demo: boolean;
  as_of: string;
  unknown_price_count: number;
  cost_yuan: number;
  known_value_yuan: number;
  pnl_yuan: number | null;
  session: {
    code: 'unknown' | 'closed' | 'auction' | 'trading' | 'break';
    label: string;
    calendar_verified: boolean;
  };
  warnings: string[];
}
export interface ImportPreview {
  rows: PositionInput[];
  errors: { line: number; message: string }[];
  valid: boolean;
  count: number;
}

const post = <T>(path: string, payload: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(payload) });
export const portfolioApi = {
  portfolio: () => request<Portfolio>('/portfolio'),
  preview: (content: string) => post<ImportPreview>('/portfolio/preview', { content }),
  import: (rows: PositionInput[]) =>
    post<{ inserted: number; skipped: number }>('/portfolio/import', { rows }),
  update: (id: string, row: PositionInput) =>
    post<{ updated: boolean }>(`/portfolio/${id}/update`, row),
  remove: (id: string) => post<{ deleted: boolean }>(`/portfolio/${id}/delete`, {}),
};
