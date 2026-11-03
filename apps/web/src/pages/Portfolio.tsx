import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Form, Input, InputNumber, Select, Table } from 'antd';
import type { TableColumnsType } from 'antd';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { researchApi, shanghaiToday } from '../api/research';
import type { ImportPreview, Position, PositionInput } from '../api/research';
import type { AnalysisMode } from '../api/types';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatTime } from '../lib/format';
import styles from '../styles/Workbench.module.css';

const emptyLot = (): PositionInput => ({
  symbol: '',
  name: '',
  asset_type: 'stock',
  quantity: 100,
  cost_price: '',
  acquired_on: shanghaiToday(),
  settlement: 'T1',
  note: '',
});
// 个人持仓按元显示，避免用行情资金的「亿元」单位把小额盈亏四舍五入为零。
const yuan = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' });
const amount = (n: number | null) => (n == null ? '—' : yuan.format(n));
export function PortfolioPage() {
  const [form] = Form.useForm<PositionInput>();
  const [editing, setEditing] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [fileError, setFileError] = useState<Error | null>(null);
  const [selection, setSelection] = useState('');
  const [reading, setReading] = useState(false);
  const client = useQueryClient(),
    navigate = useNavigate();
  const data = useQuery({
    queryKey: ['portfolio'],
    queryFn: researchApi.portfolio,
    refetchInterval: 300000,
  });
  const config = useQuery({ queryKey: ['config'], queryFn: api.config });
  const invalidate = () => client.invalidateQueries({ queryKey: ['portfolio'] });
  const save = useMutation({
    mutationFn: async (row: PositionInput) => {
      if (editing) await researchApi.update(editing, row);
      else await researchApi.import([row]);
    },
    onSuccess: () => {
      setEditing(null);
      form.resetFields();
      void invalidate();
    },
  });
  const load = useMutation({
    mutationFn: researchApi.import,
    onSuccess: () => {
      setPreview(null);
      void invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: researchApi.remove,
    onSuccess: () => {
      setRemoving(null);
      void invalidate();
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
      return api.createJob(
        row.symbol,
        row.quote_snapshot_id!,
        mode,
        split < 0 ? undefined : choice.slice(split + 1),
        true,
      );
    },
    onSuccess: (job) => {
      void navigate('/jobs/' + job.id);
    },
  });
  async function readFile(file?: File) {
    setPreview(null);
    setFileError(null);
    if (!file) return;
    if (file.size > 200000) {
      setFileError(new Error('CSV 文件不能超过 200 KB'));
      return;
    }
    setReading(true);
    try {
      setPreview(await researchApi.preview(await file.text()));
    } catch (error) {
      setFileError(error instanceof Error ? error : new Error('文件读取失败'));
    } finally {
      setReading(false);
    }
  }
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
              setEditing(r.id);
              form.setFieldsValue(r);
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
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <div className={styles.eyebrow}>POSITION RESEARCH</div>
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
      {[data.error, save.error, load.error, remove.error, analyze.error, fileError].map(
        (error, i) => (error ? <ErrorNotice key={i} error={error} /> : null),
      )}
      <section className={styles.stats}>
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
      <section className={styles.panel}>
        <div className={styles.panelHeading}>
          <h2>我的持仓</h2>
          <Select
            aria-label="持仓分析模型"
            style={{ minWidth: 210, maxWidth: '100%' }}
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
          dataSource={data.data?.items ?? []}
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
        <div style={{ padding: 16 }}>
          {data.data?.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      </section>
      <section className={`${styles.panel} ${styles.scopePanel}`}>
        <h2>{editing ? '编辑持仓' : '添加持仓'}</h2>
        <Form<PositionInput>
          form={form}
          layout="vertical"
          initialValues={emptyLot()}
          onFinish={(v) => save.mutate(v)}
          style={{ maxWidth: 650 }}
        >
          <Form.Item label="证券代码" name="symbol" rules={[{ required: true }]}>
            <Input placeholder={data.data?.is_demo ? 'DEMO001' : '600000.SH'} />
          </Form.Item>
          <Form.Item label="证券名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="证券类型" name="asset_type">
            <Select
              options={[
                { value: 'stock', label: 'A 股' },
                { value: 'etf', label: 'ETF' },
              ]}
              onChange={(value) =>
                form.setFieldValue('settlement', value === 'stock' ? 'T1' : 'unknown')
              }
            />
          </Form.Item>
          <Form.Item label="剩余数量" name="quantity" rules={[{ required: true }]}>
            <InputNumber min={1} max={1000000000} precision={0} />
          </Form.Item>
          <Form.Item label="每份成本" name="cost_price" rules={[{ required: true }]}>
            <InputNumber stringMode min="0.0001" precision={4} />
          </Form.Item>
          <Form.Item label="买入日期" name="acquired_on" rules={[{ required: true }]}>
            <Input type="date" max={shanghaiToday()} />
          </Form.Item>
          <Form.Item label="确认交易制度" name="settlement">
            <Select
              options={[
                { value: 'T1', label: 'T+1' },
                { value: 'T0', label: 'T+0（仅适用已核验 ETF）' },
                { value: 'unknown', label: 'ETF 制度未知' },
              ]}
            />
          </Form.Item>
          <Form.Item label="备注" name="note">
            <Input maxLength={300} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={save.isPending}>
            保存持仓
          </Button>
          {editing && (
            <Button
              onClick={() => {
                setEditing(null);
                form.resetFields();
              }}
            >
              取消编辑
            </Button>
          )}
        </Form>
        {save.isSuccess && (
          <Alert
            type="success"
            title="持仓已保存；完全相同的重复行会跳过。"
            style={{ marginTop: 12 }}
          />
        )}
      </section>
      <section className={`${styles.panel} ${styles.scopePanel}`}>
        <h2>CSV 导入</h2>
        <a href="/api/portfolio/template" download>
          下载 CSV 模板
        </a>
        <p>UTF-8 编码，最多 500 行。先核对预览，再确认追加；不会覆盖已有持仓。</p>
        <input
          aria-label="导入持仓 CSV"
          type="file"
          accept=".csv,text/csv"
          disabled={reading}
          onChange={(e) => void readFile(e.target.files?.[0])}
        />
        {reading && <p role="status">正在校验 CSV…</p>}
        {preview && (
          <div>
            <p>
              有效行 {preview.count}，错误 {preview.errors.length}。
            </p>
            {preview.errors.map((e) => (
              <p key={e.line}>
                第 {e.line} 行：{e.message}
              </p>
            ))}
            <Table
              rowKey={(_, i) => String(i)}
              size="small"
              dataSource={preview.rows}
              columns={[
                { title: '代码', dataIndex: 'symbol' },
                { title: '数量', dataIndex: 'quantity' },
                { title: '成本', dataIndex: 'cost_price' },
                { title: '日期', dataIndex: 'acquired_on' },
                { title: '制度', dataIndex: 'settlement' },
              ]}
              scroll={{ x: 650 }}
              pagination={{ pageSize: 10 }}
            />
            <Button
              type="primary"
              disabled={!preview.valid}
              loading={load.isPending}
              onClick={() => load.mutate(preview.rows)}
            >
              确认追加导入
            </Button>
          </div>
        )}
        {load.isSuccess && (
          <Alert
            type="success"
            title={`导入 ${load.data.inserted} 行，跳过重复 ${load.data.skipped} 行`}
          />
        )}
      </section>
    </div>
  );
}
