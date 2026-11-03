import { expect, test } from '@playwright/test';

test('research query errors can be retried through the extracted shared module', async ({
  page,
}) => {
  await page.route('**/api/research/data?*', (route) =>
    route.fulfill({ status: 503, json: { detail: 'P1 研究查询暂时失败' } }),
  );
  await page.goto('/research');
  await expect(page.getByText('P1 研究查询暂时失败')).toBeVisible({ timeout: 15000 });
  await page.unroute('**/api/research/data?*');
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.getByText('3 板 · 1 只')).toBeVisible();
  await expect(page.getByText('P1 研究查询暂时失败')).toHaveCount(0);
});

test('quant detail cancellation refreshes status and prediction pagination remains separate', async ({
  page,
}) => {
  let status = 'queued';
  let reads = 0;
  let predictionReads = 0;
  await page.route('**/api/quant/runs/p1-cancel', (route) => {
    reads++;
    return route.fulfill({
      json: {
        id: 'p1-cancel',
        dataset_id: 'p1-data',
        status,
        is_demo: true,
        cancel_requested: status === 'cancelled',
        created_at: '2026-11-03T00:00:00Z',
        updated_at: '2026-11-03T00:00:00Z',
        params: {},
        result: {},
        error: null,
      },
    });
  });
  await page.route('**/api/quant/runs/p1-cancel/predictions*', (route) => {
    predictionReads++;
    return route.fulfill({ json: { items: [], total: 0 } });
  });
  await page.route('**/api/quant/runs/p1-cancel/cancel', (route) => {
    status = 'cancelled';
    return route.fulfill({ json: { status } });
  });
  await page.goto('/quant/p1-cancel');
  await page.getByRole('button', { name: '取消实验', exact: true }).click();
  await expect(page.getByText('已取消 ·', { exact: true })).toBeVisible();
  expect(reads).toBeGreaterThanOrEqual(2);
  expect(predictionReads).toBe(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: '量化实验报告', exact: true })).toBeVisible();
  await page.getByRole('link', { name: '返回实验工作台' }).click();
  await expect(page.getByRole('heading', { name: '策略与概率实验', exact: true })).toBeVisible();
});

test('migrated pages support direct navigation, reload and narrow layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [path, title] of [
    ['/quant', '策略与概率实验'],
    ['/research', '短线研究中心'],
    ['/history', '近十年历史案例'],
  ]) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: `../../.runtime/p1-${path.slice(1)}-mobile.png`,
      fullPage: true,
    });
  }
});
