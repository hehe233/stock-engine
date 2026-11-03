import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { portfolioApi } from '../../api/portfolio';

export const portfolioQueries = {
  current: () => queryOptions({ queryKey: ['portfolio'], queryFn: portfolioApi.portfolio }),
};
export function invalidatePortfolio(client: QueryClient) {
  return client.invalidateQueries({ queryKey: portfolioQueries.current().queryKey });
}
