import { lazy, StrictMode, Suspense, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { App } from './App';
import { Dashboard } from './pages/Dashboard';
import { AuthGate } from './components/AuthGate';
import './styles/global.css';
import { workspaceTheme } from './styles/theme';

const QuantPage = lazy(() =>
  import('./pages/Quant').then((module) => ({ default: module.QuantPage })),
);
const QuantRunPage = lazy(() =>
  import('./pages/QuantRun').then((module) => ({ default: module.QuantRunPage })),
);

const ReportsPage = lazy(() =>
  import('./pages/Reports').then((module) => ({ default: module.ReportsPage })),
);
const ReportPage = lazy(() =>
  import('./pages/Report').then((module) => ({ default: module.ReportPage })),
);
const JobsPage = lazy(() =>
  import('./pages/Jobs').then((module) => ({ default: module.JobsPage })),
);
const JobPage = lazy(() => import('./pages/Job').then((module) => ({ default: module.JobPage })));
const Roadmap = lazy(() =>
  import('./pages/Roadmap').then((module) => ({ default: module.Roadmap })),
);
const ModelSettingsPage = lazy(() =>
  import('./pages/ModelSettings').then((module) => ({ default: module.ModelSettingsPage })),
);
const ResearchPage = lazy(() =>
  import('./pages/Research').then((module) => ({ default: module.ResearchPage })),
);
const PortfolioPage = lazy(() =>
  import('./pages/Portfolio').then((module) => ({ default: module.PortfolioPage })),
);
const HistoryPage = lazy(() =>
  import('./pages/History').then((module) => ({ default: module.HistoryPage })),
);

// Keep loading inside the route outlet, so the persistent shell and auth gate stay mounted.
function routeView(view: ReactNode) {
  return <Suspense fallback={<p role="status">正在加载页面…</p>}>{view}</Suspense>;
}

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
      { path: 'reports', element: routeView(<ReportsPage />) },
      { path: 'reports/:id', element: routeView(<ReportPage />) },
      { path: 'roadmap', element: routeView(<Roadmap />) },
      { path: 'jobs', element: routeView(<JobsPage />) },
      { path: 'jobs/:id', element: routeView(<JobPage />) },
      { path: 'settings/models', element: routeView(<ModelSettingsPage />) },
      { path: 'research', element: routeView(<ResearchPage />) },
      { path: 'portfolio', element: routeView(<PortfolioPage />) },
      { path: 'history', element: routeView(<HistoryPage />) },
      {
        path: 'quant',
        element: (
          <Suspense fallback={<p role="status">正在加载实验工作台…</p>}>
            <QuantPage />
          </Suspense>
        ),
      },
      {
        path: 'quant/:id',
        element: (
          <Suspense fallback={<p role="status">正在加载实验报告…</p>}>
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
