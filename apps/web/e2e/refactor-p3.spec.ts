import { expect, test } from '@playwright/test';
import type { Position, PositionInput } from '../src/api/portfolio';

test('portfolio editor keeps selected lot, cancels drafts and refreshes after update/delete', async ({
  page,
  request,
}) => {
  expect((await (await request.get('/api/health')).json()).data_mode).toBe('demo');
  const note = `P3-editor-${Date.now()}`;
  const rows: PositionInput[] = [1, 2].map((n) => ({
    symbol: `DEMO00${n}`,
    name: `${note}-${n}`,
    asset_type: 'stock',
    quantity: 100 + n,
    cost_price: '12.1234',
    acquired_on: '2025-01-02',
    settlement: 'T1',
    note,
  }));
  expect((await request.post('/api/portfolio/import', { data: { rows } })).ok()).toBe(true);
  try {
    await page.goto('/portfolio');
    const first = page.getByRole('row').filter({ hasText: `${note}-1` });
    const second = page.getByRole('row').filter({ hasText: `${note}-2` });
    await first.getByRole('button', { name: '编辑', exact: true }).click();
    await expect(page.getByLabel('证券代码', { exact: true })).toHaveValue('DEMO001');
    await page.getByLabel('剩余数量', { exact: true }).fill('777');
    await page.getByRole('button', { name: '取消编辑', exact: true }).click();
    await expect(page.getByLabel('证券代码', { exact: true })).toHaveValue('');
    await second.getByRole('button', { name: '编辑', exact: true }).click();
    await expect(page.getByLabel('证券代码', { exact: true })).toHaveValue('DEMO002');
    await expect(page.getByLabel('剩余数量', { exact: true })).toHaveValue('102');
    await page.getByLabel('剩余数量', { exact: true }).fill('202');
    await page.getByRole('button', { name: '保存持仓', exact: true }).click();
    await expect(page.getByText('持仓已保存；完全相同的重复行会跳过。')).toBeVisible();
    await expect(second).toContainText('202');
    const current: Position[] = (await (await request.get('/api/portfolio')).json()).items;
    expect(current.find((row) => row.name === `${note}-1`)?.quantity).toBe(101);
    expect(current.find((row) => row.name === `${note}-2`)?.quantity).toBe(202);
    await second.getByRole('button', { name: '删除', exact: true }).click();
    await second.getByRole('button', { name: '确认删除该笔', exact: true }).click();
    await expect(second).toHaveCount(0);
  } finally {
    const current: Position[] = (await (await request.get('/api/portfolio')).json()).items;
    for (const row of current.filter((row) => row.note === note))
      await request.post(`/api/portfolio/${row.id}/delete`);
  }
});

test('CSV module clears old preview on failure without changing the editor draft', async ({
  page,
}) => {
  await page.goto('/portfolio');
  await page.getByLabel('证券名称', { exact: true }).fill('未提交的草稿');
  const input = page.getByLabel('导入持仓 CSV');
  const content =
    'symbol,name,asset_type,quantity,cost_price,acquired_on,settlement,note\nDEMO001,样例,stock,100,12.1234,2025-01-02,T1,test\n';
  await input.setInputFiles({
    name: 'valid.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(content),
  });
  await expect(page.getByRole('button', { name: '确认追加导入' })).toBeEnabled();
  await input.setInputFiles({
    name: 'invalid.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('bad,columns\nx,y\n'),
  });
  await expect(page.getByText(/CSV 表头或顺序不正确/)).toBeVisible();
  await expect(page.getByRole('button', { name: '确认追加导入' })).toHaveCount(0);
  await expect(page.getByLabel('证券名称', { exact: true })).toHaveValue('未提交的草稿');
});

test('settings form preserves unsaved changes when profile switch is dismissed', async ({
  page,
}) => {
  await page.goto('/settings/models');
  await expect(page.getByLabel('API 地址（Base URL）')).toBeVisible();
  await page.getByLabel('API 地址（Base URL）').fill('https://draft.example/v1');
  page.once('dialog', (dialog) => dialog.dismiss());
  await page.getByRole('button', { name: '新增配置', exact: true }).click();
  await expect(page.getByLabel('API 地址（Base URL）')).toHaveValue('https://draft.example/v1');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '新增配置', exact: true }).click();
  await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('API 地址（Base URL）')).toHaveValue('');
});

test('remaining directory pages support direct entry, reload and narrow layout', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  for (const [url, title] of [
    ['/', '行情工作台'],
    ['/portfolio', '持仓分析'],
    ['/settings/models', '模型设置'],
    ['/jobs', '研究任务'],
    ['/reports', '分析记录'],
    ['/roadmap', '开发路线'],
  ]) {
    await page.goto(url);
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({
      path: `../../.runtime/refactor-p3-${url.replaceAll('/', '-') || 'home'}-mobile.png`,
      fullPage: true,
    });
  }
  expect(errors).toEqual([]);
});

test('auth module exposes login errors and clears the gate after authentication', async ({
  page,
}) => {
  let authenticated = false;
  let attempts = 0;
  await page.route('**/api/auth/status', (route) => route.fulfill({ json: { authenticated } }));
  await page.route('**/api/auth/login', (route) => {
    attempts++;
    if (attempts === 1) return route.fulfill({ status: 401, json: { detail: '测试访问密钥错误' } });
    authenticated = true;
    return route.fulfill({ json: { authenticated: true } });
  });
  await page.goto('/');
  await page.getByLabel('应用访问密钥', { exact: true }).fill('test-only');
  await page.getByRole('button', { name: '进入工作台', exact: true }).click();
  await expect(page.getByText('测试访问密钥错误')).toBeVisible();
  await page.getByRole('button', { name: '进入工作台', exact: true }).click();
  await expect(page.getByRole('heading', { name: '行情工作台', exact: true })).toBeVisible();
});
