import { request } from './http';
import type { AppConfig } from './types';

export const configApi = {
  config: () => request<AppConfig>('/config'),
};
