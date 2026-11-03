import { expect, test } from '@playwright/test';

test('research tiers, disclosed seats, flow boundaries and notices are accessible', async ({
  page,
}) => {
  await page.goto('/research');
  await expect(page.getByRole('heading', { name: '短线研究中心' })).toBeVisible();
  await expect(page.getByText('3 板 · 1 只')).toBeVisible();
  await expect(page.getByText('虚构演示数据', { exact: true })).toBeVisible();
  await page.getByRole('tab', { name: '龙虎榜', exact: true }).click();
  await expect(page.getByText('虚构上榜原因')).toBeVisible();
  await page.getByRole('button', { name: '查看席位' }).click();
  await page.getByRole('heading', { name: '营业部明细 · DEMO001' }).scrollIntoViewIfNeeded();
  const panel = page
    .locator('section')
    .filter({ has: page.getByRole('heading', { name: '营业部明细 · DEMO001' }) });
  await panel.getByRole('button', { name: /采集 \/ 更新/ }).click();
  await expect(page.getByText('演示营业部（虚构）')).toBeVisible({ timeout: 30000 });
  await page.getByRole('tab', { name: '资金流向', exact: true }).click();
  await expect(page.getByText('资金流向固定读取当前快照，源交易日期未知。')).toBeVisible();
  await page.getByRole('tab', { name: '公告证据', exact: true }).click();
  await expect(page.getByText('演示风险提示公告（虚构）')).toBeVisible();
  await page.screenshot({ path: '../../.runtime/p2-research.png', fullPage: true });
});

test('portfolio saves lots, previews CSV, computes T+1 and binds a research report', async ({
  page,
  request,
}) => {
  const note = 'P2-E2E-' + Date.now();
  try {
    await page.goto('/portfolio');
    await page.getByLabel('证券代码', { exact: true }).fill('DEMO001');
    await page.getByLabel('证券名称', { exact: true }).fill('浏览器持仓');
    await page.getByLabel('剩余数量', { exact: true }).fill('137');
    await page.getByLabel('每份成本', { exact: true }).fill('11.1234');
    await page.getByLabel('备注', { exact: true }).fill(note);
    await page.getByRole('button', { name: '保存持仓', exact: true }).click();
    await expect(page.getByText('持仓已保存；完全相同的重复行会跳过。')).toBeVisible();
    const lot = (await (await request.get('/api/portfolio')).json()).items.find(
      (r: { note: string }) => r.note === note,
    );
    expect(lot.sellable).toBe(0);
    const holdingRow = page.getByRole('row').filter({ hasText: '浏览器持仓' });
    await expect(holdingRow).toContainText(
      new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(lot.pnl_yuan),
    );
    await expect(holdingRow).not.toContainText('0.00 亿');
    const day = await page.getByLabel('买入日期').inputValue();
    const csv =
      'symbol,name,asset_type,quantity,cost_price,acquired_on,settlement,note\n' +
      `DEMO002,CSV持仓,stock,237,9.1234,${day},T1,${note}\n`;
    await page
      .getByLabel('导入持仓 CSV')
      .setInputFiles({ name: 'positions.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
    await expect(page.getByText('有效行 1，错误 0。')).toBeVisible();
    await page.getByRole('button', { name: '确认追加导入' }).click();
    await expect(page.getByText('导入 1 行，跳过重复 0 行')).toBeVisible();
    await page.screenshot({ path: '../../.runtime/p2-portfolio.png', fullPage: true });
    await page.getByRole('button', { name: '分析持仓 DEMO001', exact: true }).click();
    await page.getByRole('link', { name: '打开完整报告 →' }).click({ timeout: 30000 });
    await expect(page.getByRole('heading', { name: '提交时冻结的研究证据' })).toBeVisible({
      timeout: 30000,
    });
    await expect(page.getByText('持仓条件', { exact: true })).toBeVisible();
  } finally {
    const current = await (await request.get('/api/portfolio')).json();
    for (const row of current.items.filter((r: { note: string }) => r.note === note)) {
      await request.post('/api/portfolio/' + row.id + '/delete');
    }
  }
});

test('ten-year history has verifiable strong and failure windows and mobile layout', async ({
  page,
}) => {
  await page.goto('/history');
  await expect(page.getByRole('heading', { name: '近十年历史案例' })).toBeVisible();
  await expect(page.getByRole('cell', { name: '四川双马', exact: false })).toBeVisible();
  await page.getByRole('button', { name: '获取日线', exact: true }).first().click();
  await expect(page.getByText('虚构演示日线', { exact: true }).first()).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole('button', { name: '查看数据', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: '历史日线', exact: true })).toBeVisible();
  await page.screenshot({ path: '../../.runtime/p2-history.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/portfolio');
  await expect(page.getByRole('heading', { name: '持仓分析', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../../.runtime/p2-mobile.png', fullPage: true });
});
