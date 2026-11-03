import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { marketApi } from '../../api/market';

export const marketQueries = {
  status: () => queryOptions({ queryKey: ['market-status'], queryFn: marketApi.marketStatus }),
  quotes: (params: URLSearchParams, snapshotId?: string) =>
    queryOptions({
      queryKey: ['market', params.toString(), snapshotId],
      queryFn: () => marketApi.quotes(params),
    }),
};
export function invalidateMarketStatus(client: QueryClient) {
  return client.invalidateQueries({ queryKey: marketQueries.status().queryKey });
}
