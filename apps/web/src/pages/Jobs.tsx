import { useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Table, Tag } from 'antd';
import type { TableColumnsType } from 'antd';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { ResearchJob } from '../api/types';
import { AgentStream } from '../components/agent/AgentStream';
import { ReportWorkspace } from '../components/agent/ReportWorkspace';
import { useJobStream } from '../components/agent/useJobStream';
import { projectEvents } from '../components/agent/stream';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatTime } from '../lib/format';
import styles from '../styles/Workbench.module.css';

const labels = {
  queued: '排队中',
  running: '执行中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export function JobsPage() {
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.jobs, refetchInterval: 5000 });
  const columns: TableColumnsType<ResearchJob> = [
    { title: '证券', dataIndex: 'symbol' },
    { title: '模式 / 模型', key: 'model', render: (_, job) => job.model_name ?? '规则分析' },
    { title: '状态', key: 'status', render: (_, job) => <Tag>{labels[job.status]}</Tag> },
    { title: '提交时间', dataIndex: 'created_at', render: formatTime },
    {
      title: '详情',
      key: 'action',
      render: (_, job) => <Link to={`/jobs/${job.id}`}>查看任务</Link>,
    },
  ];
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <h1>研究任务</h1>
          <p>查看执行进度、恢复失败任务，完成后打开研究报告。</p>
        </div>
      </div>
      {jobs.error && <ErrorNotice error={jobs.error} retry={() => void jobs.refetch()} />}
      <section className={styles.panel}>
        <Table
          rowKey="id"
          columns={columns}
          dataSource={jobs.data?.items ?? []}
          loading={jobs.isPending}
          scroll={{ x: 700 }}
          pagination={false}
          locale={{ emptyText: '暂无任务，请从行情工作台选择研究对象' }}
        />
      </section>
      <p className={styles.muted}>显示最近 30 个任务；完整报告保存在分析记录中。</p>
    </div>
  );
}

export function JobPage() {
  const { id = '' } = useParams();
  return <JobDetail key={id} id={id} />;
}

function JobDetail({ id }: { id: string }) {
  const client = useQueryClient();
  const job = useQuery({
    queryKey: ['job', id],
    queryFn: () => api.job(id),
    refetchInterval: (query) =>
      ['succeeded', 'failed', 'cancelled'].includes(query.state.data?.status ?? '') ? false : 3000,
  });
  const retry = useMutation({
    mutationFn: () => api.retryJob(id),
    onSuccess: (data) => client.setQueryData(['job', id], data),
  });
  const cancel = useMutation({
    mutationFn: () => api.cancelJob(id),
    onSuccess: (data) => client.setQueryData(['job', id], data),
  });
  const { events, connection } = useJobStream(id, job.data?.attempts);
  const { preview } = useMemo(() => projectEvents(events), [events]);
  const reportId = job.data?.report_id;
  const report = useQuery({
    queryKey: ['analysis', reportId],
    queryFn: () => api.analysis(reportId!),
    enabled: Boolean(reportId),
  });
  if (job.error) return <ErrorNotice error={job.error} retry={() => void job.refetch()} />;
  if (!job.data) return <p role="status">正在读取任务…</p>;
  const current = job.data;
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
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
