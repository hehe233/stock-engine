import type {
  AnalysisList,
  AnalysisReport,
  MarketResponse,
  AppConfig,
  MarketStatus,
  ResearchJob,
  AnalysisMode,
  ModelSettings,
  ModelSettingsInput,
  ModelProfile,
  ModelProfileInput,
  ModelProfileList,
} from './types';

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    // 定时刷新或分析卡住时，页面应进入错误状态，不能无限 loading。
    signal: options?.signal ?? AbortSignal.timeout(30_000),
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null;
    throw new Error(typeof detail === 'string' ? detail : `请求失败（${response.status}）`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  modelProfiles: () => request<ModelProfileList>('/settings/models/profiles'),
  saveModelProfile: (values: ModelProfileInput, id?: string) =>
    request<ModelProfile>(
      id
        ? `/settings/models/profiles/${encodeURIComponent(id)}/update`
        : '/settings/models/profiles',
      { method: 'POST', body: JSON.stringify(values) },
    ),
  testModelProfile: (values: ModelProfileInput, id?: string) =>
    request<{ ok: boolean; message: string }>(
      id
        ? `/settings/models/profiles/${encodeURIComponent(id)}/test`
        : '/settings/models/profiles/test',
      { method: 'POST', body: JSON.stringify(values) },
    ),
  activateModelProfile: (profile: ModelProfile) =>
    request<ModelProfile>(`/settings/models/profiles/${encodeURIComponent(profile.id)}/activate`, {
      method: 'POST',
      body: JSON.stringify({ revision: profile.revision }),
    }),
  deleteModelProfile: (profile: ModelProfile) =>
    request<{ deleted: boolean }>(
      `/settings/models/profiles/${encodeURIComponent(profile.id)}/delete`,
      { method: 'POST', body: JSON.stringify({ revision: profile.revision }) },
    ),
  modelSettings: () => request<ModelSettings>('/settings/models'),
  saveModelSettings: (values: ModelSettingsInput) =>
    request<ModelSettings>('/settings/models', {
      method: 'POST',
      body: JSON.stringify(values),
    }),
  testModelSettings: (values: ModelSettingsInput) =>
    request<{ ok: boolean; message: string }>('/settings/models/test', {
      method: 'POST',
      body: JSON.stringify(values),
    }),
  config: () => request<AppConfig>('/config'),
  marketStatus: () => request<MarketStatus>('/market/status'),
  quotes: (params: URLSearchParams = new URLSearchParams()) =>
    request<MarketResponse>(`/market/quotes?${params}`),
  refresh: () =>
    request<{ accepted: boolean; message: string }>('/market/refresh', { method: 'POST' }),
  analyze: (symbol: string, snapshotId: string) =>
    request<AnalysisReport>('/analyses', {
      method: 'POST',
      body: JSON.stringify({ symbol, snapshot_id: snapshotId }),
    }),
  analyses: (page: number) => request<AnalysisList>(`/analyses?limit=10&offset=${(page - 1) * 10}`),
  analysis: (id: string) => request<AnalysisReport>(`/analyses/${encodeURIComponent(id)}`),
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
  authStatus: () => request<{ required: boolean; authenticated: boolean }>('/auth/status'),
  login: (key: string) =>
    request<{ authenticated: boolean }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ key }),
    }),
};
