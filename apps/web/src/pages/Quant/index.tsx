import { QuantWorkspace } from '../../features/quant/QuantWorkspace';
import layout from '../../styles/Workbench.module.css';
import styles from './index.less';

export function QuantPage() {
  return (
    <div className={`${layout.pageStack} ${styles.root}`}>
      <div className={layout.pageHeading}>
        <div>
          <div className={layout.eyebrow}>QUANT RESEARCH LAB</div>
          <h1>策略与概率实验</h1>
          <p>未来 5 日涨幅 ≥20% · LightGBM · 滚动样本外验证 · T+1 成交模拟</p>
        </div>
      </div>
      <QuantWorkspace />
    </div>
  );
}
