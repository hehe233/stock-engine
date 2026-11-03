import { reportQueries } from '../../features/reports/queries';
import { jobQueries, jobUpdated } from '../../features/jobs/queries';
import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Tag } from 'antd';

import { Link, useParams } from 'react-router-dom';

import { jobsApi } from '../../api/jobs';

import { AgentStream } from '../../components/agent/AgentStream';
import { ReportWorkspace } from '../../components/agent/ReportWorkspace';
import { useJobStream } from '../../components/agent/useJobStream';
import { projectEvents } from '../../components/agent/stream';
import { ErrorNotice } from '../../components/ErrorNotice';

import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

import { jobStatusLabels as labels } from '../../features/jobs/status';
export function JobPage() {
  const { id = '' } = useParams();
  return <JobDetail key={id} id={id} />;
}

function JobDetail({ id }: { id: string }) {
  const client = useQueryClient();
  const job = useQuery({
    ...jobQueries.detail(id),
    refetchInterval: (query) =>
      ['succeeded', 'failed', 'cancelled'].includes(query.state.data?.status ?? '') ? false : 3000,
  });
  const retry = useMutation({
    mutationFn: () => jobsApi.retryJob(id),
    onSuccess: (data) => jobUpdated(client, data),
  });
  const cancel = useMutation({
    mutationFn: () => jobsApi.cancelJob(id),
    onSuccess: (data) => jobUpdated(client, data),
  });
  const { events, connection } = useJobStream(id, job.data?.attempts);
  const { preview } = useMemo(() => projectEvents(events), [events]);
  const reportId = job.data?.report_id;
  const report = useQuery({ ...reportQueries.detail(reportId), enabled: Boolean(reportId) });
  if (job.error) return <ErrorNotice error={job.error} retry={() => void job.refetch()} />;
  if (!job.data) return <p role="status">正在读取任务…</p>;
  const current = job.data;
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <Link to="/jobs">← 研究任务</Link>
          <h1>{current.symbol} · Agent 研究</h1>
          <p>
            {current.model_name ?? '规则分析'} · 第 {current.attempts} 次执行
          </p>
        </div>
        <Tag>{labels[current.status]}</Tag>
      </div>
      {connection === 'reconnecting' && (
        <Alert type="warning" title="进度连接暂时中断，正在尝试重连；任务状态仍会定时更新。" />
      )}
      {current.error && <Alert type="error" title="任务未完成" description={current.error} />}
      {retry.error && <ErrorNotice error={retry.error} />}
      {cancel.error && <ErrorNotice error={cancel.error} />}
      {report.error && <ErrorNotice error={report.error} retry={() => void report.refetch()} />}
      <ReportWorkspace preview={preview} report={report.data} job={current}>
        <AgentStream events={events} job={current} connection={connection} />
      </ReportWorkspace>
      {current.status === 'failed' && (
        <div>
          <p>恢复可能再次调用尚未保存检查点的模型请求，按你的 API 服务计费。</p>
          <Button onClick={() => retry.mutate()} loading={retry.isPending}>
            从检查点重试
          </Button>
        </div>
      )}
      {['queued', 'running'].includes(current.status) && (
        <Button
          disabled={current.cancel_requested}
          loading={cancel.isPending}
          onClick={() => cancel.mutate()}
        >
          {current.cancel_requested ? '取消处理中' : '取消任务'}
        </Button>
      )}
    </div>
  );
}
