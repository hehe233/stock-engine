import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Input, Table, Tag } from 'antd';
import type { TableColumnsType } from 'antd';
import { researchApi } from '../../../../api/research';
import type { ResearchQuery, ResearchRow } from '../../../../api/research';
import { ErrorNotice } from '../../../../components/ErrorNotice';
import { formatAmount, formatTime } from '../../../../lib/format';

import { titles } from '../../titles';
import { SourceNotice } from '../SourceNotice';

import layout from '../../../../styles/Workbench.module.css';
import styles from './index.less';

const amount = (value?: number | null) => formatAmount(value ?? null);
const display = (value?: string | number | null) => value ?? '未提供';
export function ResearchDataset({ query }: { query: ResearchQuery }) {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [seat, setSeat] = useState<string | null>(null);
  const client = useQueryClient();
  const data = useQuery({
    queryKey: ['research', query, search, page],
    queryFn: () => researchApi.data(query, search, page),
    refetchInterval: (q) =>
      ['queued', 'running'].includes(q.state.data?.request?.status ?? '') ? 5000 : 300000,
  });
  const refresh = useMutation({
    mutationFn: () => researchApi.refresh(query),
    onSuccess: () => client.invalidateQueries({ queryKey: ['research'] }),
  });
  const pending =
    refresh.isPending || ['queued', 'running'].includes(data.data?.request?.status ?? '');
  const base: TableColumnsType<ResearchRow> = [
    {
      title: '证券',
      key: 'symbol',
      width: 165,
      render: (_, row) => (
        <div>
          <strong>{row.name}</strong>
          <br />
          {row.symbol}
        </div>
      ),
    },
  ];
  const financial = ['buy_yuan', 'sell_yuan', 'net_yuan'] as const;
  const columns: TableColumnsType<ResearchRow> =
    query.kind === 'ladder'
      ? [
          ...base,
          { title: '连板数', dataIndex: 'boards', render: display },
          { title: '行业', dataIndex: 'sector', render: display },
          { title: '封板资金', dataIndex: 'seal_yuan', render: amount },
          { title: '成交额', dataIndex: 'amount_yuan', render: amount },
          { title: '炸板次数', dataIndex: 'break_count', render: display },
          {
            title: '首次 / 最后封板',
            key: 'time',
            render: (_, r) => `${r.first_seal ?? '未知'} / ${r.last_seal ?? '未知'}`,
          },
        ]
      : query.kind === 'dragon' || query.kind === 'seats'
        ? [
            ...(query.kind === 'dragon'
              ? base
              : [
                  { title: '席位原名', dataIndex: 'seat', width: 320 },
                  { title: '榜单方向', dataIndex: 'side' },
                ]),
            ...financial.map((key, i) => ({
              title: ['买入额', '卖出额', '净买额'][i],
              dataIndex: key,
              render: amount,
            })),
            { title: '上榜原因 / 类型', dataIndex: 'reason', width: 320 },
            ...(query.kind === 'dragon'
              ? [
                  {
                    title: '席位',
                    key: 'action',
                    render: (_: unknown, r: ResearchRow) => (
                      <Button type="link" onClick={() => setSeat(r.symbol!)}>
                        查看席位
                      </Button>
                    ),
                  },
                ]
              : []),
          ]
        : query.kind === 'flow'
          ? [
              ...base,
              {
                title: '较上一观测主力净额变化',
                dataIndex: 'change_since_previous_yuan',
                render: amount,
              },
              ...(
                ['main_yuan', 'super_yuan', 'large_yuan', 'medium_yuan', 'small_yuan'] as const
              ).map((key, i) => ({
                title: ['主力净额', '超大单', '大单', '中单', '小单'][i],
                dataIndex: key,
                render: amount,
              })),
              { title: '主力净占比 %', dataIndex: 'main_pct', render: display },
            ]
          : query.kind === 'history'
            ? [
                { title: '交易日期', dataIndex: 'date' },
                { title: '前复权收盘价', dataIndex: 'close', render: display },
              ]
            : [
                ...base,
                { title: '公告日期', dataIndex: 'date' },
                { title: '类型', dataIndex: 'category' },
                {
                  title: '公告标题（非全文）',
                  key: 'title',
                  width: 500,
                  render: (_, r) =>
                    r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer">
                        {r.title}
                      </a>
                    ) : (
                      r.title
                    ),
                },
              ];
  const snapshot = data.data?.snapshot;
  return (
    <div className={layout.pageStack}>
      <section className={layout.panel}>
        <div className={layout.panelHeading}>
          <h2>
            {titles[query.kind]}
            {query.symbol ? ` · ${query.symbol}` : ''}
          </h2>
          <Button loading={pending} onClick={() => refresh.mutate()}>
            采集 / 更新{pending ? '（排队执行）' : ''}
          </Button>
        </div>
        <div className={styles.inset}>
          <Input
            aria-label="搜索研究数据"
            placeholder="搜索代码、名称或证据文字"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        {data.error && <ErrorNotice error={data.error} retry={() => void data.refetch()} />}
        {refresh.error && <ErrorNotice error={refresh.error} />}
        {data.data?.request?.status === 'failed' && (
          <Alert
            type="error"
            showIcon
            title={data.data.request.error ?? '采集失败'}
            description="继续保留旧批次；同一查询五分钟内不会重复采集。"
          />
        )}
        {!snapshot && (
          <Alert
            type="info"
            title={
              pending
                ? '后台正在排队或采集，可稍后回来查看。'
                : '暂无本日期数据，请点击采集；空结果不代表没有事件。'
            }
          />
        )}
        {query.kind === 'ladder' && data.data?.summary.tiers && (
          <div className={styles.inset}>
            {data.data.summary.tiers.map((t) => (
              <Tag key={t.boards} color="blue">
                {t.boards} 板 · {t.count} 只
              </Tag>
            ))}
            <p>
              本批最高连板观察对象：{data.data.summary.leaders?.join('、') || '暂无'}
              （不等于确定龙头）
            </p>
            <p>
              行业聚合：
              {data.data.summary.sectors
                ?.map((s) => `${s.sector} ${s.count}只 / 最高${s.max_boards}板`)
                .join('；')}
            </p>
            <p>
              行业联动观察：
              {data.data.summary.comparison_date
                ? `对照已存 ${data.data.summary.comparison_date} 批次`
                : '尚无近期较早日期批次，无法判断行业扩散变化'}
              。
              {data.data.summary.sectors
                ?.filter((s) => s.count_change !== null)
                .map(
                  (s) => `${s.sector} 数量变化 ${s.count_change! >= 0 ? '+' : ''}${s.count_change}`,
                )
                .join('；')}
            </p>
          </div>
        )}
        {query.kind === 'flow' && (
          <div className={styles.inset}>
            上一观测：{formatTime(data.data?.summary.previous_observed_at ?? null)}
            。差额仅为同源累计统计的观测变化，源日期未知时不能认定为盘中真实新增资金；无上批时保持未知。
          </div>
        )}
        <Table<ResearchRow>
          rowKey="id"
          columns={columns}
          dataSource={snapshot?.rows ?? []}
          size="small"
          loading={data.isFetching}
          scroll={{ x: 1000 }}
          pagination={{
            current: page,
            pageSize: 50,
            total: data.data?.total ?? 0,
            showSizeChanger: false,
            onChange: setPage,
          }}
          locale={{
            emptyText: snapshot ? '本次来源未返回匹配记录；不代表市场没有该事件' : '等待研究数据',
          }}
        />
        {snapshot && <SourceNotice snapshot={snapshot} />}
      </section>
      {seat && (
        <>
          <Button onClick={() => setSeat(null)}>收起席位明细</Button>
          <ResearchDataset key={seat} query={{ kind: 'seats', date: query.date, symbol: seat }} />
        </>
      )}
    </div>
  );
}
