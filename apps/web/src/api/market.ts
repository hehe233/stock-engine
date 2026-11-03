import { request } from './http';
import type { MarketResponse, MarketStatus } from './types';

export const marketApi = {
  marketStatus: () => request<MarketStatus>('/market/status'),
  quotes: (params: URLSearchParams = new URLSearchParams()) =>
    request<MarketResponse>(`/market/quotes?${params}`),
  refresh: () =>
    request<{ accepted: boolean; message: string }>('/market/refresh', { method: 'POST' }),
};
