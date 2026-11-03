import { reportQueries } from '../../features/reports/queries';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Table, Tag } from 'antd';
import type { TableColumnsType } from 'antd';
import { Link } from 'react-router-dom';

import type { AnalysisReport } from '../../api/types';
import { ErrorNotice } from '../../components/ErrorNotice';
import { formatTime } from '../../lib/format';
import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

export function ReportsPage() {
  const [page, setPage] = useState(1);
  const history = useQuery(reportQueries.list(page));
  const columns: TableColumnsType<AnalysisReport> = [
    {
      title: '研究对象',
      dataIndex: 'name',
      render: (name: string, report) => (
        <div className={layout.stockName}>
          <strong>{name}</strong>
          <span>{report.symbol}</span>
        </div>
      ),
    },
    {
      title: '规则热度分',
      dataIndex: 'heat_score',
      render: (score: number | null) => (
        <strong className={layout.scoreText}>
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
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>RESEARCH ARCHIVE</div>
          <h1>分析记录</h1>
          <p>每份报告保留生成时的数据依据，刷新行情不会改写历史结论。</p>
        </div>
        <Link to="/">返回行情工作台 →</Link>
      </div>
      {history.error && <ErrorNotice error={history.error} retry={() => void history.refetch()} />}
      <section className={layout.panel}>
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
              <div className={layout.empty}>
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
