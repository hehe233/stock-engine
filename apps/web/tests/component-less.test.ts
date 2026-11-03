import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
import { build, createServer, preview } from 'vite';

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const runtime = resolve(webRoot, '../../.runtime');
await mkdir(runtime, { recursive: true });
const output = await mkdtemp(join(runtime, 'p0-less-'));
const fixture = await mkdtemp(join(webRoot, 'src/__less_test_'));
const configFile = join(webRoot, 'vite.config.ts');
const entry = join(fixture, 'index.html');
const relative = fixture.slice(webRoot.length).split(String.fromCharCode(92)).join('/');
let dev: Awaited<ReturnType<typeof createServer>> | undefined;
let production: Awaited<ReturnType<typeof preview>> | undefined;
let browser: Awaited<ReturnType<typeof chromium.launch>> | undefined;

async function save(path: string, content: string) {
  const target = join(fixture, path);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, content);
}

const styleA = (color: string) =>
  '@import "./tokens.less"; .root { color: ' +
  color +
  '; padding-left: @space; background-image: url("./pixel.svg"); .child { font-weight: 700; } }';

try {
  await save('A/index.less', styleA('rgb(1, 2, 3)'));
  await save('A/tokens.less', '@space: 11px;');
  await save(
    'A/pixel.svg',
    '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><path fill="red" d="M0 0h2v2H0z"/></svg>',
  );
  await save('B/index.less', '.root { color: rgb(4, 5, 6); }');
  await save('legacy.module.css', '.root { margin-left: 7px; }');
  await save('global.css', 'body { margin: 0; }');
  await save(
    'Fixture.tsx',
    [
      "import React from 'react';",
      "import { ErrorNotice } from '../components/ErrorNotice';",
      "import a from './A/index.less';",
      "import b from './B/index.less';",
      "import legacy from './legacy.module.css';",
      "import './global.css';",
      "export function Fixture() { return <><div id='a' className={a.root}><span className={a.child}>A</span></div><div id='b' className={b.root}>B</div><div id='legacy' className={legacy.root}>Legacy</div><ErrorNotice error={new Error('离线验证错误消息')} retry={() => { document.getElementById('result').textContent = 'retried'; }} /><span id='result' /></>; }",
    ].join(String.fromCharCode(10)),
  );
  await save(
    'main.tsx',
    "import React from 'react'; import {createRoot} from 'react-dom/client'; import {Fixture} from './Fixture'; createRoot(document.getElementById('root')).render(<Fixture />);",
  );
  await writeFile(
    entry,
    '<!doctype html><html><body><div id="root"></div><script type="module" src="./main.tsx"></script></body></html>',
  );
  dev = await createServer({
    root: webRoot,
    configFile,
    server: { host: '127.0.0.1', port: 0, strictPort: false, open: false },
  });
  await dev.listen();
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(dev.resolvedUrls!.local[0] + relative.slice(1) + '/index.html');
  await page.locator('#a').waitFor();
  const state = () =>
    page.evaluate(() => {
      const a = document.getElementById('a')!;
      const b = document.getElementById('b')!;
      return {
        a: a.className,
        b: b.className,
        colorA: getComputedStyle(a).color,
        colorB: getComputedStyle(b).color,
        padding: getComputedStyle(a).paddingLeft,
        weight: getComputedStyle(a.firstElementChild!).fontWeight,
        margin: getComputedStyle(document.getElementById('legacy')!).marginLeft,
        background: getComputedStyle(a).backgroundImage,
      };
    });
  const initial = await state();
  assert.notEqual(initial.a, initial.b);
  assert.equal(initial.colorA, 'rgb(1, 2, 3)');
  assert.equal(initial.colorB, 'rgb(4, 5, 6)');
  assert.equal(initial.padding, '11px');
  assert.equal(initial.weight, '700');
  assert.equal(initial.margin, '7px');
  const asset = initial.background.slice(5, -2);
  assert.ok(
    await page.evaluate(
      (url) =>
        new Promise<boolean>((done) => {
          const image = new Image();
          image.onload = () => done(image.naturalWidth === 2);
          image.onerror = () => done(false);
          image.src = url;
        }),
      asset,
    ),
  );
  await page.getByRole('button', { name: '重试' }).click();
  assert.equal(await page.locator('#result').textContent(), 'retried');
  await page.evaluate(() => (document.body.dataset.hmrSentinel = 'preserved'));
  await save('A/index.less', styleA('rgb(7, 8, 9)'));
  await page.waitForFunction(
    () => getComputedStyle(document.getElementById('a')!).color === 'rgb(7, 8, 9)',
  );
  await save('A/tokens.less', '@space: 23px;');
  await page.waitForFunction(
    () => getComputedStyle(document.getElementById('a')!).paddingLeft === '23px',
  );
  assert.equal(await page.evaluate(() => document.body.dataset.hmrSentinel), 'preserved');
  assert.equal((await state()).colorB, 'rgb(4, 5, 6)');
  await page.setViewportSize({ width: 375, height: 812 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.screenshot({ path: join(output, 'less-mobile.png') });
  await dev.close();
  dev = undefined;
  const dist = join(output, 'dist');
  await build({
    root: webRoot,
    configFile,
    logLevel: 'warn',
    build: {
      outDir: dist,
      emptyOutDir: true,
      assetsInlineLimit: 0,
      rollupOptions: { input: entry },
    },
  });
  production = await preview({
    root: webRoot,
    configFile,
    build: { outDir: dist },
    preview: { host: '127.0.0.1', port: 0, strictPort: false, open: false },
  });
  assert.ok(production.resolvedUrls);
  await page.goto(production.resolvedUrls.local[0] + relative.slice(1) + '/index.html');
  await page.locator('#a').waitFor();
  const built = await state();
  assert.equal(built.colorA, 'rgb(7, 8, 9)');
  assert.equal(built.padding, '23px');
  assert.notEqual(built.a, built.b);
  assert.equal(built.margin, '7px');
  assert.equal((await page.request.get(built.background.slice(5, -2))).status(), 200);
  const html = await readFile(join(dist, relative.slice(1), 'index.html'), 'utf8');
  assert.ok(html.includes('stylesheet'));
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({
      passed: [
        'module isolation',
        'Less nesting/imports',
        'asset URLs',
        'legacy CSS coexistence',
        'component retry',
        'HMR without reload',
        'imported Less HMR',
        'mobile layout',
        'production CSS extraction',
      ],
      output,
    }),
  );
} finally {
  await browser?.close();
  await dev?.close();
  if (production)
    await new Promise<void>((done, reject) =>
      production!.httpServer.close((error) => (error ? reject(error) : done())),
    );
  await rm(fixture, { recursive: true, force: true });
}
