import { useEffect, useRef, useState, type ReactNode, type PointerEvent } from 'react';
import { Button, Drawer } from 'antd';
import { FileTextOutlined, RightOutlined } from '@ant-design/icons';
import type { AnalysisReport, ReportPreview, ResearchJob } from '../../api/types';
import { GeneratedReport } from './GeneratedReport';
import { IconParkFont } from './IconParkFont';
import styles from './ReportWorkspace.module.css';

const STORAGE_KEY = 'stock-engine-report-drawer-width';
const MIN_WIDTH = 320;

function storedWidth() {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null');
    if (
      value &&
      typeof value === 'object' &&
      'width' in value &&
      'user' in value &&
      value.user === true &&
      typeof value.width === 'number' &&
      Number.isFinite(value.width)
    ) {
      return Math.max(MIN_WIDTH, Math.min(948, value.width));
    }
  } catch {
    /* Storage can be unavailable in private browsing. */
  }
  return 640;
}

export function ReportWorkspace({
  children,
  preview,
  report,
  job,
}: {
  children: ReactNode;
  preview: ReportPreview;
  report?: AnalysisReport;
  job: ResearchJob;
}) {
  const container = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const focusFrame = useRef(0);
  const drag = useRef<{ x: number; width: number; current: number; moved: boolean } | null>(null);
  const [containerWidth, setContainerWidth] = useState(window.innerWidth - 56);
  const [width, setWidth] = useState(storedWidth);
  const [dragWidth, setDragWidth] = useState<number | null>(null);
  const [selection, setSelection] = useState<boolean | null>(null);
  const mobile = containerWidth < 850;
  const hasReport = Boolean(report || preview.summary || preview.factors || preview.insight);
  const open = selection ?? (hasReport && !mobile);
  const limit = Math.max(MIN_WIDTH, Math.min(948, containerWidth - 420 - 20));
  const displayedWidth = dragWidth ?? Math.min(width, limit);
  const active = ['queued', 'running'].includes(job.status);
  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver((entries) =>
      setContainerWidth(entries[0].contentRect.width),
    );
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => () => cancelAnimationFrame(focusFrame.current), []);

  const close = () => {
    setSelection(false);
    cancelAnimationFrame(focusFrame.current);
    // Also restore after a quick close that interrupts the opening animation.
    focusFrame.current = requestAnimationFrame(() =>
      opener.current?.focus({ preventScroll: true }),
    );
  };
  const saveWidth = (value: number) => {
    setWidth(value);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ width: Math.round(value), user: true }));
    } catch {
      /* Optional preference. */
    }
  };
  const endDrag = (event: PointerEvent<HTMLDivElement>, cancelled = false) => {
    const current = drag.current;
    if (!current) return;
    drag.current = null;
    setDragWidth(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
    if (cancelled || !current.moved) return;
    if (current.current < MIN_WIDTH - 80) close();
    else saveWidth(Math.max(MIN_WIDTH, Math.min(limit, current.current)));
  };
  const document = <GeneratedReport preview={preview} report={report} job={job} />;
  return (
    <div ref={container} className={styles.workspace} data-dragging={dragWidth !== null}>
      <div className={styles.main}>
        {children}
        <button
          ref={opener}
          type="button"
          className={styles.artifact}
          onClick={() => setSelection(true)}
          aria-expanded={open}
          aria-controls="research-report-drawer"
        >
          <span className={styles.documentIcon}>
            <IconParkFont type="icon-fuwenben_fasongwenjian" />
          </span>
          <span className={styles.fileInfo}>
            <strong>{report?.name ?? job.symbol} · 研究报告</strong>
            <small>
              {report
                ? 'Document · 已保存'
                : active
                  ? 'Document · 正在生成'
                  : 'Document · 未完成草稿'}
            </small>
          </span>
          <span className={styles.openLabel}>
            {open ? '正在查看' : '查看报告'}
            <RightOutlined />
          </span>
        </button>
      </div>
      {mobile ? (
        <Drawer
          title="研究报告"
          open={open}
          onClose={close}
          afterOpenChange={(visible) => {
            cancelAnimationFrame(focusFrame.current);
            if (!visible)
              focusFrame.current = requestAnimationFrame(() =>
                opener.current?.focus({ preventScroll: true }),
              );
          }}
          focusable={{ trap: true, focusTriggerAfterClose: false }}
          size="100%"
          destroyOnHidden
          closable={{ 'aria-label': '收起报告抽屉' }}
          styles={{ body: { padding: 0, background: '#f7f8fc' } }}
        >
          <div id="research-report-drawer">{document}</div>
        </Drawer>
      ) : (
        <aside
          id="research-report-drawer"
          className={styles.drawer}
          style={{ width: open ? displayedWidth : 0 }}
          data-open={open}
          data-dragging={dragWidth !== null}
          aria-label="研究报告抽屉"
          aria-hidden={!open}
          inert={!open}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              close();
            }
          }}
        >
          <div className={styles.drawerContent}>
            <header className={styles.header}>
              <span className={styles.headerIcon}>
                <FileTextOutlined />
              </span>
              <strong>研究报告</strong>
              <span>{active ? '实时生成' : report ? '已保存' : '草稿'}</span>
              <Button
                type="text"
                size="small"
                aria-label="收起报告抽屉"
                icon={<IconParkFont type="icon-cebianchoutizhankaishouqi" />}
                onClick={close}
              />
            </header>
            <div className={styles.body}>{document}</div>
          </div>
          <div
            className={styles.handle}
            role="separator"
            aria-label="调整报告抽屉宽度"
            aria-orientation="vertical"
            aria-valuemin={MIN_WIDTH}
            aria-valuemax={limit}
            aria-valuenow={Math.round(displayedWidth)}
            tabIndex={open ? 0 : -1}
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              event.preventDefault();
              event.currentTarget.setPointerCapture(event.pointerId);
              drag.current = {
                x: event.clientX,
                width: displayedWidth,
                current: displayedWidth,
                moved: false,
              };
            }}
            onPointerMove={(event) => {
              const current = drag.current;
              if (!current) return;
              current.current = current.width + current.x - event.clientX;
              current.moved ||= Math.abs(current.x - event.clientX) > 4;
              if (current.moved)
                setDragWidth(
                  current.current < MIN_WIDTH - 80
                    ? 0
                    : Math.max(MIN_WIDTH, Math.min(limit, current.current)),
                );
            }}
            onPointerUp={(event) => endDrag(event)}
            onPointerCancel={(event) => endDrag(event, true)}
            onKeyDown={(event) => {
              const amount = event.key === 'ArrowLeft' ? 32 : event.key === 'ArrowRight' ? -32 : 0;
              if (amount || event.key === 'Home' || event.key === 'End') {
                event.preventDefault();
                saveWidth(
                  event.key === 'Home'
                    ? MIN_WIDTH
                    : event.key === 'End'
                      ? limit
                      : Math.max(MIN_WIDTH, Math.min(limit, displayedWidth + amount)),
                );
              }
            }}
          >
            <span />
          </div>
        </aside>
      )}
    </div>
  );
}
