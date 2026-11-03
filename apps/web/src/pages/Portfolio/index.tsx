import { PositionTable } from '../../features/portfolio/PositionTable';
import { PositionEditor } from '../../features/portfolio/PositionEditor';
import { PositionImportPanel } from '../../features/portfolio/PositionImportPanel';
import { amount } from '../../features/portfolio/format';

import { portfolioQueries } from '../../features/portfolio/queries';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert } from 'antd';

import type { Position } from '../../api/portfolio';

import { ErrorNotice } from '../../components/ErrorNotice';

import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

export function PortfolioPage() {
  const [editing, setEditing] = useState<Position | null>(null);
  const data = useQuery({ ...portfolioQueries.current(), refetchInterval: 300000 });
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>POSITION RESEARCH</div>
          <h1>持仓分析</h1>
          <p>手动录入或 CSV 导入 · 参考盈亏 · T+1 可卖条件 · {data.data?.session.label}</p>
        </div>
      </div>
      <Alert
        type="warning"
        showIcon
        title={
          data.data?.is_demo ? '演示模式：持仓与公开模式分开保存' : '本页是研究账本，不连接券商'
        }
        description="输入每笔剩余数量和成本。ETF 须确认具体交易制度；无日历或行情时保留未知。点击“分析持仓”会把该证券的录入持仓纳入任务；选择 API 模型时会发送给你的模型服务。"
      />
      {data.error && <ErrorNotice error={data.error} retry={() => void data.refetch()} />}
      <section className={layout.stats}>
        <article>
          <span>录入成本</span>
          <strong>{amount(data.data?.cost_yuan ?? null)}</strong>
        </article>
        <article>
          <span>已知参考市值</span>
          <strong>{amount(data.data?.known_value_yuan ?? null)}</strong>
        </article>
        <article>
          <span>参考盈亏</span>
          <strong>{amount(data.data?.pnl_yuan ?? null)}</strong>
        </article>
        <article>
          <span>缺少行情的笔数</span>
          <strong>{data.data?.unknown_price_count ?? '—'}</strong>
        </article>
      </section>
      <PositionTable portfolio={data.data} onEdit={setEditing} />
      <PositionEditor
        editing={editing}
        isDemo={data.data?.is_demo}
        onDone={() => setEditing(null)}
      />
      <PositionImportPanel />
    </div>
  );
}
