import { expect, test } from '@playwright/test';

test('configure API from navigation, persist, switch models and clear the key', async ({
  page,
  request,
}) => {
  const before = await (await request.get('/api/settings/models')).json();
  // 此测试只能在隔离演示库执行；不可覆盖用户的真实供应商凭证。
  expect(before.has_api_key).toBe(false);
  const reset = async () => {
    const current = await (await request.get('/api/settings/models')).json();
    const result = await request.post('/api/settings/models', {
      data: {
        revision: current.revision,
        base_url: before.base_url,
        key_action: 'clear',
        default_model: before.default_model,
        models: before.models,
        ollama_base_url: before.ollama_base_url,
        ollama_model: before.ollama_model,
      },
    });
    expect(result.ok()).toBe(true);
  };
  try {
    await page.goto('/');
    await page.getByRole('link', { name: '模型设置', exact: true }).click();
    await expect(page.getByRole('heading', { name: '模型设置', exact: true })).toBeVisible();
    await page.getByLabel('API 地址（Base URL）').fill('https://models.example/v1');
    await page.getByLabel('API Key', { exact: true }).fill('browser-test-key');
    const choices = page.getByRole('combobox', { name: '可选模型', exact: true });
    await choices.fill('browser-model-a');
    await choices.press('Enter');
    await choices.fill('browser-model-b');
    await choices.press('Enter');
    await page.getByRole('combobox', { name: '默认模型', exact: true }).click();
    await page.getByTitle('browser-model-b', { exact: true }).last().click();
    await page.getByRole('button', { name: '保存设置', exact: true }).click();
    await expect(
      page.getByText('模型设置已保存并生效，可返回行情工作台选择模型进行分析。'),
    ).toBeVisible();
    await page.reload();
    await expect(page.getByLabel('API 地址（Base URL）')).toHaveValue('https://models.example/v1');
    await expect(page.getByText('密钥已配置', { exact: false })).toBeVisible();
    expect(await page.content()).not.toContain('browser-test-key');
    await page.screenshot({ path: '../../.runtime/model-settings-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.screenshot({ path: '../../.runtime/model-settings-mobile.png', fullPage: true });

    // 验证选择值确实提交，不让测试凭证触发任何真实模型请求。
    let selected = '';
    await page.route('**/api/jobs', (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      selected = route.request().postDataJSON().model_name;
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '测试拦截，不调用模型' }),
      });
    });
    await page.getByRole('link', { name: '返回行情工作台 →' }).click();
    await expect(page.getByTitle('API · browser-model-b', { exact: true })).toBeVisible();
    await page.getByRole('combobox', { name: '分析模型', exact: true }).click();
    await page.getByTitle('API · browser-model-a', { exact: true }).click();
    await page.getByRole('button', { name: '分析 DEMO001', exact: true }).click();
    await expect(page.getByText('测试拦截，不调用模型')).toBeVisible();
    expect(selected).toBe('browser-model-a');
  } finally {
    await reset();
  }
});
