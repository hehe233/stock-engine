import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { QueryClient, type QueryKey } from '@tanstack/react-query';
import { request } from '../src/api/http';
import { invalidateModelSettings } from '../src/features/model-settings/queries';
import { invalidateResearch } from '../src/features/research/queries';
import { refreshJob } from '../src/features/jobs/queries';
import { quantQueries, refreshQuantRun } from '../src/features/quant/queries';
import { projectEvents } from '../src/components/agent/stream';
import type { JobEvent } from '../src/api/types';

test('model switch refreshes both settings views and analysis model config', async () => {
  const client = new QueryClient();
  const keys = [['model-settings'], ['model-profiles'], ['config'], ['portfolio']];
  keys.forEach((key) => client.setQueryData(key, { version: 'old' }));
  await invalidateModelSettings(client);
  expect(keys.map((key) => client.getQueryState(key)?.isInvalidated)).toEqual([
    true,
    true,
    true,
    false,
  ]);
  client.clear();
});

test('research refresh invalidates all filtered pages and historical summaries', async () => {
  const client = new QueryClient();
  const keys = [
    ['research', { kind: 'ladder' }, '', 1],
    ['research', { kind: 'history' }, 'x', 2],
    ['history'],
    ['quant-datasets'],
  ];
  keys.forEach((key) => client.setQueryData(key, {}));
  await invalidateResearch(client);
  expect(keys.map((key) => client.getQueryState(key)?.isInvalidated)).toEqual([
    true,
    true,
    true,
    false,
  ]);
  client.clear();
});

test('job terminal refresh includes report lists and details without touching other jobs', async () => {
  const client = new QueryClient();
  const keys = [['job', 'a'], ['jobs'], ['analyses', 1], ['analysis', 'a'], ['job', 'b']];
  keys.forEach((key) => client.setQueryData(key, {}));
  await refreshJob(client, 'a');
  expect(keys.map((key) => client.getQueryState(key)?.isInvalidated)).toEqual([
    true,
    true,
    false,
    false,
    false,
  ]);
  await refreshJob(client, 'a', true);
  expect(keys.map((key) => client.getQueryState(key)?.isInvalidated)).toEqual([
    true,
    true,
    true,
    true,
    false,
  ]);
  client.clear();
});

test('quant cancellation refreshes detail and list; immutable prediction pages stay distinct', async () => {
  const client = new QueryClient();
  const keys: QueryKey[] = [
    quantQueries.run('a').queryKey,
    quantQueries.runs().queryKey,
    quantQueries.predictions('a', 1).queryKey,
    quantQueries.predictions('a', 2).queryKey,
  ];
  keys.forEach((key, page) => client.setQueryData(key, { page }));
  await refreshQuantRun(client, 'a');
  expect(keys.map((key) => client.getQueryState(key)?.isInvalidated)).toEqual([
    true,
    true,
    false,
    false,
  ]);
  expect(client.getQueryData(keys[2])).not.toEqual(client.getQueryData(keys[3]));
  client.clear();
});

test('HTTP keeps API prefix, timeout, custom signal and same-origin cookie defaults', async () => {
  const originalFetch = globalThis.fetch;
  const originalTimeout = AbortSignal.timeout;
  const timeouts: number[] = [];
  const calls: { path: unknown; init?: RequestInit }[] = [];
  AbortSignal.timeout = (ms) => {
    timeouts.push(ms);
    return originalTimeout(ms);
  };
  globalThis.fetch = async (path, init) => {
    calls.push({ path, init });
    return Response.json({ ok: true });
  };
  try {
    expect(await request('/config')).toEqual({ ok: true });
    const controller = new AbortController();
    await request('/auth/login', {
      method: 'POST',
      signal: controller.signal,
      headers: { 'X-Test': 'yes' },
      body: '{}',
    });
    expect(calls[0].path).toBe('/api/config');
    expect(calls[0].init?.credentials).toBeUndefined();
    expect(calls[0].init?.signal).toBeInstanceOf(AbortSignal);
    expect(timeouts).toEqual([30000]);
    expect(calls[1].init?.signal).toBe(controller.signal);
    expect(calls[1].init?.headers).toEqual({ 'Content-Type': 'application/json', 'X-Test': 'yes' });
    expect(calls[1].init?.body).toBe('{}');
  } finally {
    globalThis.fetch = originalFetch;
    AbortSignal.timeout = originalTimeout;
  }
});

test('HTTP errors expose only string detail and fall back safely for invalid JSON', async () => {
  const original = globalThis.fetch;
  try {
    for (const [body, message] of [
      ['{"detail":"配置版本冲突"}', '配置版本冲突'],
      ['{"detail":[{"secret":"hidden"}]}', '请求失败（409）'],
      ['<html>private server error</html>', '请求失败（409）'],
    ]) {
      globalThis.fetch = async () => new Response(body, { status: 409 });
      await expect(request('/test')).rejects.toThrow(message);
    }
  } finally {
    globalThis.fetch = original;
  }
});

test('shared replay contract keeps retry history and replaces draft with validated report', () => {
  const fixture = JSON.parse(
    readFileSync(new URL('../../../tests/fixtures/agent-replay.json', import.meta.url), 'utf8'),
  );
  const events: JobEvent[] = fixture.events.map(
    (event: Pick<JobEvent, 'kind' | 'payload'>, index: number) => ({
      ...event,
      id: index + 1,
      created_at: '2026-01-01T00:00:00Z',
    }),
  );
  const beforeRetry = projectEvents(events.slice(0, 7));
  expect(beforeRetry.preview.insight).toBeUndefined();
  const result = projectEvents(events);
  expect(result.blocks.find((block) => block.id === '1:report')?.interrupted).toBe(
    fixture.expected.old_block_interrupted,
  );
  expect(result.blocks.find((block) => block.id === '2:report')?.done).toBe(
    fixture.expected.new_block_done,
  );
  expect(result.preview.summary).toBe(fixture.expected.summary);
  expect(result.preview.insight?.summary).toBe(fixture.expected.insight_summary);
});
