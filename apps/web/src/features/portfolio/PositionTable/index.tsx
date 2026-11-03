import { configQueries } from '../../config/queries';
import { invalidateJobs } from '../../jobs/queries';
import { invalidatePortfolio } from '../queries';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Select, Table } from 'antd';
import type { TableColumnsType } from 'antd';
import { useNavigate } from 'react-router-dom';

import { jobsApi } from '../../../api/jobs';
import { portfolioApi } from '../../../api/portfolio';

import type { Position } from '../../../api/portfolio';
import type { AnalysisMode } from '../../../api/types';
import { ErrorNotice } from '../../../components/ErrorNotice';
import { formatTime } from '../../../lib/format';
import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

import type { Portfolio } from '../../../api/portfolio';
import { amount } from '../format';
export function PositionTable({
  portfolio,
  onEdit,
}: {
  portfolio?: Portfolio;
  onEdit: (position: Position) => void;
}) {
  const [removing, setRemoving] = useState<string | null>(null);
  const [selection, setSelection] = useState('');
  const client = useQueryClient();
  const navigate = useNavigate();
  const config = useQuery(configQueries.current());
  const remove = useMutation({
    mutationFn: portfolioApi.remove,
    onSuccess: () => {
      setRemoving(null);
      void invalidatePortfolio(client);
    },
  });
  const choice =
    selection ||
    (config.data?.api_configured
      ? 'api:' + (config.data.default_model || config.data.api_models[0])
      : 'rules');
  const analyze = useMutation({
    mutationFn: (row: Position) => {
      const split = choice.indexOf(':');
      const mode = (split < 0 ? 'rules' : choice.slice(0, split)) as AnalysisMode;
      return jobsApi.createJob(
        row.symbol,
        row.quote_snapshot_id!,
        mode,
        split < 0 ? undefined : choice.slice(split + 1),
        true,
      );
    },
    onSuccess: (job) => {
      void invalidateJobs(client);
      void navigate('/jobs/' + job.id);
    },
  });
  const columns: TableColumnsType<Position> = [
    {
      title: '证券 / 买入日期',
      key: 'symbol',
      width: 170,
      render: (_, r) => (
        <div>
          <strong>{r.name}</strong>
          <br />
          {r.symbol}
          <br />
          {r.acquired_on}
        </div>
      ),
    },
    { title: '剩余数量', dataIndex: 'quantity' },
    {
      title: '成本 / 参考价',
      key: 'price',
      render: (_, r) => `${r.cost_price} / ${r.price ?? '未知'}`,
    },
    { title: '参考市值', dataIndex: 'value_yuan', render: amount },
    { title: '参考盈亏', dataIndex: 'pnl_yuan', render: amount },
    {
      title: '可卖估计',
      key: 'sellable',
      render: (_, r) => (
        <span>
          {r.sellable ?? '未知'}
          <br />
          <small>{r.settlement}</small>
        </span>
      ),
    },
    {
      title: '条件分析',
      key: 'conditions',
      width: 330,
      render: (_, r) => (
        <ul>
          {r.conditions.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      render: (_, r) => (
        <div>
          <Button
            type="link"
            onClick={() => {
              onEdit(r);
            }}
          >
            编辑
          </Button>
          <Button type="link" danger onClick={() => setRemoving(r.id)}>
            删除
          </Button>
          {removing === r.id && (
            <Button danger onClick={() => remove.mutate(r.id)} loading={remove.isPending}>
              确认删除该笔
            </Button>
          )}
          <Button
            type="link"
            aria-label={'分析持仓 ' + r.symbol}
            disabled={!r.quote_snapshot_id || r.price === null}
            loading={analyze.isPending && analyze.variables?.id === r.id}
            onClick={() => analyze.mutate(r)}
          >
            分析持仓
          </Button>
        </div>
      ),
    },
  ];
  return (
    <section className={layout.panel}>
      {remove.error && <ErrorNotice error={remove.error} />}
      {analyze.error && <ErrorNotice error={analyze.error} />}
      <div className={layout.panelHeading}>
        <h2>我的持仓</h2>
        <Select
          aria-label="持仓分析模型"
          className={styles.modelSelect}
          value={choice}
          onChange={setSelection}
          options={[
            { value: 'rules', label: '规则条件分析' },
            ...(config.data?.api_configured
              ? config.data.api_models.map((n) => ({ value: 'api:' + n, label: 'API · ' + n }))
              : []),
            { value: 'ollama:' + config.data?.ollama_model, label: 'Ollama 备选' },
          ]}
        />
      </div>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={portfolio?.items ?? []}
        scroll={{ x: 1300 }}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        expandable={{
          expandedRowRender: (r) => (
            <p>
              源时间：{formatTime(r.quote_time)} · 采集：{formatTime(r.fetched_at)} · 备注：
              {r.note || '无'}
            </p>
          ),
        }}
      />
      <div className={styles.warnings}>
        {portfolio?.warnings.map((w) => (
          <p key={w}>{w}</p>
        ))}
      </div>
    </section>
  );
}
