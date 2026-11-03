import { request } from './http';
import type {
  ModelSettings,
  ModelSettingsInput,
  ModelProfile,
  ModelProfileInput,
  ModelProfileList,
} from './types';

export const modelSettingsApi = {
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
};
