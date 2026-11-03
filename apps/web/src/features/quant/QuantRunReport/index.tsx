import { quantQueries, refreshQuantRun, invalidateQuantRuns } from '../queries';
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Table } from 'antd';
import { Link } from 'react-router-dom';
import { quantApi } from '../../../api/quant';
import type { Metrics, Prediction } from '../../../api/quant';
import { ErrorNotice } from '../../../components/ErrorNotice';
import { formatTime } from '../../../lib/format';
import { pct, decimal, statusNames } from '../format';
import { BacktestReport } from '../BacktestReport';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

function MetricsTable({ rows }: { rows: ({ name: string } & Metrics)[] }) {
  return (
    <Table
      rowKey="name"
      size="small"
      dataSource={rows}
      pagination={false}
      scroll={{ x: 850 }}
      columns={[
        { title: '预测版本', dataIndex: 'name' },
        { title: '样本数', dataIndex: 'count' },
        { title: '实际发生率', dataIndex: 'event_rate', render: pct },
        { title: 'Brier ↓', dataIndex: 'brier', render: decimal },
        { title: 'Log loss ↓', dataIndex: 'log_loss', render: decimal },
        { title: 'AUC ↑', dataIndex: 'auc', render: decimal },
        { title: 'ECE ↓', dataIndex: 'ece', render: decimal },
      ]}
    />
  );
}

export function QuantRunReport({ id }: { id: string }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const run = useQuery(quantQueries.run(id));
  const predictions = useQuery({
    ...quantQueries.predictions(id, page),
    enabled: run.data?.status === 'succeeded',
  });
  const cancel = useMutation({
    mutationFn: () => quantApi.cancel(id),
    onSuccess: () => refreshQuantRun(client, id),
  });
  const result = run.data?.result;
  const status = run.data?.status;
  useEffect(() => {
    if (status && ['succeeded', 'failed', 'cancelled'].includes(status)) {
      void invalidateQuantRuns(client);
    }
  }, [client, id, status]);
  return (
    <div className={layout.pageStack}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>EXPERIMENT REPORT</div>
          <h1>量化实验报告</h1>
          <p>
            {run.data ? statusNames[run.data.status] : '加载中'} · {result?.stage}
          </p>
        </div>
        <Link to="/quant">返回实验工作台</Link>
      </div>
      {[run.error, cancel.error, predictions.error].map((e, i) =>
        e ? <ErrorNotice key={i} error={e} /> : null,
      )}
      {run.data?.error && <Alert type="error" title={run.data.error} />}
      {run.data && ['queued', 'running'].includes(run.data.status) && (
        <Button
          danger
          loading={cancel.isPending || run.data.cancel_requested}
          onClick={() => cancel.mutate()}
        >
          取消实验
        </Button>
      )}
      <Alert
        type="warning"
        showIcon
        title={
          run.data?.is_demo ? '这是合成数据实验，不代表市场效果' : '仅为冻结数据上的样本外研究结果'
        }
        description="校准概率对应未来 5 日收盘涨幅 ≥20%，不能读作当前证券的连板概率。反复查看测试集后调参会引入选择偏差。"
      />
      {result?.metrics && (
        <>
          <section className={`${layout.panel} ${layout.scopePanel}`}>
            <h2>样本外预测与校准</h2>
            <p>
              {result.target} · 有效特征标签 {result.usable_samples} 行 · 剔除{' '}
              {result.excluded_rows} 行
            </p>
            <MetricsTable
              rows={[
                { name: '校准后', ...result.metrics },
                ...(result.raw_metrics ? [{ name: '校准前', ...result.raw_metrics }] : []),
                ...(result.baseline_metrics
                  ? [{ name: '各折校准区发生率基准', ...result.baseline_metrics }]
                  : []),
              ]}
            />
            <h3>校准分箱（预测与实际发生率）</h3>
            <Table
              rowKey="lower"
              size="small"
              pagination={false}
              dataSource={result.metrics.bins}
              scroll={{ x: 600 }}
              columns={[
                {
                  title: '预测区间',
                  key: 'range',
                  render: (_, r) => pct(r.lower) + ' — ' + pct(r.upper),
                },
                { title: '样本数', dataIndex: 'count' },
                { title: '平均预测', dataIndex: 'predicted', render: pct },
                { title: '实际发生率', dataIndex: 'observed', render: pct },
              ]}
            />
          </section>
          <section className={`${layout.panel} ${layout.scopePanel}`}>
            <h2>滚动分区与误差追踪</h2>
            <p>
              完成 {result.folds?.length} / 请求 {result.requested_folds}{' '}
              折。标签结束日必须早于下一分区起始日。
            </p>
            {result.skipped_folds?.map((f) => (
              <p key={f.fold}>
                第 {f.fold} 折跳过：{f.reason}
              </p>
            ))}
            <Table
              rowKey="fold"
              size="small"
              dataSource={result.folds}
              pagination={false}
              scroll={{ x: 1000 }}
              columns={[
                { title: '折', dataIndex: 'fold' },
                {
                  title: '训练信号期',
                  key: 'train',
                  render: (_, r) => r.train_start + ' 至 ' + r.train_end,
                },
                { title: '训练标签最晚日', dataIndex: 'train_label_end' },
                {
                  title: '校准期',
                  key: 'cal',
                  render: (_, r) => r.calibration_start + ' 至 ' + r.calibration_end,
                },
                { title: '校准标签最晚日', dataIndex: 'calibration_label_end' },
                {
                  title: '测试期',
                  key: 'test',
                  render: (_, r) => r.test_start + ' 至 ' + r.test_end,
                },
                { title: '测试 Brier', key: 'metric', render: (_, r) => decimal(r.metrics.brier) },
              ]}
            />
            <h3>按月误差</h3>
            <Table
              rowKey="month"
              size="small"
              dataSource={result.monthly_errors}
              pagination={{ pageSize: 12 }}
              scroll={{ x: 650 }}
              columns={[
                { title: '月份', dataIndex: 'month' },
                { title: '样本数', dataIndex: 'count' },
                { title: '正例', dataIndex: 'positives' },
                { title: 'Brier', dataIndex: 'brier', render: decimal },
                { title: 'ECE', dataIndex: 'ece', render: decimal },
              ]}
            />
          </section>
          {result.backtest && <BacktestReport value={result.backtest} />}
          <section className={`${layout.panel} ${layout.scopePanel}`}>
            <h2>逐条样本外预测</h2>
            <Table<Prediction>
              rowKey={(r) => r.symbol + r.date}
              dataSource={predictions.data?.items ?? []}
              scroll={{ x: 900 }}
              pagination={{
                current: page,
                pageSize: 50,
                total: predictions.data?.total ?? 0,
                onChange: setPage,
                showSizeChanger: false,
              }}
              columns={[
                { title: '信号日', dataIndex: 'date' },
                { title: '证券', dataIndex: 'symbol' },
                { title: '事件窗口结束', dataIndex: 'label_end' },
                { title: '校准概率', dataIndex: 'probability', render: pct },
                { title: '实际事件', dataIndex: 'label', render: (v) => (v ? '发生' : '未发生') },
                { title: '实际收盘收益', dataIndex: 'future_return', render: pct },
                { title: '折', dataIndex: 'fold' },
              ]}
            />
          </section>
        </>
      )}
      {run.data && (
        <section className={`${layout.panel} ${layout.scopePanel}`}>
          <h2>版本与复现信息</h2>
          <p>
            实验 ID：{id} · 创建 {formatTime(run.data.created_at)}
          </p>
          <p className={styles.hash}>
            数据 SHA-256：{result?.dataset_checksum}
            <br />
            计算代码 SHA-256：{result?.code_sha256}
          </p>
          <p>
            计算版本 {result?.engine_version} · 特征版本 {result?.feature_version}
          </p>
          <details>
            <summary>参数、依赖和末折特征重要性</summary>
            <pre className={styles.json}>
              {JSON.stringify(
                {
                  params: run.data.params,
                  dependencies: result?.dependencies,
                  importance: result?.importance,
                },
                null,
                2,
              )}
            </pre>
          </details>
          {run.data.status === 'succeeded' && (
            <p>
              <a href={`/api/quant/runs/${id}/artifacts/models.json`} download>
                下载各折模型文本与校准参数
              </a>
              {' · '}
              <a href={`/api/quant/runs/${id}/artifacts/predictions.parquet`} download>
                下载样本外预测 Parquet
              </a>
            </p>
          )}
          <ul>
            {result?.warnings?.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
