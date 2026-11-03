import type { DatasetAudit as AuditData } from '../../../api/quant';
import styles from './index.less';

export function DatasetAudit({ audit }: { audit: AuditData }) {
  return (
    <div className={styles.root}>
      <p>
        {audit.rows.toLocaleString()} 行 · {audit.symbol_count} 只证券 · {audit.days} 个数据集交易日
        · {audit.first} 至 {audit.last}
      </p>
      <p>
        成交所需字段完整：{audit.executable_rows.toLocaleString()} 行；缺精确可见时间：
        {audit.missing_available_at.toLocaleString()} 行。
      </p>
      <ul>
        {audit.warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
    </div>
  );
}
