import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { App } from './App';
import { Dashboard } from './pages/Dashboard';
import { ReportsPage, ReportPage } from './pages/Reports';
import { Roadmap } from './pages/Roadmap';
import { JobsPage, JobPage } from './pages/Jobs';
import { AuthGate } from './components/AuthGate';
import { ModelSettingsPage } from './pages/ModelSettings';
import { ResearchPage } from './pages/Research';
import { PortfolioPage } from './pages/Portfolio';
import { HistoryPage } from './pages/History';
import './styles/global.css';
import { workspaceTheme } from './styles/theme';

const QuantPage = lazy(() =>
  import('./pages/Quant').then((module) => ({ default: module.QuantPage })),
);
const QuantRunPage = lazy(() =>
  import('./pages/QuantRun').then((module) => ({ default: module.QuantRunPage })),
);

// 服务端状态交给 Query 管理；筛选词等临时交互状态留在组件中。
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 }, mutations: { retry: false } },
});

const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <AuthGate>
        <App />
      </AuthGate>
    ),
    errorElement: (
      <main className="fallback">
        <h1>页面暂时不可用</h1>
        <a href="/">返回工作台</a>
      </main>
    ),
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'reports/:id', element: <ReportPage /> },
      { path: 'roadmap', element: <Roadmap /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'jobs/:id', element: <JobPage /> },
      { path: 'settings/models', element: <ModelSettingsPage /> },
      { path: 'research', element: <ResearchPage /> },
      { path: 'portfolio', element: <PortfolioPage /> },
      { path: 'history', element: <HistoryPage /> },
      {
        path: 'quant',
        element: (
          <Suspense fallback={<p>正在加载实验工作台…</p>}>
            <QuantPage />
          </Suspense>
        ),
      },
      {
        path: 'quant/:id',
        element: (
          <Suspense fallback={<p>正在加载实验报告…</p>}>
            <QuantRunPage />
          </Suspense>
        ),
      },
      {
        path: '*',
        element: (
          <main className="fallback">
            <h1>页面不存在</h1>
            <a href="/">返回工作台</a>
          </main>
        ),
      },
    ],
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={zhCN} theme={workspaceTheme}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ConfigProvider>
  </StrictMode>,
);
