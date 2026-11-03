import { researchQueries, invalidateResearch } from '../../features/research/queries';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Table, Tag } from 'antd';
import type { TableColumnsType } from 'antd';
import { researchApi } from '../../api/research';
import type { HistoryCase, WindowStats } from '../../api/research';
import { ResearchDataset } from '../../features/research/components/ResearchDataset';
import { ErrorNotice } from '../../components/ErrorNotice';

import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

function WindowCell({ value }: { value: WindowStats | null | undefined }) {
  if (!value) return <span>暂无符合条件的窗口</span>;
  return (
    <div>
      <strong>{value.return_pct.toFixed(2)}%</strong>
      <br />
      <small>
        {value.start} → {value.end}
        <br />
        窗口最大回撤 {value.drawdown_pct.toFixed(2)}%
      </small>
    </div>
  );
}
export function HistoryPage() {
  const client = useQueryClient();
  const [selected, setSelected] = useState<HistoryCase | null>(null);
  const history = useQuery(researchQueries.history());
  const collect = useMutation({
    mutationFn: async (items: HistoryCase[]) => {
      for (const item of items)
        await researchApi.refresh({ kind: 'history', date: item.end, case_id: item.id });
    },
    onSuccess: () => invalidateResearch(client),
  });
  const columns: TableColumnsType<HistoryCase> = [
    { title: '年度', dataIndex: 'year', width: 75 },
    {
      title: '观察对象（人工目录）',
      key: 'name',
      width: 160,
      render: (_, r) => (
        <div>
          {r.name}
          <br />
          <small>{r.symbol}</small>
        </div>
      ),
    },
    {
      title: '日线覆盖',
      key: 'coverage',
      width: 200,
      render: (_, r) =>
        r.statistics ? (
          <div>
            {r.statistics.bars} 条<br />
            {r.statistics.first_date} → {r.statistics.last_date}
            <br />
            {r.snapshot?.is_demo && <Tag color="orange">虚构演示日线</Tag>}
          </div>
        ) : (
          '尚未获取'
        ),
    },
    {
      title: '最强 20 交易日窗口',
      key: 'strong',
      width: 230,
      render: (_, r) => <WindowCell value={r.statistics?.strong} />,
    },
    {
      title: '同期失败对照窗口',
      key: 'failure',
      width: 230,
      render: (_, r) => <WindowCell value={r.statistics?.failure} />,
    },
    {
      title: '状态 / 操作',
      key: 'action',
      width: 200,
      render: (_, r) => (
        <div>
          <Button
            type="link"
            loading={
              ['queued', 'running'].includes(r.request?.status ?? '') ||
              (collect.isPending && collect.variables?.some((i) => i.id === r.id))
            }
            onClick={() => collect.mutate([r])}
          >
            获取日线
          </Button>
          <Button type="link" onClick={() => setSelected(r)} disabled={!r.snapshot}>
            查看数据
          </Button>
          {r.request?.status === 'failed' && <p>{r.request.error}</p>}
        </div>
      ),
    },
  ];
  const items = history.data?.items ?? [];
  const ready = items.filter((r) => r.statistics);
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>HISTORICAL CASES</div>
          <h1>近十年历史案例</h1>
          <p>2016—2025 十个完整年度 · 人工观察目录 · 同期强势与失败窗口对照</p>
        </div>
        <Button
          loading={collect.isPending}
          disabled={!items.length}
          onClick={() => collect.mutate(items)}
        >
          依次获取十年日线
        </Button>
      </div>
      <Alert
        type="warning"
        showIcon
        title="案例研究不等于妖股概率回测"
        description="同一证券同一年，统一比较 20 个交易日的收盘到收盘变化及窗口最大回撤；窗口有重叠、对象是事后选择，不能把统计比例当胜率。缺失数据不补造收益。"
      />
      {history.error && <ErrorNotice error={history.error} retry={() => void history.refetch()} />}
      {collect.error && <ErrorNotice error={collect.error} />}
      {collect.isSuccess && (
        <Alert type="info" title="采集请求已入队，后台逐个执行；失败原因会显示在对应行。" />
      )}
      <section className={layout.panel}>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          pagination={false}
          scroll={{ x: 1200 }}
        />
      </section>
      <section className={`${layout.panel} ${layout.scopePanel}`}>
        <h2>本库可观察到的规律与边界</h2>
        <p>
          已有日线的年度：{ready.length} / 10；出现负收益 20 日窗口的年度：
          {ready.filter((r) => r.statistics!.negative_count > 0).length}
          。这是目录内描述，不能外推到全市场。
        </p>
        <ul>
          {history.data?.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
        <p>
          先检查同一标的强势后的回撤、持有期敏感性和缺失覆盖，再考虑策略规则。仅凭涨幅、连板或知名案例无法确认稳定可复制的规律。
        </p>
      </section>
      {selected && (
        <ResearchDataset
          key={selected.id}
          query={{ kind: 'history', date: selected.end, case_id: selected.id }}
        />
      )}
    </div>
  );
}
