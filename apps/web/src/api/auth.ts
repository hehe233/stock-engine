import { request } from './http';

export const authApi = {
  authStatus: () => request<{ required: boolean; authenticated: boolean }>('/auth/status'),
  login: (key: string) =>
    request<{ authenticated: boolean }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ key }),
    }),
};
