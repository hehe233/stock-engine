import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Form, Input, InputNumber, Select, Table, Tag } from 'antd';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { quantApi } from '../api/quant';
import type {
  DatasetAudit,
  DatasetInput,
  ExperimentInput,
  Metrics,
  QuantDataset,
  QuantRun,
  Backtest,
  Prediction,
} from '../api/quant';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatTime } from '../lib/format';
import styles from '../styles/Workbench.module.css';

const defaults = {
  train_days: 120,
  calibration_days: 60,
  test_days: 60,
  folds: 3,
  probability_threshold: 0.6,
  initial_cash: 100000,
  max_positions: 3,
  commission_bps: 3,
  slippage_bps: 10,
  participation: 0.01,
};
const pct = (value: number | null | undefined) =>
  value == null ? '未知' : (value * 100).toFixed(2) + '%';
const decimal = (value: number | null | undefined) => (value == null ? '未知' : value.toFixed(4));
const money = (value: number | null | undefined) =>
  value == null
    ? '未知'
    : new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(value);
const statusNames = {
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

function Audit({ audit }: { audit: DatasetAudit }) {
  return (
    <div>
      <p>
        {audit.rows.toLocaleString()} 行 · {audit.symbol_count} 只证券 · {audit.days} 个数据集交易日
        · {audit.first} 至 {audit.last}
      </p>
      <p>
        成交所需字段完整：{audit.executable_rows.toLocaleString()} 行；缺精确可见时间：
        {audit.missing_available_at.toLocaleString()} 行。
      </p>
      <ul>
        {audit.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
    </div>
  );
}

export function QuantPage() {
  const client = useQueryClient(),
    navigate = useNavigate();
  const datasets = useQuery({ queryKey: ['quant-datasets'], queryFn: quantApi.datasets });
  const runs = useQuery({
    queryKey: ['quant-runs'],
    queryFn: quantApi.runs,
    refetchInterval: (q) =>
      q.state.data?.items.some((r) => ['queued', 'running'].includes(r.status)) ? 3000 : 300000,
  });
  const config = useQuery({ queryKey: ['config'], queryFn: api.config });
  const [selected, setSelected] = useState<string>('');
  const [file, setFile] = useState('');
  const [fileError, setFileError] = useState<Error | null>(null);
  const [preview, setPreview] = useState<{ payload: DatasetInput; audit: DatasetAudit } | null>(
    null,
  );
  const [uploadForm] = Form.useForm<Omit<DatasetInput, 'content'>>();
  const [form] = Form.useForm<ExperimentInput>();
  const selection = selected || datasets.data?.items[0]?.id;
  const current = datasets.data?.items.find((d) => d.id === selection);
  const invalidate = async (data: QuantDataset) => {
    setSelected(data.id);
    await client.invalidateQueries({ queryKey: ['quant-datasets'] });
  };
  const fromHistory = useMutation({ mutationFn: quantApi.history, onSuccess: invalidate });
  const fromDemo = useMutation({ mutationFn: quantApi.demo, onSuccess: invalidate });
  const imported = useMutation({
    mutationFn: quantApi.import,
    onSuccess: async (data) => {
      setPreview(null);
      await invalidate(data);
    },
  });
  const check = useMutation({
    mutationFn: quantApi.preview,
    onSuccess: (audit, payload) => setPreview({ audit, payload }),
  });
  const create = useMutation({
    mutationFn: quantApi.create,
    onSuccess: (run) => {
      void client.invalidateQueries({ queryKey: ['quant-runs'] });
      void navigate('/quant/' + run.id);
    },
  });
  async function readFile(value?: File) {
    setPreview(null);
    setFile('');
    setFileError(null);
    if (!value) return;
    if (value.size > 20000000) {
      setFileError(new Error('CSV 最多 20 MB、100000 行'));
      return;
    }
    try {
      setFile(await value.text());
    } catch {
      setFileError(new Error('无法读取 CSV 文件'));
    }
  }
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <div className={styles.eyebrow}>QUANT RESEARCH LAB</div>
          <h1>策略与概率实验</h1>
          <p>未来 5 日涨幅 ≥20% · LightGBM · 滚动样本外验证 · T+1 成交模拟</p>
        </div>
      </div>
      <Alert
        type="warning"
        showIcon
        title="实验概率只对应明确事件与数据范围"
        description="本页验证未来 5 个数据集交易日收盘涨幅 ≥20% 的事件，不等于连板概率。精选案例、缺失历史成分与退市数据会限制泛化；所有版本仅用于研究，未发布交易模型。"
      />
      {[
        datasets.error,
        runs.error,
        fromHistory.error,
        fromDemo.error,
        imported.error,
        check.error,
        create.error,
        fileError,
      ].map((e, i) => (e ? <ErrorNotice key={i} error={e} /> : null))}
      <section className={`${styles.panel} ${styles.scopePanel}`}>
        <h2>1. 选择不可变数据版本</h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Select
            aria-label="实验数据集"
            style={{ width: 420, maxWidth: '100%' }}
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
            <Audit audit={current.details} />
            <details>
              <summary>证券范围与数据哈希</summary>
              <p style={{ overflowWrap: 'anywhere' }}>SHA-256：{current.checksum}</p>
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
      <section className={`${styles.panel} ${styles.scopePanel}`}>
        <h2>导入自有日线 CSV</h2>
        <a href="/api/quant/template" download>
          下载量化 CSV 模板
        </a>
        <p>
          UTF-8，至少 30 行。OHLC
          必填；成交量单位为股，实际涨跌停价及交易状态留空时拒绝模拟成交。日期使用
          YYYY-MM-DD，available_at 需带时区。
        </p>
        <Form
          form={uploadForm}
          layout="vertical"
          initialValues={{ adjustment: 'raw', selection: 'manual' }}
          onValuesChange={() => setPreview(null)}
          onFinish={(values) => check.mutate({ ...values, content: file })}
          style={{ maxWidth: 680 }}
        >
          <Form.Item label="数据集名称" name="name" rules={[{ required: true }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item label="数据来源说明" name="source" rules={[{ required: true }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item label="价格口径" name="adjustment">
            <Select
              options={[
                { value: 'raw', label: '不复权（交易仍需实际限制字段）' },
                { value: 'qfq', label: '前复权（仅概率研究）' },
              ]}
            />
          </Form.Item>
          <Form.Item label="证券选择依据" name="selection">
            <Select
              options={[
                { value: 'manual', label: '人工选择 / 案例目录' },
                { value: 'historical_universe', label: '提供者声明为历史范围（系统尚未核验）' },
              ]}
            />
          </Form.Item>
          <input
            aria-label="量化日线 CSV"
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => void readFile(e.target.files?.[0])}
          />
          <Button htmlType="submit" disabled={!file} loading={check.isPending}>
            校验并预览
          </Button>
        </Form>
        {preview && (
          <>
            <Audit audit={preview.audit} />
            <Button
              type="primary"
              loading={imported.isPending}
              onClick={() => imported.mutate(preview.payload)}
            >
              确认保存数据版本
            </Button>
          </>
        )}
      </section>
      <section className={`${styles.panel} ${styles.scopePanel}`}>
        <h2>2. 固定参数并创建实验</h2>
        <p>
          每折按日期分为训练、校准、测试。训练和校准末尾的跨区间标签被剔除；下一折向前移动一个测试窗口。样本不足或任一类别过少会拒绝训练。
        </p>
        <Form<ExperimentInput>
          form={form}
          layout="vertical"
          initialValues={defaults}
          style={{ maxWidth: 680 }}
          onFinish={(v) => selection && create.mutate({ ...v, dataset_id: selection })}
        >
          {(
            [
              ['train_days', '训练区天数', 60, 1000],
              ['calibration_days', '校准区天数', 20, 250],
              ['test_days', '每折测试天数', 20, 250],
              ['folds', '滚动折数', 1, 6],
              ['probability_threshold', '交易概率阈值', 0.05, 0.95],
              ['initial_cash', '初始资金（元）', 10000, 100000000],
              ['max_positions', '最多同时持仓', 1, 10],
              ['commission_bps', '双边佣金（基点，另有最低 5 元）', 0, 100],
              ['slippage_bps', '单边滑点（基点）', 0, 100],
              ['participation', '整日成交量参与率上限', 0.0001, 0.1],
            ] as const
          ).map(([name, label, min, max]) => (
            <Form.Item key={name} name={name} label={label} rules={[{ required: true }]}>
              <InputNumber
                min={min}
                max={max}
                step={max <= 1 ? 0.01 : 1}
                style={{ width: 240, maxWidth: '100%' }}
              />
            </Form.Item>
          ))}
          <Button type="primary" htmlType="submit" loading={create.isPending} disabled={!selection}>
            创建滚动实验
          </Button>
        </Form>
      </section>
      <section className={styles.panel}>
        <div className={styles.panelHeading}>
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

function BacktestReport({ value }: { value: Backtest }) {
  const curve = value.curve ?? [];
  const min = Math.min(...curve.map((p) => p.equity)),
    max = Math.max(...curve.map((p) => p.equity));
  const points = curve
    .map(
      (p, i) =>
        `${30 + (i / Math.max(curve.length - 1, 1)) * 740},${210 - ((p.equity - min) / Math.max(max - min, 1)) * 180}`,
    )
    .join(' ');
  return (
    <section className={`${styles.panel} ${styles.scopePanel}`}>
      <h2>成交约束与资金曲线</h2>
      {!value.enabled ? (
        <Alert type="warning" title={value.reason} />
      ) : (
        <>
          <p>
            参考总收益 {value.return_pct == null ? '未知' : value.return_pct.toFixed(2) + '%'} ·
            最大回撤{' '}
            {value.max_drawdown_pct == null ? '未知' : value.max_drawdown_pct.toFixed(2) + '%'} ·
            完成交易 {value.trade_count} · 费用 {money(value.fees)}
          </p>
          {curve.length > 0 && (
            <figure style={{ margin: 0 }}>
              <svg
                role="img"
                aria-label="样本外交易模拟参考资金曲线"
                viewBox="0 0 800 240"
                style={{ width: '100%', maxHeight: 280 }}
              >
                <title>
                  参考权益，最低 {money(min)}，最高 {money(max)}
                </title>
                <line x1="30" y1="210" x2="770" y2="210" stroke="#ccd5e3" />
                <polyline points={points} fill="none" stroke="var(--brand)" strokeWidth="2" />
              </svg>
              <figcaption>
                {curve[0].date} 至 {curve[curve.length - 1].date}；最低 {money(min)}，最高{' '}
                {money(max)}。
              </figcaption>
            </figure>
          )}
          <ul>
            {value.warnings?.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
          <p>
            未平仓：
            {value.open_positions?.map((p) => `${p.symbol} ${p.quantity} 股`).join('；') || '无'}
            。估值完整：{value.valuation_complete ? '是（仍受数据范围限制）' : '否，总收益不展示'}。
          </p>
          <details>
            <summary>成交拒绝原因</summary>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(value.rejected, null, 2)}</pre>
          </details>
          <h3>逐笔模拟交易</h3>
          <Table
            rowKey={(r) => r.symbol + r.buy_date}
            size="small"
            dataSource={value.trades}
            pagination={{ pageSize: 10 }}
            scroll={{ x: 1000 }}
            columns={[
              { title: '证券', dataIndex: 'symbol' },
              { title: '信号日', dataIndex: 'signal_date' },
              { title: '买入日', dataIndex: 'buy_date' },
              { title: '卖出日', dataIndex: 'sell_date' },
              { title: '股数', dataIndex: 'quantity' },
              { title: '毛盈亏', dataIndex: 'gross_pnl', render: money },
              { title: '费用', dataIndex: 'fees', render: money },
              { title: '净盈亏', dataIndex: 'net_pnl', render: money },
            ]}
          />
          <h3>按证券收益归因</h3>
          <Table
            rowKey="symbol"
            size="small"
            dataSource={value.attribution}
            pagination={{ pageSize: 10 }}
            scroll={{ x: 650 }}
            columns={[
              { title: '证券', dataIndex: 'symbol' },
              { title: '完成交易', dataIndex: 'trades' },
              { title: '毛盈亏', dataIndex: 'gross_pnl', render: money },
              { title: '费用', dataIndex: 'fees', render: money },
              { title: '净盈亏', dataIndex: 'net_pnl', render: money },
            ]}
          />
        </>
      )}
    </section>
  );
}

export function QuantRunPage() {
  const { id = '' } = useParams();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const run = useQuery({
    queryKey: ['quant-run', id],
    queryFn: () => quantApi.run(id),
    refetchInterval: (q) =>
      q.state.data && ['queued', 'running'].includes(q.state.data.status) ? 2000 : false,
  });
  const predictions = useQuery({
    queryKey: ['quant-predictions', id, page],
    queryFn: () => quantApi.predictions(id, page),
    enabled: run.data?.status === 'succeeded',
  });
  const cancel = useMutation({
    mutationFn: () => quantApi.cancel(id),
    onSuccess: () => client.invalidateQueries({ queryKey: ['quant-run', id] }),
  });
  const result = run.data?.result;
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <div className={styles.eyebrow}>EXPERIMENT REPORT</div>
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
          <section className={`${styles.panel} ${styles.scopePanel}`}>
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
          <section className={`${styles.panel} ${styles.scopePanel}`}>
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
          <section className={`${styles.panel} ${styles.scopePanel}`}>
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
        <section className={`${styles.panel} ${styles.scopePanel}`}>
          <h2>版本与复现信息</h2>
          <p>
            实验 ID：{id} · 创建 {formatTime(run.data.created_at)}
          </p>
          <p style={{ overflowWrap: 'anywhere' }}>
            数据 SHA-256：{result?.dataset_checksum}
            <br />
            计算代码 SHA-256：{result?.code_sha256}
          </p>
          <p>
            计算版本 {result?.engine_version} · 特征版本 {result?.feature_version}
          </p>
          <details>
            <summary>参数、依赖和末折特征重要性</summary>
            <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
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
