import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { quantApi } from '../../api/quant';

export const quantQueries = {
  datasets: () => queryOptions({ queryKey: ['quant-datasets'], queryFn: quantApi.datasets }),
  runs: () =>
    queryOptions({
      queryKey: ['quant-runs'],
      queryFn: quantApi.runs,
      refetchInterval: (q) =>
        q.state.data?.items.some((r) => ['queued', 'running'].includes(r.status)) ? 3000 : 300000,
    }),
  run: (id: string) =>
    queryOptions({
      queryKey: ['quant-run', id],
      queryFn: () => quantApi.run(id),
      refetchInterval: (q) =>
        q.state.data && ['queued', 'running'].includes(q.state.data.status) ? 2000 : false,
    }),
  predictions: (id: string, page: number) =>
    queryOptions({
      queryKey: ['quant-predictions', id, page],
      queryFn: () => quantApi.predictions(id, page),
    }),
};
export function invalidateQuantDatasets(client: QueryClient) {
  return client.invalidateQueries({ queryKey: quantQueries.datasets().queryKey });
}
export function invalidateQuantRuns(client: QueryClient) {
  return client.invalidateQueries({ queryKey: quantQueries.runs().queryKey });
}
export async function refreshQuantRun(client: QueryClient, id: string) {
  await Promise.all([
    client.invalidateQueries({ queryKey: quantQueries.run(id).queryKey }),
    invalidateQuantRuns(client),
  ]);
}
