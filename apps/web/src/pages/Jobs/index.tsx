import { jobQueries } from '../../features/jobs/queries';

import { useQuery } from '@tanstack/react-query';
import { Table, Tag } from 'antd';
import type { TableColumnsType } from 'antd';
import { Link } from 'react-router-dom';

import type { ResearchJob } from '../../api/types';

import { ErrorNotice } from '../../components/ErrorNotice';
import { formatTime } from '../../lib/format';
import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

import { jobStatusLabels as labels } from '../../features/jobs/status';
export function JobsPage() {
  const jobs = useQuery({ ...jobQueries.list(), refetchInterval: 5000 });
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
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <h1>研究任务</h1>
          <p>查看执行进度、恢复失败任务，完成后打开研究报告。</p>
        </div>
      </div>
      {jobs.error && <ErrorNotice error={jobs.error} retry={() => void jobs.refetch()} />}
      <section className={layout.panel}>
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
      <p className={layout.muted}>显示最近 30 个任务；完整报告保存在分析记录中。</p>
    </div>
  );
}
