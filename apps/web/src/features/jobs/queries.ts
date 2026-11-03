import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { jobsApi } from '../../api/jobs';
import type { ResearchJob } from '../../api/types';
import { reportKeys } from '../reports/queries';

export const jobQueries = {
  list: () => queryOptions({ queryKey: ['jobs'], queryFn: jobsApi.jobs }),
  detail: (id: string) => queryOptions({ queryKey: ['job', id], queryFn: () => jobsApi.job(id) }),
};

export function invalidateJobs(client: QueryClient) {
  return client.invalidateQueries({ queryKey: jobQueries.list().queryKey });
}

export async function refreshJob(client: QueryClient, id: string, terminal = false) {
  await Promise.all([
    client.invalidateQueries({ queryKey: jobQueries.detail(id).queryKey }),
    invalidateJobs(client),
    ...(terminal
      ? [
          client.invalidateQueries({ queryKey: reportKeys.lists }),
          client.invalidateQueries({ queryKey: reportKeys.details }),
        ]
      : []),
  ]);
}

export function jobUpdated(client: QueryClient, job: ResearchJob) {
  client.setQueryData(jobQueries.detail(job.id).queryKey, job);
  return invalidateJobs(client);
}
