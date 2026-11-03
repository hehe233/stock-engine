import { defineConfig, devices } from '@playwright/test';

// 服务由 start-dev.ps1 启动；测试不暗中拉起另一个 dev server，避免 Windows 残留进程。
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'msedge' } }],
});
