import { request } from './http';
import type { AnalysisList, AnalysisReport } from './types';

export const reportsApi = {
  analyze: (symbol: string, snapshotId: string) =>
    request<AnalysisReport>('/analyses', {
      method: 'POST',
      body: JSON.stringify({ symbol, snapshot_id: snapshotId }),
    }),
  analyses: (page: number) => request<AnalysisList>(`/analyses?limit=10&offset=${(page - 1) * 10}`),
  analysis: (id: string) => request<AnalysisReport>(`/analyses/${encodeURIComponent(id)}`),
};
