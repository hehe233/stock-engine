import { expect, test } from '@playwright/test';

test('P3 dataset, durable training, calibration, constrained backtest and artifact download', async ({
  page,
  request,
}) => {
  expect((await (await request.get('/api/health')).json()).data_mode).toBe('demo');
  await page.goto('/quant');
  await expect(page.getByRole('heading', { name: '策略与概率实验', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '创建合成实验集', exact: true }).click();
  await expect(page.getByText('合成 / 演示数据', { exact: true })).toBeVisible();
  await expect(page.getByText(/4,960 行 · 8 只证券/)).toBeVisible();
  await page.getByRole('button', { name: '创建滚动实验', exact: true }).click();
  await expect(page.getByRole('heading', { name: '量化实验报告', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '样本外预测与校准', exact: true })).toBeVisible({
    timeout: 90000,
  });
  await expect(
    page.getByRole('heading', { name: '成交约束与资金曲线', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('这是合成数据实验，不代表市场效果', { exact: true })).toBeVisible();
  await expect(
    page.getByText('完成 3 / 请求 3 折。标签结束日必须早于下一分区起始日。'),
  ).toBeVisible();
  const id = page.url().split('/').pop();
  const report = await (await request.get(`/api/quant/runs/${id}`)).json();
  expect(report.result.metrics.count).toBeGreaterThan(100);
  expect(report.result.backtest.trade_count).toBeGreaterThan(0);
  const download = await request.get(`/api/quant/runs/${id}/artifacts/models.json`);
  expect(download.ok()).toBe(true);
  expect((await download.json())[0].lightgbm_text).toContain('tree');
  await page.screenshot({ path: '../../.runtime/p3-report.png', fullPage: true });
  await page.reload();
  await expect(page.getByRole('heading', { name: '样本外预测与校准', exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.runtime/p3-mobile.png', fullPage: true });
});

test('P3 CSV preview reports missing execution fields before immutable import', async ({
  page,
}) => {
  await page.goto('/quant');
  await page.getByLabel('数据集名称', { exact: true }).fill('CSV 浏览器审计');
  await page.getByLabel('数据来源说明', { exact: true }).fill('自动化测试，非市场数据');
  const lines = ['symbol,date,open,high,low,close'];
  for (let i = 0; i < 40; i++) {
    const date = new Date(Date.UTC(2024, 0, 1 + i)).toISOString().slice(0, 10);
    lines.push(`DEMOQ999,${date},10,11,9,10`);
  }
  await page.getByLabel('量化日线 CSV').setInputFiles({
    name: 'bars.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(lines.join('\n')),
  });
  await page.getByRole('button', { name: '校验并预览', exact: true }).click();
  await expect(page.getByText('成交所需字段完整：0 行；缺精确可见时间：40 行。')).toBeVisible();
  await page.getByRole('button', { name: '确认保存数据版本', exact: true }).click();
  await expect(page.getByTitle(/CSV 浏览器审计/)).toBeVisible();
  await expect(page.getByRole('button', { name: '确认保存数据版本', exact: true })).toHaveCount(0);
});
