import { Button, Table } from 'antd';
import type { TableColumnsType, TableProps } from 'antd';
import type { Quote } from '../../../api/types';
import { formatAmount, formatChange, formatTime } from '../../../lib/format';
import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

const numeric = (value: number | null) => (value === null ? '未提供' : value.toFixed(2));

export function QuoteTable({
  quotes,
  total,
  page,
  search,
  sort,
  loading,
  pending,
  pendingSymbol,
  onAnalyze,
  onChange,
}: {
  quotes: Quote[];
  total: number;
  page: number;
  search: string;
  sort: { field: string; descending: boolean };
  loading: boolean;
  pending: boolean;
  pendingSymbol?: string;
  onAnalyze: (quote: Quote) => void;
  onChange: TableProps<Quote>['onChange'];
}) {
  const baseColumns: TableColumnsType<Quote> = [
    {
      title: '代码 / 名称',
      key: 'symbol',
      width: 185,
      render: (_, quote) => (
        <div className={layout.stockName}>
          <strong>{quote.name}</strong>
          <span>{quote.symbol}</span>
        </div>
      ),
    },
    {
      title: '最新价',
      dataIndex: 'price',
      width: 100,
      align: 'right',
      sorter: true,
      render: numeric,
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_pct',
      width: 110,
      align: 'right',
      sorter: true,
      render: (value: number | null) => (
        <strong
          className={
            value !== null && value > 0
              ? layout.rise
              : value !== null && value < 0
                ? layout.fall
                : undefined
          }
        >
          {formatChange(value)}
        </strong>
      ),
    },
    {
      title: '换手率',
      dataIndex: 'turnover_pct',
      width: 100,
      align: 'right',
      sorter: true,
      render: (value: number | null) => (value === null ? '未提供' : `${numeric(value)}%`),
    },
    {
      title: '量比',
      dataIndex: 'volume_ratio',
      width: 90,
      align: 'right',
      sorter: true,
      render: numeric,
    },
    {
      title: '成交额',
      dataIndex: 'amount_yuan',
      width: 110,
      align: 'right',
      sorter: true,
      render: formatAmount,
    },
    { title: '源时间', dataIndex: 'quote_time', width: 165, render: formatTime },
    {
      title: '研究',
      key: 'action',
      fixed: 'right',
      width: 90,
      render: (_, quote) => (
        <Button
          type="link"
          size="small"
          aria-label={`分析 ${quote.symbol}`}
          disabled={pending || quote.price === null}
          onClick={() => onAnalyze(quote)}
          loading={pending && pendingSymbol === quote.symbol}
        >
          分析
        </Button>
      ),
    },
  ];
  const columns: TableColumnsType<Quote> = baseColumns.map((column) => ({
    ...column,
    sortOrder:
      'dataIndex' in column && column.dataIndex === sort.field
        ? sort.descending
          ? 'descend'
          : 'ascend'
        : null,
  }));
  return (
    <Table<Quote>
      rowKey="symbol"
      className={styles.table}
      columns={columns}
      dataSource={quotes}
      loading={loading}
      size="small"
      scroll={{ x: 1050 }}
      onChange={onChange}
      pagination={{
        current: page,
        pageSize: 50,
        total: total,
        showSizeChanger: false,
      }}
      locale={{
        emptyText: search ? '没有匹配的样本，请调整搜索条件' : '暂无可用行情，请查看采集状态',
      }}
    />
  );
}
