import { Tag } from 'antd';
import styles from '../styles/Workbench.module.css';

const milestones = [
  {
    phase: 'P0',
    title: '跑通研究闭环',
    status: '已完成',
    color: 'green',
    items: [
      '虚构样本行情、搜索排序、五分钟刷新',
      'LangGraph 四节点工作流与透明规则评分',
      '行情快照、分析记录、数据库迁移',
      '接口测试、页面测试、启动与学习文档',
    ],
  },
  {
    phase: 'P1',
    title: '接入真实数据与模型',
    status: '已完成',
    color: 'green',
    items: [
      '免费公开 A 股、ETF、指数行情与来源状态',
      '可配置模型 API、Ollama 备选和受控工具调用',
      '流式执行进度、持久化检查点与失败恢复',
      '单用户访问密钥、限流和独立任务进程',
    ],
  },
  {
    phase: 'P2',
    title: '扩展短线研究能力',
    status: '已完成',
    color: 'green',
    items: [
      '连板梯队、行业聚合与跨批次扩散观察',
      '龙虎榜、资金流向与公告证据',
      '持仓导入、T+1 可卖数量与条件分析',
      '十年观察目录、日线归档与同期失败窗口对照',
    ],
  },
  {
    phase: 'P3',
    title: '验证策略与概率',
    status: '研究验证版',
    color: 'blue',
    items: [
      '滚动样本外回测与可成交性约束',
      'LightGBM 建模与概率校准',
      '模型版本、误差追踪与收益归因',
      'Parquet 数据版本与 DuckDB 查询；历史主表覆盖待核验',
      'Level-2 与实盘交易待授权数据和独立验收，本版不启用',
    ],
  },
];

export function Roadmap() {
  return (
    <div className={styles.pageStack}>
      <div className={styles.pageHeading}>
        <div>
          <div className={styles.eyebrow}>PRODUCT ROADMAP</div>
          <h1>开发路线</h1>
          <p>先让数据与分析可靠流转，再逐步接入真实市场与模型能力。</p>
        </div>
      </div>
      <div className={styles.roadmapGrid}>
        {milestones.map((item) => (
          <section className={styles.panel} key={item.phase}>
            <div className={styles.panelHeading}>
              <h2>
                {item.phase} · {item.title}
              </h2>
              <Tag color={item.color}>{item.status}</Tag>
            </div>
            <ul className={styles.roadmapList}>
              {item.items.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
