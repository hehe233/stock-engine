import { expect, test } from '@playwright/test';

test('search, analyze, persist, refresh and reopen a report', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '行情工作台', exact: true })).toBeVisible();
  await expect(page.getByText('演示数据模式', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '分析 DEMO001', exact: true })).toBeVisible();
  await page.screenshot({ path: '../../.runtime/workbench-desktop.png', fullPage: true });
  await page.getByRole('textbox', { name: '搜索样本' }).fill('DEMO001');
  await expect(page.getByRole('button', { name: '分析 DEMO001', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '分析 DEMO002', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '分析 DEMO001', exact: true }).click();
  await expect(page).toHaveURL(/\/jobs\/[a-f0-9-]+$/, { timeout: 20000 });
  await expect(page.getByRole('region', { name: 'Agent 分析过程' })).toBeVisible();
  await page.getByRole('link', { name: '打开完整报告 →' }).click({ timeout: 20000 });
  await expect(page.getByRole('heading', { name: '样本·算力一号 · 研究报告' })).toBeVisible();
  await expect(page.getByText('91.94 / 100', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '执行记录' })).toBeVisible();
  const reportUrl = page.url();
  await page.reload();
  await expect(page.getByRole('heading', { name: '数据依据' })).toBeVisible();
  await page.screenshot({ path: '../../.runtime/report-desktop.png', fullPage: true });
  await page.getByRole('link', { name: '行情工作台', exact: true }).click();
  const refreshed = page.waitForResponse(
    (response) =>
      response.url().endsWith('/api/market/refresh') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: '请求刷新' }).click();
  expect([202, 429]).toContain((await refreshed).status());
  await page.goto(reportUrl);
  await expect(page.getByText('91.94 / 100', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: '分析记录', exact: true }).click();
  await expect(page.getByRole('link', { name: '查看报告' }).first()).toBeVisible();
  expect(errors).toEqual([]);
});

test('empty search and narrow viewport remain usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('textbox', { name: '搜索样本' }).fill('不存在的股票');
  await expect(page.getByText('没有匹配的样本，请调整搜索条件')).toBeVisible();
  await page.screenshot({ path: '../../.runtime/workbench-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.getByRole('button', { name: '打开导航菜单' }).click();
  await page
    .getByRole('navigation', { name: '移动导航' })
    .getByRole('link', { name: '开发路线', exact: true })
    .click();
  await expect(page.getByRole('heading', { name: 'P1 · 接入真实数据与模型' })).toBeVisible();
});

test('API errors are visible and can be retried', async ({ page }) => {
  await page.route('**/api/market/quotes?*', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '测试：行情暂时不可用' }),
    }),
  );
  await page.goto('/');
  await expect(page.getByText('测试：行情暂时不可用')).toBeVisible();
  await page.unroute('**/api/market/quotes?*');
  await page.getByRole('button', { name: '重试', exact: true }).click();
  await expect(page.getByRole('button', { name: '分析 DEMO001', exact: true })).toBeVisible();
});

test('market data is read again after five minutes', async ({ page }) => {
  await page.clock.install();
  await page.goto('/');
  await expect(page.getByRole('button', { name: '分析 DEMO001', exact: true })).toBeVisible();
  const updated = page.waitForResponse((response) =>
    response.url().includes('/api/market/quotes?'),
  );
  await page.clock.fastForward(300_000);
  expect((await updated).status()).toBe(200);
});

test('ETF and index use their own universe and do not receive stock scores', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('combobox', { name: '证券类别' }).click();
  await page.getByTitle('ETF', { exact: true }).click();
  await expect(page.getByRole('button', { name: '分析 DEMOETF', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '分析 DEMOETF', exact: true }).click();
  await page.getByRole('link', { name: '打开完整报告 →' }).click({ timeout: 20000 });
  await expect(page.getByRole('heading', { name: '样本·ETF · 研究报告' })).toBeVisible({
    timeout: 20000,
  });
  await expect(page.getByText('不可用', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: '行情工作台', exact: true }).click();
  await page.getByRole('combobox', { name: '证券类别' }).click();
  await page.getByTitle('指数', { exact: true }).click();
  await expect(page.getByRole('button', { name: '分析 DEMOINDEX', exact: true })).toBeVisible();
});

test('configured API models can be selected and the chosen name is submitted', async ({ page }) => {
  await page.route('**/api/config', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        market_provider: 'demo',
        refresh_interval_seconds: 300,
        api_configured: true,
        api_models: ['model-a', 'model-b'],
        default_model: 'model-a',
        ollama_model: 'qwen3:8b',
      }),
    }),
  );
  let payload: { mode?: string; model_name?: string } = {};
  await page.route('**/api/jobs', (route) => {
    if (route.request().method() === 'POST') {
      payload = route.request().postDataJSON();
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '测试：模型服务未连接，不进行外部调用' }),
      });
    }
    return route.continue();
  });
  await page.goto('/');
  await page.getByRole('combobox', { name: '分析模型' }).click();
  await page.getByTitle('API · model-b', { exact: true }).click();
  await page.getByRole('button', { name: '分析 DEMO001', exact: true }).click();
  await expect(page.getByText('测试：模型服务未连接，不进行外部调用')).toBeVisible();
  expect(payload).toMatchObject({ mode: 'api', model_name: 'model-b' });
});
