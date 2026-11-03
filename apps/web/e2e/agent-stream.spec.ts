import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type { AnalysisReport, JobEvent, ResearchJob } from '../src/api/types';

declare global {
  interface Window {
    agentTestStreams: (EventTarget & {
      closed: boolean;
      url: string;
      onerror: ((event: Event) => void) | null;
    })[];
  }
}

const jobId = 'stream-test';
const replayFixture = JSON.parse(
  readFileSync(new URL('../../../tests/fixtures/agent-replay.json', import.meta.url), 'utf8'),
);
const timestamp = new Date().toISOString();
const summary = '样本活跃程度较高，但现有证据不能推断连板概率。';
const factors = [
  {
    name: '涨幅强度',
    value: 9.8,
    points: 29.4,
    max_points: 30,
    explanation: '涨幅 / 10 × 30，上限 30 分',
  },
  {
    name: '换手活跃',
    value: 18,
    points: 22.5,
    max_points: 25,
    explanation: '换手率 / 20 × 25，上限 25 分',
  },
  {
    name: '量比强度',
    value: 4.8,
    points: 24,
    max_points: 25,
    explanation: '量比 / 5 × 25，上限 25 分',
  },
  {
    name: '成交规模',
    value: 800000000,
    points: 16,
    max_points: 20,
    explanation: '成交额 / 10 亿 × 20',
  },
];
const insight = {
  summary,
  observations: [
    { text: '量比与换手率均表现活跃，需要结合行情来源时间阅读。', evidence_ids: ['read_quote'] },
  ],
  limitations: ['仅解读当前快照，不能视为买卖指令。'],
};
const report: AnalysisReport = {
  id: jobId,
  snapshot_id: 'snapshot',
  symbol: 'DEMO001',
  name: '样本·算力一号',
  created_at: timestamp,
  as_of: timestamp,
  source: 'demo',
  is_demo: true,
  asset_type: 'stock',
  analysis_mode: 'api',
  score_version: 'heat-v1',
  heat_score: 91.9,
  model_name: 'stream-test-model',
  insight,
  evidence: { read_quote: { quote: { symbol: 'DEMO001', price: 18.5 } } },
  summary,
  factors,
  risks: ['当前为虚构演示样本，不能用于真实交易判断。'],
  trace: [],
  research_context: {},
};

async function setup(page: Page, live = true) {
  let job: ResearchJob = {
    id: jobId,
    snapshot_id: 'snapshot',
    symbol: 'DEMO001',
    mode: 'api',
    model_name: 'stream-test-model',
    status: 'running',
    created_at: timestamp,
    updated_at: timestamp,
    attempts: 1,
    cancel_requested: false,
    error: null,
    report_id: null,
  };
  let reads = 0;
  let nextId = 0;
  const history: JobEvent[] = [];
  const make = (kind: string, payload: JobEvent['payload']): JobEvent => ({
    id: ++nextId,
    kind,
    payload: { attempt: job.attempts, ...payload },
    created_at: new Date().toISOString(),
  });
  if (live)
    await page.addInitScript(() => {
      window.agentTestStreams = [];
      class FakeEventSource extends EventTarget {
        closed = false;
        onopen: ((event: Event) => void) | null = null;
        onerror: ((event: Event) => void) | null = null;
        constructor(public url: string) {
          super();
          window.agentTestStreams.push(this);
          queueMicrotask(() => this.onopen?.(new Event('open')));
        }
        close() {
          this.closed = true;
        }
      }
      window.EventSource = FakeEventSource as unknown as typeof EventSource;
    });
  await page.route('http://127.0.0.1:5173/api/**', (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/auth/status')
      return route.fulfill({ json: { authenticated: true } });
    if (url.pathname === '/api/jobs') return route.fulfill({ json: { items: [job] } });
    if (url.pathname === `/api/jobs/${jobId}`) {
      reads++;
      return route.fulfill({ json: job });
    }
    if (url.pathname === `/api/analyses/${jobId}`) return route.fulfill({ json: report });
    if (url.pathname === `/api/jobs/${jobId}/cancel`) {
      job = { ...job, cancel_requested: true };
      return route.fulfill({ json: job });
    }
    if (url.pathname === `/api/jobs/${jobId}/retry`) {
      job = { ...job, status: 'running', error: null, attempts: 2 };
      return route.fulfill({ json: job });
    }
    if (url.pathname.endsWith('/events'))
      return route.fulfill({
        contentType: 'text/event-stream',
        body:
          history
            .map((item) => `id: ${item.id}\nevent: progress\ndata: ${JSON.stringify(item)}\n\n`)
            .join('') + 'event: done\ndata: {}\n\n',
      });
    return route.abort();
  });
  return {
    make,
    history,
    reads: () => reads,
    status: (status: ResearchJob['status']) => {
      job = {
        ...job,
        status,
        updated_at: new Date().toISOString(),
        report_id: status === 'succeeded' ? jobId : null,
        error: status === 'failed' ? '测试：连接中断，检查点已保留' : null,
      };
    },
    emit: async (...events: JobEvent[]) => {
      history.push(...events);
      await expect
        .poll(() => page.evaluate(() => window.agentTestStreams.filter((s) => !s.closed).length))
        .toBe(1);
      await page.evaluate((items) => {
        const source = window.agentTestStreams.filter((s) => !s.closed).at(-1)!;
        for (const item of items)
          source.dispatchEvent(new MessageEvent('progress', { data: JSON.stringify(item) }));
      }, events);
    },
  };
}

test('live reasoning, tool details, character output and report drawer stay in sync', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  const app = await setup(page);
  await page.goto(`/jobs/${jobId}`);
  await expect
    .poll(() => page.evaluate(() => window.agentTestStreams.filter((s) => !s.closed).length))
    .toBe(1);
  const connections = await page.evaluate(() => window.agentTestStreams.length);
  await page.getByRole('button', { name: '收起侧边栏', exact: true }).click();
  await page.getByRole('button', { name: '展开侧边栏', exact: true }).click();
  expect(await page.evaluate(() => window.agentTestStreams.length)).toBe(connections);
  const stream = page.getByRole('region', { name: 'Agent 分析过程' });
  await expect(stream).toBeVisible();
  await app.emit(
    app.make('node', {
      node: 'validate',
      message: '校验行情快照',
      detail: '确认证券、来源和行情时间',
    }),
    app.make('model.start', { block_id: 'plan', message: '分析证据' }),
    app.make('reasoning.delta', { block_id: 'plan', text: '先检查数据来源，再对照规则因子。' }),
  );
  await expect(stream.getByText('先检查数据来源，再对照规则因子。')).toBeVisible();
  const body =
    '**已取得行情证据。**\n\n' + '将结合换手率、量比和成交额判断样本活跃程度。'.repeat(20);
  const readCount = app.reads();
  await app.emit(app.make('content.delta', { block_id: 'plan', text: body }));
  await expect(stream.locator('[data-streaming="true"]')).toHaveCount(1);
  await expect(stream.getByText('已取得行情证据。', { exact: true })).toBeVisible();
  expect(app.reads()).toBeLessThanOrEqual(readCount + 1);
  const modelEnd = app.make('model.end', { block_id: 'plan' });
  const toolStart = app.make('tool.start', { call_id: 'quote', name: 'read_quote', arguments: {} });
  await app.emit(
    modelEnd,
    toolStart,
    app.make('tool.end', {
      call_id: 'quote',
      name: 'read_quote',
      result: report.evidence.read_quote,
    }),
    app.make('report.patch', {
      patch: { heat_score: 91.9, summary, factors, risks: report.risks },
    }),
    app.make('model.start', { block_id: 'report', message: '生成研究报告' }),
    app.make('report.start', { block_id: 'report' }),
    app.make('report.delta', { block_id: 'report', insight }),
  );
  // Duplicate replay must not create another tool card or repeat text.
  await app.emit(toolStart);
  await expect(stream.getByText('读取行情快照', { exact: true })).toHaveCount(1);
  await stream.getByText('查看完整工具结果', { exact: true }).click();
  await expect(stream.locator('pre').filter({ hasText: '18.5' })).toBeVisible();
  const drawer = page.getByRole('complementary', { name: '研究报告抽屉' });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole('heading', { name: '模型研究解读' })).toBeVisible();
  await expect(drawer.getByText('生成草稿 · 待校验')).toBeVisible();
  await expect(stream.getByText(summary, { exact: true })).toBeVisible();
  const handle = page.getByRole('separator', { name: '调整报告抽屉宽度' });
  const before = Number(await handle.getAttribute('aria-valuenow'));
  await handle.focus();
  await page.keyboard.press('ArrowRight');
  await expect(handle).toHaveAttribute('aria-valuenow', String(before - 32));
  await expect
    .poll(async () => Math.abs((await drawer.boundingBox())!.width - (before - 32)))
    .toBeLessThan(1);
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 100);
  await page.mouse.down();
  await page.mouse.move(box.x + 85, box.y + 100, { steps: 5 });
  await page.mouse.up();
  await expect
    .poll(async () => Number(await handle.getAttribute('aria-valuenow')))
    .toBeLessThan(before - 32);
  await drawer.getByRole('button', { name: '收起报告抽屉' }).click();
  await expect(drawer).not.toBeVisible();
  await app.emit(
    app.make('content.delta', { block_id: 'plan', text: '\n\n关闭报告后仍持续接收正文。' }),
  );
  await expect(stream.getByText('关闭报告后仍持续接收正文。')).toBeVisible();
  await page.getByRole('button', { name: /样本|DEMO001 · 研究报告/ }).click();
  await expect(drawer).toBeVisible();
  app.status('succeeded');
  await app.emit(app.make('model.end', { block_id: 'report' }));
  await app.emit(app.make('succeeded', { message: '报告已保存', report_id: jobId }));
  await page.evaluate(() =>
    window.agentTestStreams
      .filter((s) => !s.closed)
      .at(-1)
      ?.dispatchEvent(new MessageEvent('done')),
  );
  await expect(page.getByRole('link', { name: '打开完整报告 →' })).toBeVisible();
  await expect(drawer.getByText('生成草稿 · 待校验')).toHaveCount(0);
  await page.getByRole('main').evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({ path: '../../.runtime/agent-stream-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('native SSE history survives reload and the mobile report drawer closes accessibly', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const app = await setup(page, false);
  app.status('succeeded');
  app.history.push(
    app.make('model.start', { block_id: 'history', message: '分析证据' }),
    app.make('reasoning.delta', { block_id: 'history', text: '已保存的模型思考内容。' }),
    app.make('content.delta', { block_id: 'history', text: '已保存的分析正文。' }),
    app.make('model.end', { block_id: 'history' }),
    app.make('report.patch', { patch: report }),
    app.make('succeeded', { report_id: jobId }),
  );
  await page.goto(`/jobs/${jobId}`);
  await expect(page.getByText('已保存的分析正文。')).toBeVisible();
  await page.reload();
  await expect(page.getByText('已保存的模型思考内容。')).toHaveCount(1);
  await page.getByRole('button', { name: /样本·算力一号 · 研究报告/ }).click();
  const drawer = page.getByRole('dialog', { name: '研究报告' });
  await expect(drawer).toBeVisible();
  await expect.poll(async () => Math.abs((await drawer.boundingBox())!.x)).toBeLessThan(1);
  await expect(drawer.getByRole('heading', { name: '分析摘要' })).toBeVisible();
  await page.screenshot({ path: '../../.runtime/agent-stream-mobile.png', fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
  await expect(page.getByRole('button', { name: /样本·算力一号 · 研究报告/ })).toBeFocused();
  // Closing during the opening animation must also return focus.
  await page.getByRole('button', { name: /样本·算力一号 · 研究报告/ }).click();
  await page.keyboard.press('Escape');
  await expect(drawer).not.toBeVisible();
  await expect(page.getByRole('button', { name: /样本·算力一号 · 研究报告/ })).toBeFocused();
});

test('reconnection deduplicates deltas and retry retains interrupted history', async ({ page }) => {
  const app = await setup(page);
  await page.goto(`/jobs/${jobId}`);
  await app.emit(
    app.make('model.start', { block_id: 'first' }),
    app.make('reasoning.delta', { block_id: 'first', text: '已接收的思考片段。' }),
  );
  await page.evaluate(() =>
    window.agentTestStreams
      .filter((s) => !s.closed)
      .at(-1)
      ?.onerror?.(new Event('error')),
  );
  await expect(
    page.getByText('进度连接暂时中断，正在尝试重连；任务状态仍会定时更新。'),
  ).toBeVisible();
  const last = app.make('content.delta', { block_id: 'first', text: '已恢复的正文。' });
  await app.emit(last, last);
  await expect(page.getByText('已恢复的正文。')).toHaveCount(1);
  app.status('failed');
  await app.emit(app.make('failed', { message: '本次执行失败' }));
  await page.evaluate(() =>
    window.agentTestStreams
      .filter((s) => !s.closed)
      .at(-1)
      ?.dispatchEvent(new MessageEvent('done')),
  );
  await page.getByRole('button', { name: '从检查点重试' }).click();
  await expect
    .poll(() => page.evaluate(() => window.agentTestStreams.filter((s) => !s.closed).at(-1)?.url))
    .toContain(`after=${app.history.at(-1)!.id}`);
  await app.emit(
    app.make('running', { message: '恢复执行' }),
    app.make('model.start', { block_id: 'second' }),
  );
  await expect(page.getByText('已中断', { exact: true })).toBeVisible();
  await expect(page.getByText('正在思考', { exact: true })).toHaveCount(1);
  await page.getByRole('button', { name: '取消任务', exact: true }).click();
  await expect(page.getByRole('button', { name: '取消处理中' })).toBeDisabled();
});

test('shared persisted replay deduplicates events and archives the final report', async ({
  page,
}) => {
  const app = await setup(page);
  await page.goto(`/jobs/${jobId}`);
  const events: JobEvent[] = replayFixture.events.map((event: Pick<JobEvent, 'kind' | 'payload'>) =>
    app.make(event.kind, event.payload),
  );
  app.status('succeeded');
  // Reconnect can redeliver the last persisted event. The hook owns cursor deduplication.
  await app.emit(...events.slice(0, 9), events[8], ...events.slice(9));
  await expect(page.getByText('核验来源。', { exact: true })).toHaveCount(1);
  await expect(page.getByText('旧草稿', { exact: true })).toHaveCount(1);
  await expect(page.getByText('已中断', { exact: true })).toHaveCount(1);
  await expect(page.getByRole('link', { name: '打开完整报告 →' })).toBeVisible();
  const reads = app.reads();
  await page.evaluate(() =>
    window.agentTestStreams
      .filter((s) => !s.closed)
      .at(-1)
      ?.dispatchEvent(new MessageEvent('done')),
  );
  // Terminal progress already refreshed the job; done only drains and closes the stream.
  await expect
    .poll(() => page.evaluate(() => window.agentTestStreams.filter((s) => !s.closed).length))
    .toBe(0);
  expect(app.reads()).toBe(reads);
});
