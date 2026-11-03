import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { researchApi, type ResearchQuery } from '../../api/research';

export const researchKeys = { datasets: ['research'] as const, history: ['history'] as const };
export const researchQueries = {
  data: (query: ResearchQuery, search: string, page: number) =>
    queryOptions({
      queryKey: [...researchKeys.datasets, query, search, page],
      queryFn: () => researchApi.data(query, search, page),
      refetchInterval: (q) =>
        ['queued', 'running'].includes(q.state.data?.request?.status ?? '') ? 5000 : 300000,
    }),
  history: () =>
    queryOptions({
      queryKey: researchKeys.history,
      queryFn: researchApi.history,
      refetchInterval: (q) =>
        q.state.data?.items.some((item) =>
          ['queued', 'running'].includes(item.request?.status ?? ''),
        )
          ? 5000
          : 300000,
    }),
};
export async function invalidateResearch(client: QueryClient) {
  await Promise.all([
    client.invalidateQueries({ queryKey: researchKeys.datasets }),
    client.invalidateQueries({ queryKey: researchKeys.history }),
  ]);
}
