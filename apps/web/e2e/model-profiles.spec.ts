import { expect, test } from '@playwright/test';

test('manage independent API profiles, switch, edit and delete across reloads', async ({
  page,
  request,
}) => {
  const health = await (await request.get('/api/health')).json();
  expect(health.data_mode).toBe('demo');
  const original = await (await request.get('/api/settings/models/profiles')).json();
  const before = await (await request.get('/api/settings/models')).json();
  expect(before.has_api_key).toBe(false);
  const prefix = `E2E-${Date.now()}`;
  async function add(name: string, model: string, host: string) {
    await page.getByRole('button', { name: '新增配置', exact: true }).click();
    await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('');
    await page.getByLabel('配置名称', { exact: true }).fill(name);
    await page.getByLabel('API 地址（Base URL）').fill(host);
    await page.getByLabel('API Key', { exact: true }).fill('profile-browser-secret');
    const models = page.getByRole('combobox', { name: '可选模型', exact: true });
    await models.fill(model);
    await models.press('Enter');
    await page.getByRole('combobox', { name: '默认模型', exact: true }).click();
    await page.getByTitle(model, { exact: true }).last().click();
    await page.getByRole('button', { name: '保存设置', exact: true }).click();
    await expect(page.getByText('配置已保存，点击「切换启用」后用于新任务。')).toBeVisible();
    expect(await page.content()).not.toContain('profile-browser-secret');
  }
  async function choose(name: string) {
    await page.getByRole('combobox', { name: '选择配置', exact: true }).click();
    await page.getByTitle(name, { exact: true }).click();
  }
  try {
    await page.goto('/settings/models');
    await add(prefix + ' A', 'profile-a', 'https://a.example/v1');
    await page.getByRole('button', { name: '切换启用', exact: true }).click();
    await expect(page.getByText(`已启用「${prefix} A」，新任务使用这套配置。`)).toBeVisible();
    await add(prefix + ' B', 'profile-b', 'https://b.example/v1');
    expect((await (await request.get('/api/config')).json()).default_model).toBe('profile-a');
    await page.getByRole('button', { name: '切换启用', exact: true }).click();
    await expect(page.getByText(`已启用「${prefix} B」，新任务使用这套配置。`)).toBeVisible();
    await page.reload();
    await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue(prefix + ' B');
    await expect(page.getByLabel('API 地址（Base URL）')).toHaveValue('https://b.example/v1');
    await page.getByLabel('配置名称', { exact: true }).fill(prefix + ' B edited');
    await page.getByRole('button', { name: '保存设置', exact: true }).click();
    await expect(
      page.getByText('模型设置已保存并生效，可返回行情工作台选择模型进行分析。'),
    ).toBeVisible();
    await choose(prefix + ' A');
    await page.getByRole('button', { name: '切换启用', exact: true }).click();
    await expect(page.getByText(`已启用「${prefix} A」，新任务使用这套配置。`)).toBeVisible();
    await choose(prefix + ' B edited');
    await page.getByRole('button', { name: '删除配置', exact: true }).click();
    await page.getByRole('button', { name: '确认删除配置', exact: true }).click();
    await expect(page.getByLabel('配置名称', { exact: true })).toHaveValue(prefix + ' A');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: '../../.runtime/model-profiles-mobile.png', fullPage: true });
    await page.getByRole('button', { name: '删除配置', exact: true }).click();
    await page.getByRole('button', { name: '确认删除配置', exact: true }).click();
    await expect(page.getByText('配置已删除；已提交任务仍保留原配置版本。')).toBeVisible();
    expect((await (await request.get('/api/config')).json()).api_configured).toBe(false);
  } finally {
    const current = await (await request.get('/api/settings/models/profiles')).json();
    for (const row of current.items.filter((p: { name: string }) => p.name.startsWith(prefix))) {
      await request.post(`/api/settings/models/profiles/${row.id}/delete`, {
        data: { revision: row.revision },
      });
    }
    if (original.active_id) {
      const row = current.items.find((p: { id: string }) => p.id === original.active_id);
      await request.post(`/api/settings/models/profiles/${row.id}/activate`, {
        data: { revision: row.revision },
      });
    } else {
      const now = await (await request.get('/api/settings/models')).json();
      await request.post('/api/settings/models', {
        data: {
          revision: now.revision,
          base_url: before.base_url,
          key_action: 'clear',
          default_model: before.default_model,
          models: before.models,
          ollama_base_url: before.ollama_base_url,
          ollama_model: before.ollama_model,
        },
      });
    }
  }
});
