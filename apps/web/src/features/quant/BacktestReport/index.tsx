import { Alert, Table } from 'antd';
import type { Backtest } from '../../../api/quant';
import { money } from '../format';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

export function BacktestReport({ value }: { value: Backtest }) {
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
    <section className={`${layout.panel} ${layout.scopePanel}`}>
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
            <figure className={styles.figure}>
              <svg
                role="img"
                aria-label="样本外交易模拟参考资金曲线"
                viewBox="0 0 800 240"
                className={styles.curve}
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
            <pre className={styles.json}>{JSON.stringify(value.rejected, null, 2)}</pre>
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
