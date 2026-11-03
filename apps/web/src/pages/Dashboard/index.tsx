import { QuoteTable } from '../../features/market/QuoteTable';
import { invalidateJobs } from '../../features/jobs/queries';
import { marketQueries, invalidateMarketStatus } from '../../features/market/queries';
import { configQueries } from '../../features/config/queries';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { Alert, Button, Input, Select, Tag } from 'antd';
import type { TableProps } from 'antd';
import { Link, useNavigate } from 'react-router-dom';

import { marketApi } from '../../api/market';
import { jobsApi } from '../../api/jobs';
import type { AnalysisMode, AssetType, Quote } from '../../api/types';
import { ErrorNotice } from '../../components/ErrorNotice';
import { formatTime } from '../../lib/format';
import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

const assetNames = { stock: 'A 股', etf: 'ETF', index: '指数' };

export function Dashboard() {
  const [asset, setAsset] = useState<AssetType>('stock');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({ field: 'change_pct', descending: true });
  const [selection, setSelection] = useState('');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const config = useQuery(configQueries.current());
  const status = useQuery({ ...marketQueries.status(), refetchInterval: 5000 });
  const params = new URLSearchParams({
    asset_type: asset,
    page: String(page),
    page_size: '50',
    search,
    sort_by: sort.field,
    descending: String(sort.descending),
  });
  const collecting = status.data?.collection[asset].status === 'running';
  const market = useQuery({
    ...marketQueries.quotes(params, status.data?.collection[asset].snapshot_id),
    refetchInterval: collecting ? 5000 : (config.data?.refresh_interval_seconds ?? 300) * 1000,
  });
  const refresh = useMutation({
    mutationFn: marketApi.refresh,
    onSuccess: () => invalidateMarketStatus(queryClient),
  });
  const analyze = useMutation({
    mutationFn: ({
      symbol,
      snapshotId,
      mode,
      model,
    }: {
      symbol: string;
      snapshotId: string;
      mode: AnalysisMode;
      model?: string;
    }) => jobsApi.createJob(symbol, snapshotId, mode, model),
    onSuccess: (job) => {
      void invalidateJobs(queryClient);
      void navigate(`/jobs/${job.id}`);
    },
  });
  const modelChoice =
    selection ||
    (config.data?.api_configured
      ? `api:${config.data.default_model || config.data.api_models[0]}`
      : 'rules');
  const modelOptions = [
    { value: 'rules', label: '规则分析（无需模型）' },
    ...(config.data?.api_configured
      ? config.data.api_models.map((name) => ({ value: `api:${name}`, label: `API · ${name}` }))
      : []),
    {
      value: `ollama:${config.data?.ollama_model ?? ''}`,
      label: `Ollama · ${config.data?.ollama_model ?? '未配置'}`,
    },
  ];
  const startAnalysis = (quote: Quote) => {
    if (!market.data) return;
    const separator = modelChoice.indexOf(':');
    const mode = separator < 0 ? 'rules' : (modelChoice.slice(0, separator) as AnalysisMode);
    analyze.mutate({
      symbol: quote.symbol,
      snapshotId: market.data.snapshot_id,
      mode,
      model: separator < 0 ? undefined : modelChoice.slice(separator + 1),
    });
  };
  const onChange: TableProps<Quote>['onChange'] = (pagination, _, sorter, extra) => {
    if (extra.action === 'paginate') setPage(pagination.current ?? 1);
    if (extra.action === 'sort' && !Array.isArray(sorter)) {
      setSort({
        field: String(sorter.field ?? 'change_pct'),
        descending: sorter.order !== 'ascend',
      });
      setPage(1);
    }
  };
  const demo = config.data?.market_provider === 'demo';
  const collection = status.data?.collection[asset];
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>MARKET WORKBENCH</div>
          <h1>行情工作台</h1>
          <p>
            A 股、场内 ETF 与指数 · 每五分钟尝试更新 ·{' '}
            {status.data?.session.label ?? '正在读取状态'}
          </p>
        </div>
        <Button
          icon={<ReloadOutlined />}
          loading={refresh.isPending}
          disabled={collecting}
          onClick={() => refresh.mutate()}
        >
          请求刷新
        </Button>
      </div>
      <Alert
        type="warning"
        showIcon
        title={demo ? '演示数据模式' : '免费公开行情 · 延迟与稳定性不保证'}
        description={
          demo
            ? '当前为虚构样本，不能用于真实交易判断。模型分析可单独选择 API 或 Ollama。'
            : '批量采集可能耗时数十秒至数分钟，快照不同时刻生成。接口可能限流、中断或缺页；源时间未知时无法确认数据延迟。不提供逐笔盘口。'
        }
      />
      {status.data && !status.data.worker_online && (
        <Alert
          type="warning"
          showIcon
          title="后台 worker 未在线，采集和研究任务暂时不会执行。请使用启动脚本启动完整服务。"
        />
      )}
      {collection?.status === 'failed' && (
        <Alert
          type="error"
          showIcon
          title={collection.message}
          description="如有历史快照，将继续显示原采集时间；不会回退为演示行情。"
        />
      )}
      {refresh.isSuccess && <Alert type="info" title={refresh.data.message} />}
      {market.error && <ErrorNotice error={market.error} retry={() => void market.refetch()} />}
      {refresh.error && <ErrorNotice error={refresh.error} />}
      {analyze.error && <ErrorNotice error={analyze.error} />}
      {market.data?.stale && (
        <Alert
          type="warning"
          title="当前展示的是超过两个采集周期的旧快照；休市时也保留真实采集时间。"
        />
      )}
      <section className={layout.stats} aria-label="数据覆盖状态">
        <article>
          <span>来源返回数量</span>
          <strong>
            {market.data?.universe_count ?? '—'}
            <small> 只</small>
          </strong>
          <p>{assetNames[asset]} · 非交易所全量核验</p>
        </article>
        <article>
          <span>有源时间的记录</span>
          <strong>{market.data?.source_time_known_count ?? '—'}</strong>
          <p>其余记录延迟未知</p>
        </article>
        <article>
          <span>较上批缺失</span>
          <strong>{market.data?.missing_from_previous.length ?? '—'}</strong>
          <p>不等于退市或停牌</p>
        </article>
        <article>
          <span>本批异常记录</span>
          <strong>{market.data?.rejected_count ?? '—'}</strong>
          <p>格式校验未通过</p>
        </article>
      </section>
      <section className={layout.panel}>
        <div className={layout.panelHeading}>
          <h2>行情观察池</h2>
          <Tag color={collecting ? 'processing' : 'blue'}>
            {collecting ? '采集中' : (market.data?.source ?? '等待数据')}
          </Tag>
        </div>
        <div className={`${layout.toolbar} ${styles.filters}`}>
          <Select
            aria-label="证券类别"
            value={asset}
            className={styles.assetSelect}
            options={Object.entries(assetNames).map(([value, label]) => ({ value, label }))}
            onChange={(value) => {
              setAsset(value);
              setPage(1);
            }}
          />
          <Input
            prefix={<SearchOutlined />}
            aria-label="搜索样本"
            placeholder="输入代码或名称"
            value={search}
            allowClear
            className={layout.search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
          <Select
            aria-label="分析模型"
            value={modelChoice}
            options={modelOptions}
            className={styles.modelSelect}
            onChange={setSelection}
          />
          <Link to="/settings/models">配置 API / 管理模型</Link>
        </div>
        <QuoteTable
          quotes={market.data?.quotes ?? []}
          total={market.data?.total ?? 0}
          page={page}
          search={search}
          sort={sort}
          loading={market.isFetching}
          pending={analyze.isPending}
          pendingSymbol={analyze.variables?.symbol}
          onAnalyze={startAnalysis}
          onChange={onChange}
        />
        <div className={layout.dataStamp}>
          <span>本批最新源时间：{formatTime(market.data?.as_of ?? null)}</span>
          <span>采集完成：{market.data ? formatTime(market.data.fetched_at) : '尚未完成'}</span>
          <span>同批记录可能存在不同延迟</span>
        </div>
      </section>
      {market.data && (
        <section className={`${layout.panel} ${layout.scopePanel}`}>
          <h2>数据质量与分析边界</h2>
          <ul>
            {market.data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          {market.data.missing_from_previous.length > 0 && (
            <details>
              <summary>查看较上批缺失代码</summary>
              <p className={styles.missingSymbols}>
                {market.data.missing_from_previous.join('、')}
              </p>
            </details>
          )}
          <p>股票缺少评分因子时不生成总分；ETF 和指数不套用股票热度评分。</p>
          <p>
            {config.data?.api_configured
              ? 'API 模型已配置，调用费用由你的模型服务决定。'
              : 'API 模型尚未配置；点击“配置 API / 管理模型”填写你的服务地址和密钥。'}
          </p>
          <Link to="/jobs">查看研究任务 →</Link>
        </section>
      )}
    </div>
  );
}
