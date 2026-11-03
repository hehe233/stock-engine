import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Drawer } from 'antd';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  AppstoreOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  RadarChartOutlined,
  SettingOutlined,
  WalletOutlined,
  CompassOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { api } from './api/client';
import { IconParkFont } from './components/agent/IconParkFont';
import styles from './styles/AppShell.module.css';

function RadarLogo() {
  return (
    <span className={styles.brandMark} aria-hidden="true">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="1em"
        height="1em"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M19.07 4.93A10 10 0 0 0 6.99 3.34" />
        <path d="M4 6h.01" />
        <path d="M2.29 9.62A10 10 0 1 0 21.31 8.35" />
        <path d="M16.24 7.76A6 6 0 1 0 8.23 16.67" />
        <path d="M12 18h.01" />
        <path d="M17.99 11.66A6 6 0 0 1 15.77 16.67" />
        <circle cx="12" cy="12" r="2" />
        <path d="m13.41 10.59 5.66-5.66" />
      </svg>
    </span>
  );
}

const groups = [
  {
    label: '研究空间',
    items: [
      { to: '/', label: '行情工作台', icon: <AppstoreOutlined /> },
      { to: '/research', label: '短线研究', icon: <RadarChartOutlined /> },
      { to: '/portfolio', label: '持仓分析', icon: <WalletOutlined /> },
      { to: '/quant', label: '策略实验', icon: <ExperimentOutlined /> },
    ],
  },
  {
    label: '研究记录',
    items: [
      { to: '/jobs', label: '研究任务', icon: <IconParkFont type="icon-agent-linear" /> },
      { to: '/reports', label: '分析记录', icon: <FileTextOutlined /> },
      { to: '/history', label: '历史案例', icon: <HistoryOutlined /> },
    ],
  },
  {
    label: '工作区设置',
    items: [
      { to: '/settings/models', label: '模型设置', icon: <SettingOutlined /> },
      { to: '/roadmap', label: '开发路线', icon: <CompassOutlined /> },
    ],
  },
];
function preference(key: string, fallback: number) {
  try {
    const raw = localStorage.getItem(key);
    const value = raw === null ? NaN : Number(raw);
    return Number.isFinite(value) ? value : fallback;
  } catch {
    return fallback;
  }
}
function remember(key: string, value: number) {
  try {
    localStorage.setItem(key, String(value));
  } catch {
    /* Optional local preference. */
  }
}

export function App() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => preference('stock-sidebar-collapsed', 0) === 1);
  const [width, setWidth] = useState(() =>
    Math.max(200, Math.min(260, preference('stock-sidebar-width', 224))),
  );
  const [dragging, setDragging] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const focusFrame = useRef(0);
  const main = useRef<HTMLElement>(null);
  const drag = useRef<{ x: number; width: number; next: number } | null>(null);
  const jobs = useQuery({
    queryKey: ['jobs'],
    queryFn: api.jobs,
    refetchInterval: 15000,
    retry: false,
  });
  const activeRoute = groups
    .flatMap((group) => group.items)
    .find((item) =>
      item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to),
    );
  const researching = /^\/jobs\/[^/]+$/.test(location.pathname);
  useEffect(() => {
    main.current?.scrollTo({ top: 0 });
  }, [location.pathname]);
  useEffect(() => () => cancelAnimationFrame(focusFrame.current), []);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const change = () => {
      if (media.matches) setMobileOpen(false);
    };
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    remember('stock-sidebar-collapsed', Number(next));
  };
  const closeMobile = () => {
    setMobileOpen(false);
    cancelAnimationFrame(focusFrame.current);
    focusFrame.current = requestAnimationFrame(() =>
      menuButton.current?.focus({ preventScroll: true }),
    );
  };
  const navigation = (compact: boolean, mobile = false) => (
    <>
      <div className={styles.brand}>
        {compact ? (
          <button
            type="button"
            className={styles.railBrand}
            onClick={toggle}
            aria-label="展开侧边栏"
            title="展开侧边栏"
          >
            <RadarLogo />
            <MenuUnfoldOutlined className={styles.railBrandIcon} />
          </button>
        ) : (
          <RadarLogo />
        )}
        {!compact && (
          <div>
            <strong>Stock Engine</strong>
          </div>
        )}
        {!mobile && !compact && (
          <button
            type="button"
            className={styles.collapse}
            onClick={toggle}
            aria-label={compact ? '展开侧边栏' : '收起侧边栏'}
            title={compact ? '展开侧边栏' : '收起侧边栏'}
          >
            {compact ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
        )}
      </div>
      <div className={styles.sidebarContent}>
        <NavLink
          to="/"
          className={styles.newResearch}
          aria-label="开始新的研究"
          title={compact ? '开始新的研究' : undefined}
          onClick={() => setMobileOpen(false)}
        >
          <PlusOutlined />
          {!compact && <span>开始研究</span>}
        </NavLink>
        <nav className={styles.navigation} aria-label={mobile ? '移动导航' : '主导航'}>
          {groups.map((group) => (
            <div className={styles.navGroup} key={group.label}>
              {!compact && <div className={styles.groupLabel}>{group.label}</div>}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  aria-label={item.label}
                  title={compact ? item.label : undefined}
                  className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
                  onClick={() => setMobileOpen(false)}
                >
                  <span className={styles.navIcon}>{item.icon}</span>
                  {!compact && <span>{item.label}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        {!compact && (
          <section className={styles.recent} aria-label="最近研究">
            <div className={styles.groupLabel}>最近研究</div>
            {jobs.data?.items.slice(0, 4).map((job) => (
              <NavLink
                to={`/jobs/${job.id}`}
                key={job.id}
                className={styles.recentItem}
                onClick={() => setMobileOpen(false)}
              >
                <span data-status={job.status} />
                <span>
                  {job.symbol}
                  <small>{job.model_name ?? '规则分析'}</small>
                </span>
                <RightOutlined />
              </NavLink>
            ))}
            {!jobs.data?.items.length && (
              <p>
                {jobs.isPending
                  ? '正在同步任务…'
                  : jobs.error
                    ? '打开研究任务查看记录'
                    : '从行情工作台开启首次研究'}
              </p>
            )}
          </section>
        )}
      </div>
      <div className={styles.sidebarBottom}>
        <span className={styles.workspaceAvatar}>S</span>
        {!compact && (
          <div>
            <strong>本地研究空间</strong>
            <small>Stock Engine · P3</small>
          </div>
        )}
      </div>
    </>
  );
  return (
    <div
      className={styles.shell}
      style={{ '--sidebar-width': `${collapsed ? 64 : width}px` } as CSSProperties}
      data-collapsed={collapsed}
      data-dragging={dragging}
    >
      <a className={styles.skipLink} href="#workspace-main">
        跳转至主要内容
      </a>
      <aside className={styles.sidebar} aria-label="工作区侧边栏">
        {navigation(collapsed)}
        {!collapsed && (
          <div
            className={styles.resizeHandle}
            role="separator"
            aria-label="调整侧边栏宽度"
            aria-orientation="vertical"
            aria-valuemin={200}
            aria-valuemax={260}
            aria-valuenow={width}
            tabIndex={0}
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              event.preventDefault();
              event.currentTarget.setPointerCapture(event.pointerId);
              drag.current = { x: event.clientX, width, next: width };
              setDragging(true);
            }}
            onPointerMove={(event) => {
              const current = drag.current;
              if (current) {
                current.next = Math.round(
                  Math.max(200, Math.min(260, current.width + event.clientX - current.x)),
                );
                setWidth(current.next);
              }
            }}
            onPointerUp={(event) => {
              if (drag.current) remember('stock-sidebar-width', drag.current.next);
              drag.current = null;
              setDragging(false);
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onPointerCancel={() => {
              if (drag.current) setWidth(drag.current.width);
              drag.current = null;
              setDragging(false);
            }}
            onKeyDown={(event) => {
              const delta = event.key === 'ArrowRight' ? 16 : event.key === 'ArrowLeft' ? -16 : 0;
              if (delta) {
                event.preventDefault();
                const next = Math.max(200, Math.min(260, width + delta));
                setWidth(next);
                remember('stock-sidebar-width', next);
              }
            }}
          >
            <span />
          </div>
        )}
      </aside>
      <div className={styles.workspace}>
        <header className={styles.topbar}>
          <button
            ref={menuButton}
            type="button"
            className={styles.mobileMenu}
            aria-label="打开导航菜单"
            onClick={() => setMobileOpen(true)}
          >
            <MenuUnfoldOutlined />
          </button>
          <div className={styles.breadcrumb}>
            <span>研究空间</span>
            <RightOutlined />
            <strong>{researching ? 'Agent 分析' : (activeRoute?.label ?? '工作台')}</strong>
          </div>
          <div className={styles.topbarMeta}>
            <span className={styles.version}>P3 · 研究验证版</span>
            <span className={styles.timezone}>北京时间 UTC+8</span>
          </div>
        </header>
        <main
          ref={main}
          id="workspace-main"
          className={styles.main}
          tabIndex={-1}
          data-researching={researching}
        >
          <div key={location.pathname} className={styles.pageContent}>
            <Outlet />
          </div>
          <footer className={styles.footer}>
            <span>Stock Engine</span>
            <span>公开行情存在延迟与缺失 · 研究结果不构成交易指令</span>
          </footer>
        </main>
      </div>
      <Drawer
        title="研究空间"
        placement="left"
        size={280}
        open={mobileOpen}
        onClose={closeMobile}
        destroyOnHidden
        closable={{ 'aria-label': '关闭导航菜单' }}
        focusable={{ trap: true, focusTriggerAfterClose: false }}
        afterOpenChange={(open) => {
          cancelAnimationFrame(focusFrame.current);
          if (!open)
            focusFrame.current = requestAnimationFrame(() =>
              menuButton.current?.focus({ preventScroll: true }),
            );
        }}
        styles={{ body: { padding: 0, background: 'var(--surface-sidebar)' } }}
      >
        <div className={styles.mobileSidebar}>{navigation(false, true)}</div>
      </Drawer>
    </div>
  );
}
