import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { modelSettingsApi } from '../../api/model-settings';
import { configQueries } from '../config/queries';

export const modelSettingsQueries = {
  settings: () =>
    queryOptions({ queryKey: ['model-settings'], queryFn: modelSettingsApi.modelSettings }),
  profiles: () =>
    queryOptions({ queryKey: ['model-profiles'], queryFn: modelSettingsApi.modelProfiles }),
};
export async function invalidateModelSettings(client: QueryClient) {
  await Promise.all([
    client.invalidateQueries({ queryKey: modelSettingsQueries.settings().queryKey }),
    client.invalidateQueries({ queryKey: modelSettingsQueries.profiles().queryKey }),
    client.invalidateQueries({ queryKey: configQueries.current().queryKey }),
  ]);
}
