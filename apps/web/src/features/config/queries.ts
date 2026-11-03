import { queryOptions } from '@tanstack/react-query';
import { configApi } from '../../api/config';

export const configQueries = {
  current: () => queryOptions({ queryKey: ['config'], queryFn: configApi.config }),
};
