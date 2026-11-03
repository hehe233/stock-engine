import { request } from './http';
import type { ResearchJob, AnalysisMode } from './types';

export const jobsApi = {
  createJob: (
    symbol: string,
    snapshotId: string,
    mode: AnalysisMode,
    modelName?: string,
    includePortfolio = false,
  ) =>
    request<ResearchJob>('/jobs', {
      method: 'POST',
      body: JSON.stringify({
        symbol,
        snapshot_id: snapshotId,
        mode,
        model_name: modelName,
        include_portfolio: includePortfolio,
      }),
    }),
  jobs: () => request<{ items: ResearchJob[] }>('/jobs'),
  job: (id: string) => request<ResearchJob>(`/jobs/${encodeURIComponent(id)}`),
  cancelJob: (id: string) =>
    request<ResearchJob>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  retryJob: (id: string) =>
    request<ResearchJob>(`/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
};
