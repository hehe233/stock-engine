import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/status', (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
  await page.route('**/api/jobs', (route) => route.fulfill({ json: { items: [] } }));
});

test('sidebar routes, collapse and width preferences remain usable after reload', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/roadmap');
  const nav = page.getByRole('navigation', { name: '主导航' });
  await expect(nav.getByRole('link')).toHaveCount(9);
  await expect(nav.getByRole('link', { name: '开发路线' })).toHaveAttribute('aria-current', 'page');
  await page.screenshot({ path: '../../.runtime/sidebar-reference-desktop.png' });
  const sidebar = page.getByRole('complementary', { name: '工作区侧边栏' });
  const handle = page.getByRole('separator', { name: '调整侧边栏宽度' });
  await handle.focus();
  await page.keyboard.press('ArrowRight');
  await expect(handle).toHaveAttribute('aria-valuenow', '240');
  // The state updates before the width transition finishes; drag the settled handle.
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBe(240);
  const rect = (await handle.boundingBox())!;
  await page.mouse.move(rect.x + rect.width / 2, rect.y + 200);
  await page.mouse.down();
  await page.mouse.move(rect.x + 100, rect.y + 200, { steps: 5 });
  await page.mouse.up();
  await expect(handle).toHaveAttribute('aria-valuenow', '260');
  await page.getByRole('button', { name: '收起侧边栏' }).click();
  await expect.poll(async () => (await sidebar.boundingBox())!.width).toBe(64);
  await expect(nav.getByRole('link', { name: '研究任务' })).toBeVisible();
  await page.screenshot({ path: '../../.runtime/shell-collapsed.png' });
  await page.reload();
  await expect(page.getByRole('button', { name: '展开侧边栏' })).toBeVisible();
  await page.getByRole('button', { name: '展开侧边栏' }).click();
  await expect(handle).toHaveAttribute('aria-valuenow', '260');
  await nav.getByRole('link', { name: '研究任务' }).click();
  await expect(page.getByRole('heading', { name: '研究任务', exact: true })).toBeVisible();
  await expect(nav.getByRole('link', { name: '研究任务' })).toHaveAttribute('aria-current', 'page');
  expect(errors).toEqual([]);
});

test('mobile navigation closes after selection and restores focus on escape', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/roadmap');
  await expect(page.getByRole('navigation', { name: '主导航' })).not.toBeVisible();
  const opener = page.getByRole('button', { name: '打开导航菜单' });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: '研究空间' });
  await expect(dialog).toBeVisible();
  await expect.poll(async () => Math.abs((await dialog.boundingBox())!.x)).toBeLessThan(1);
  await page.screenshot({ path: '../../.runtime/shell-mobile-navigation.png' });
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();
  await opener.click();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();
  await opener.click();
  await dialog.getByRole('link', { name: '研究任务' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole('heading', { name: '研究任务', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('workspace respects reduced motion and tablet content width', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 900, height: 800 });
  await page.goto('/roadmap');
  const main = page.getByRole('main');
  await expect(main.getByRole('heading', { name: 'P1 · 接入真实数据与模型' })).toBeVisible();
  expect(await main.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(
    await main
      .locator(':scope > div')
      .first()
      .evaluate((element) => getComputedStyle(element).animationName),
  ).toBe('none');
  await page.setViewportSize({ width: 320, height: 700 });
  expect(await main.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
});
