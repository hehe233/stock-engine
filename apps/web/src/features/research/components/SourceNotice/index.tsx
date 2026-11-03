import { Alert, Tag } from 'antd';
import type { ResearchSnapshot } from '../../../../api/research';
import { formatTime } from '../../../../lib/format';

import styles from './index.less';

export function SourceNotice({ snapshot }: { snapshot: ResearchSnapshot }) {
  return (
    <div className={styles.inset}>
      <Tag color={snapshot.is_demo ? 'orange' : 'blue'}>
        {snapshot.is_demo ? '虚构演示数据' : snapshot.source}
      </Tag>
      <span>
        请求日期 {snapshot.query_date} · 源日期 {snapshot.data_date ?? '未提供'} · 采集{' '}
        {formatTime(snapshot.observed_at)}
      </span>
      <p>
        来源返回 {snapshot.total} 条 · 异常拒绝 {snapshot.details.rejected_count} 条 ·
        完整覆盖未核验 · 精确披露时间未知
      </p>
      {snapshot.details.warnings.map((w) => (
        <p key={w}>{w}</p>
      ))}
      {snapshot.stale && (
        <Alert type="warning" title="这是超过两个采集周期的历史快照，请核对日期后使用。" />
      )}
    </div>
  );
}
