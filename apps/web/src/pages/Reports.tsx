import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Table, Tag } from 'antd';
import type { TableColumnsType } from 'antd';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { AnalysisReport } from '../api/types';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatTime } from '../lib/format';
import styles from '../styles/Workbench.module.css';

export function ReportsPage() {
  const [page, setPage] = useState(1);
  const history = useQuery({ queryKey: ['analyses', page], queryFn: () => api.analyses(page) });
  const columns: TableColumnsType<AnalysisReport> = [
    {
      title: '研究对象',
      dataIndex: 'name',
      render: (name: string, report) => (
        <div className={styles.stockName}>
          <strong>{name}</strong>
          <span>{report.symbol}</span>
        </div>
      ),
    },
    {
      title: '规则热度分',
      dataIndex: 'heat_score',
      render: (score: number | null) => (
        <strong className={styles.scoreText}>
          {score === null ? '不可用' : `${score.toFixed(2)} / 100`}
        </strong>
      ),
    },
    {
      title: '数据模式',
      key: 'mode',
      render: (_, report) => (
        <Tag color={report.is_demo ? 'orange' : 'blue'}>
          {report.is_demo ? '演示' : '公开行情'} · {report.model_name ?? '规则分析'}
        </Tag>
      ),
    },
    { title: '创建时间（北京时间）', dataIndex: 'created_at', render: formatTime },
    {
      title: '报告',
      key: 'action',
      render: (_, report) => <Link to={`/reports/${report.id}`}>查看报告</Link>,
    },
  ];
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <div className={styles.eyebrow}>RESEARCH ARCHIVE</div>
          <h1>分析记录</h1>
          <p>每份报告保留生成时的数据依据，刷新行情不会改写历史结论。</p>
        </div>
        <Link to="/">返回行情工作台 →</Link>
      </div>
      {history.error && <ErrorNotice error={history.error} retry={() => void history.refetch()} />}
      <section className={styles.panel}>
        <Table<AnalysisReport>
          columns={columns}
          dataSource={history.data?.items ?? []}
          rowKey="id"
          loading={history.isPending}
          scroll={{ x: 800 }}
          pagination={{
            current: page,
            pageSize: 10,
            total: history.data?.total ?? 0,
            onChange: setPage,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 份报告`,
          }}
          locale={{
            emptyText: (
              <div className={styles.empty}>
                <p>还没有分析记录</p>
                <Link to="/">选择一个样本，开始首次分析 →</Link>
              </div>
            ),
          }}
        />
      </section>
    </div>
  );
}

export function ReportPage() {
  const { id = '' } = useParams();
  const reportQuery = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => api.analysis(id),
    enabled: Boolean(id),
  });
  if (reportQuery.error)
    return <ErrorNotice error={reportQuery.error} retry={() => void reportQuery.refetch()} />;
  if (!reportQuery.data) return <p role="status">正在读取分析报告…</p>;
  const report = reportQuery.data;
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <Link to="/reports">← 分析记录</Link>
          <h1>{report.name} · 研究报告</h1>
          <p>
            {report.symbol} <span className={styles.separator}>|</span>{' '}
            {formatTime(report.created_at)}
          </p>
        </div>
        <Tag color={report.is_demo ? 'orange' : 'blue'}>
          {report.is_demo ? '演示数据' : report.source} · {report.model_name ?? '规则分析'}
        </Tag>
      </div>
      <section className={`${styles.panel} ${styles.reportSummary}`}>
        <div className={styles.scoreBlock}>
          <span>规则热度分</span>
          <strong>
            {report.heat_score === null ? '不可用' : report.heat_score.toFixed(2)}
            {report.heat_score !== null && <small> / 100</small>}
          </strong>
          <span>规则版本 {report.score_version}</span>
        </div>
        <div>
          <h2>分析摘要</h2>
          <p>{report.summary}</p>
          <span className={styles.muted}>该分数未做概率校准，不代表连板概率。</span>
        </div>
      </section>
      {report.insight && (
        <section className={`${styles.panel} ${styles.scopePanel}`}>
          <h2>模型解读 · {report.model_name}</h2>
          <p style={{ display: 'block', lineHeight: 1.9 }}>{report.insight.summary}</p>
          <ul>
            {report.insight.observations.map((observation, index) => (
              <li key={index} style={{ marginBottom: 12 }}>
                {observation.text} <small>依据：{observation.evidence_ids.join('、')}</small>
              </li>
            ))}
          </ul>
          <h2>模型说明的局限</h2>
          <ul>
            {report.insight.limitations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p>程序已校验报告结构和证据 ID，模型文字仍可能有误；原始数值以上方规则报告为准。</p>
          {Object.entries(report.evidence).map(([name, value]) => (
            <details key={name}>
              <summary>查看引用证据：{name}</summary>
              <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {JSON.stringify(value, null, 2)}
              </pre>
            </details>
          ))}
        </section>
      )}
      <div className={styles.reportGrid}>
        <section className={styles.panel}>
          <div className={styles.panelHeading}>
            <h2>因子贡献</h2>
            <span>计算过程透明可查</span>
          </div>
          <div className={styles.factorList}>
            {report.factors.map((factor) => (
              <div key={factor.name}>
                <div className={styles.factorLabel}>
                  <strong>{factor.name}</strong>
                  <span>
                    {factor.points === null ? '未提供' : factor.points.toFixed(2)} /{' '}
                    {factor.max_points}
                  </span>
                </div>
                {factor.points !== null && (
                  <progress
                    aria-label={factor.name}
                    value={factor.points}
                    max={factor.max_points}
                  />
                )}
                <p>{factor.explanation}</p>
              </div>
            ))}
          </div>
        </section>
        <section className={styles.panel}>
          <div className={styles.panelHeading}>
            <h2>执行记录</h2>
            <Tag color="green">已完成</Tag>
          </div>
          <ol className={styles.workflow}>
            {report.trace.map((step, index) => (
              <li key={step.node}>
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div>
                  <strong>{step.title}</strong>
                  <p>{step.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </div>
      <section className={`${styles.panel} ${styles.riskPanel}`}>
        <h2>风险与数据边界</h2>
        <ul>
          {report.risks.map((risk) => (
            <li key={risk}>{risk}</li>
          ))}
        </ul>
      </section>
      {Object.keys(report.research_context).length > 0 && (
        <section className={`${styles.panel} ${styles.scopePanel}`}>
          <h2>提交时冻结的研究证据</h2>
          <p>各资料日期和来源不同；缺失不表示没有事件。后续刷新不会改写本报告。</p>
          {Object.entries(report.research_context).map(([name, value]) => (
            <details key={name}>
              <summary>
                {(
                  {
                    ladder: '连板梯队',
                    dragon: '龙虎榜',
                    seats: '龙虎榜席位',
                    quant: '历史量化实验（非当前预测）',
                    flow: '资金流向',
                    notices: '公告证据',
                    history: '历史窗口',
                    portfolio: '持仓条件',
                  } as Record<string, string>
                )[name] ?? name}
              </summary>
              <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {JSON.stringify(value, null, 2)}
              </pre>
            </details>
          ))}
        </section>
      )}
      <section className={`${styles.panel} ${styles.provenance}`}>
        <h2>数据依据</h2>
        <dl>
          <div>
            <dt>行情源时间</dt>
            <dd>{formatTime(report.as_of)}</dd>
          </div>
          <div>
            <dt>行情快照 ID</dt>
            <dd>{report.snapshot_id}</dd>
          </div>
          <div>
            <dt>分析记录 ID</dt>
            <dd>{report.id}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
