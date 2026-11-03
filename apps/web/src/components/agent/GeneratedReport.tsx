import { FileTextOutlined, LoadingOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { Link } from 'react-router-dom';
import type { AnalysisReport, ReportPreview, ResearchJob } from '../../api/types';
import { StreamText } from './StreamText';
import styles from './AgentStream.module.css';

export function GeneratedReport({
  preview,
  report,
  job,
}: {
  preview: ReportPreview;
  report?: AnalysisReport;
  job: ResearchJob;
}) {
  const data = report ?? preview;
  const active = job.status === 'queued' || job.status === 'running';
  const insight = data.insight;
  const hasContent = data.summary || data.factors || insight;
  return (
    <section className={styles.reportPanel} aria-label="生成式研究报告" aria-busy={active}>
      <header className={styles.panelHeader}>
        <FileTextOutlined className={styles.reportIcon} />
        <div>
          <h2>{report ? `${report.name} · 研究报告` : '研究报告'}</h2>
          <p>{job.symbol} · 随分析逐步生成</p>
        </div>
        <span className={styles.previewBadge}>
          {report ? (
            <>
              <CheckCircleOutlined /> 已保存
            </>
          ) : active ? (
            <>
              <LoadingOutlined spin /> 生成中
            </>
          ) : (
            '未完成'
          )}
        </span>
      </header>
      <div className={styles.reportBody}>
        {!hasContent && (
          <div className={styles.reportEmpty}>
            <FileTextOutlined />
            <h3>正在整理研究材料</h3>
            <p>规则因子、分析结论与引用证据将在这里逐步呈现。</p>
            <div className={styles.skeleton} />
            <div className={styles.skeleton} />
            <div className={styles.skeleton} />
          </div>
        )}
        {hasContent && (
          <>
            <div className={styles.reportTitle}>
              <span>STOCK ENGINE / RESEARCH</span>
              <h3>{report?.name ?? job.symbol}</h3>
              <p>
                {report?.is_demo ? '演示数据' : '证券研究'} · {job.model_name ?? '规则分析'}
              </p>
            </div>
            {data.heat_score !== undefined && (
              <div className={styles.score}>
                <div>
                  <span>规则热度分</span>
                  <strong>
                    {data.heat_score === null ? '不可用' : data.heat_score.toFixed(2)}
                    {data.heat_score !== null && <small> / 100</small>}
                  </strong>
                </div>
                <p>
                  衡量样本活跃程度
                  <br />
                  不代表连板概率
                </p>
              </div>
            )}
            {data.summary && (
              <section className={styles.reportSection}>
                <h3>分析摘要</h3>
                <StreamText text={data.summary} animate={active} />
              </section>
            )}
            {data.factors && (
              <section className={styles.reportSection}>
                <h3>因子贡献</h3>
                <div className={styles.factors}>
                  {data.factors.map((factor) => (
                    <div key={factor.name}>
                      <div>
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
            )}
            {insight && (
              <section className={styles.reportSection}>
                <div className={styles.sectionHeading}>
                  <h3>模型研究解读</h3>
                  {!report && <span>生成草稿 · 待校验</span>}
                </div>
                {typeof insight.summary === 'string' && (
                  <StreamText text={insight.summary} animate={active} />
                )}
                <div className={styles.observations}>
                  {Array.isArray(insight.observations) &&
                    insight.observations.map(
                      (item, index) =>
                        item && (
                          <div key={index}>
                            <span className={styles.observationIndex}>
                              {String(index + 1).padStart(2, '0')}
                            </span>
                            <div>
                              {typeof item.text === 'string' && (
                                <StreamText text={item.text} animate={active} />
                              )}
                              <div className={styles.citations}>
                                {Array.isArray(item.evidence_ids) &&
                                  item.evidence_ids
                                    .filter((id) => typeof id === 'string')
                                    .map((id) => (
                                      <a key={id} href={`#evidence-${id}`}>
                                        {id}
                                      </a>
                                    ))}
                              </div>
                            </div>
                          </div>
                        ),
                    )}
                </div>
              </section>
            )}
            {(data.risks || insight?.limitations) && (
              <section className={`${styles.reportSection} ${styles.risks}`}>
                <h3>风险与数据边界</h3>
                <ul>
                  {[
                    ...(data.risks ?? []),
                    ...(Array.isArray(insight?.limitations) ? insight.limitations : []),
                  ]
                    .filter((item) => typeof item === 'string')
                    .map((risk, index) => (
                      <li key={index}>{risk}</li>
                    ))}
                </ul>
              </section>
            )}
            {report && Object.keys(report.evidence).length > 0 && (
              <section className={styles.reportSection}>
                <h3>引用证据</h3>
                {Object.entries(report.evidence).map(([id, value]) => (
                  <details id={`evidence-${id}`} key={id}>
                    <summary>{id}</summary>
                    <pre>{JSON.stringify(value, null, 2)}</pre>
                  </details>
                ))}
              </section>
            )}
          </>
        )}
      </div>
      {report && (
        <footer className={styles.reportFooter}>
          <span>
            <CheckCircleOutlined /> 报告已保存，可随时回看
          </span>
          <Link to={`/reports/${report.id}`}>打开完整报告 →</Link>
        </footer>
      )}
      {!active && !report && (
        <footer className={styles.reportFooter}>当前内容为未完成草稿，尚未保存为正式报告。</footer>
      )}
    </section>
  );
}
