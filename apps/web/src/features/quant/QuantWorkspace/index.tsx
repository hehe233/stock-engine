import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Select, Table, Tag } from 'antd';
import { Link } from 'react-router-dom';
import { api } from '../../../api/client';
import { quantApi } from '../../../api/quant';
import type { QuantDataset, QuantRun } from '../../../api/quant';
import { ErrorNotice } from '../../../components/ErrorNotice';
import { formatTime } from '../../../lib/format';
import { decimal, statusNames } from '../format';
import { DatasetAudit } from '../DatasetAudit';
import { DatasetImportPanel } from '../DatasetImportPanel';
import { ExperimentForm } from '../ExperimentForm';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

export function QuantWorkspace() {
  const client = useQueryClient();
  const datasets = useQuery({ queryKey: ['quant-datasets'], queryFn: quantApi.datasets });
  const runs = useQuery({
    queryKey: ['quant-runs'],
    queryFn: quantApi.runs,
    refetchInterval: (q) =>
      q.state.data?.items.some((r) => ['queued', 'running'].includes(r.status)) ? 3000 : 300000,
  });
  const config = useQuery({ queryKey: ['config'], queryFn: api.config });
  const [selected, setSelected] = useState<string>('');
  const selection = selected || datasets.data?.items[0]?.id;
  const current = datasets.data?.items.find((d) => d.id === selection);
  const invalidate = async (data: QuantDataset) => {
    setSelected(data.id);
    await client.invalidateQueries({ queryKey: ['quant-datasets'] });
  };
  const fromHistory = useMutation({ mutationFn: quantApi.history, onSuccess: invalidate });
  const fromDemo = useMutation({ mutationFn: quantApi.demo, onSuccess: invalidate });
  return (
    <div className={layout.pageStack}>
      <Alert
        type="warning"
        showIcon
        title="实验概率只对应明确事件与数据范围"
        description="本页验证未来 5 个数据集交易日收盘涨幅 ≥20% 的事件，不等于连板概率。精选案例、缺失历史成分与退市数据会限制泛化；所有版本仅用于研究，未发布交易模型。"
      />
      {[datasets.error, runs.error, fromHistory.error, fromDemo.error].map((e, i) =>
        e ? <ErrorNotice key={i} error={e} /> : null,
      )}
      <section className={`${layout.panel} ${layout.scopePanel}`}>
        <h2>1. 选择不可变数据版本</h2>
        <div className={styles.actions}>
          <Select
            aria-label="实验数据集"
            className={styles.datasetSelect}
            value={selection}
            onChange={setSelected}
            placeholder="导入或转换历史数据"
            options={datasets.data?.items.map((d) => ({
              value: d.id,
              label: d.name + ' · ' + formatTime(d.created_at),
            }))}
          />
          <Button onClick={() => fromHistory.mutate()} loading={fromHistory.isPending}>
            转换已归档历史案例
          </Button>
          {config.data?.market_provider === 'demo' && (
            <Button onClick={() => fromDemo.mutate()} loading={fromDemo.isPending}>
              创建合成实验集
            </Button>
          )}
        </div>
        {current && (
          <>
            <Tag color={current.is_demo ? 'orange' : 'blue'}>
              {current.is_demo ? '合成 / 演示数据' : current.source}
            </Tag>
            <DatasetAudit audit={current.details} />
            <details>
              <summary>证券范围与数据哈希</summary>
              <p className={styles.hash}>SHA-256：{current.checksum}</p>
              <Table
                rowKey="symbol"
                size="small"
                dataSource={current.details.symbols}
                pagination={{ pageSize: 10 }}
                scroll={{ x: 700 }}
                columns={[
                  { title: '证券', dataIndex: 'symbol' },
                  { title: '日线数', dataIndex: 'rows' },
                  { title: '首日', dataIndex: 'first' },
                  { title: '末日', dataIndex: 'last' },
                  { title: '上市日期声明', dataIndex: 'listed_on', render: (v) => v ?? '未知' },
                  { title: '退市日期声明', dataIndex: 'delisted_on', render: (v) => v ?? '未知' },
                ]}
              />
            </details>
          </>
        )}
        {!current && (
          <p>尚无量化数据集。可先转换 P2 历史案例，或按模板导入 CSV；合成数据仅在演示模式提供。</p>
        )}
      </section>
      <DatasetImportPanel onImported={invalidate} />
      <ExperimentForm selection={selection} />
      <section className={layout.panel}>
        <div className={layout.panelHeading}>
          <h2>实验版本与结果</h2>
        </div>
        <Table<QuantRun>
          rowKey="id"
          dataSource={runs.data?.items ?? []}
          scroll={{ x: 850 }}
          pagination={{ pageSize: 10 }}
          columns={[
            { title: '创建时间', dataIndex: 'created_at', render: formatTime },
            {
              title: '状态',
              dataIndex: 'status',
              render: (v: QuantRun['status']) => statusNames[v],
            },
            {
              title: '校准后 Brier（越小越好）',
              key: 'metric',
              render: (_, r) => decimal(r.result.metrics?.brier),
            },
            {
              title: '说明',
              key: 'note',
              render: (_, r) => r.error ?? r.result.stage ?? '冻结数据与参数',
            },
            {
              title: '结果',
              key: 'action',
              render: (_, r) => <Link to={'/quant/' + r.id}>查看实验</Link>,
            },
          ]}
        />
      </section>
    </div>
  );
}
