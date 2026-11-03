import { useState } from 'react';
import { Alert, Input, Tabs } from 'antd';
import { shanghaiToday } from '../../api/research';
import type { ResearchKind } from '../../api/research';
import { titles } from '../../features/research/titles';
import { ResearchDataset } from '../../features/research/components/ResearchDataset';

import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

export function ResearchPage() {
  const [kind, setKind] = useState<ResearchKind>('ladder');
  const [day, setDay] = useState(shanghaiToday);
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>RESEARCH CENTER</div>
          <h1>短线研究中心</h1>
          <p>连板、行业、龙虎榜、资金和公告 · 独立证据批次 · 五分钟尝试更新</p>
        </div>
      </div>
      <Alert
        type="info"
        showIcon
        title="不同数据有不同披露时间"
        description="龙虎榜为盘后资料；资金排名只有当前观测。涨停池覆盖不完整，不能把未收录解释为未涨停。席位名称不能识别具体游资个人。"
      />
      <div className={layout.toolbar}>
        <label>
          研究日期{' '}
          <Input
            type="date"
            aria-label="研究日期"
            value={day}
            max={shanghaiToday()}
            disabled={kind === 'flow'}
            onChange={(e) => {
              if (e.target.value) setDay(e.target.value);
            }}
          />
        </label>
        {kind === 'flow' && <span>资金流向固定读取当前快照，源交易日期未知。</span>}
      </div>
      <Tabs
        activeKey={kind}
        onChange={(value) => setKind(value as ResearchKind)}
        items={(['ladder', 'dragon', 'flow', 'notices'] as const).map((key) => ({
          key,
          label: titles[key],
        }))}
      />
      <ResearchDataset
        key={kind + day}
        query={{ kind, date: kind === 'flow' ? shanghaiToday() : day }}
      />
    </div>
  );
}
