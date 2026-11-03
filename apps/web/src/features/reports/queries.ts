import { queryOptions } from '@tanstack/react-query';
import { reportsApi } from '../../api/reports';

export const reportKeys = { lists: ['analyses'] as const, details: ['analysis'] as const };
export const reportQueries = {
  list: (page: number) =>
    queryOptions({
      queryKey: [...reportKeys.lists, page],
      queryFn: () => reportsApi.analyses(page),
    }),
  detail: (id: string | null | undefined) =>
    queryOptions({
      queryKey: [...reportKeys.details, id],
      enabled: Boolean(id),
      queryFn: () => {
        if (!id) throw new Error('报告 ID 缺失');
        return reportsApi.analysis(id);
      },
    }),
};
