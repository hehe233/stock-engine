import { queryOptions } from '@tanstack/react-query';
import { authApi } from '../../api/auth';

export const authQueries = {
  status: () => queryOptions({ queryKey: ['auth'], queryFn: authApi.authStatus, staleTime: 0 }),
};
