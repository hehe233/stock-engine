import { useEffect, useMemo, useRef, useState } from 'react';
import {
  LoadingOutlined,
  BulbOutlined,
  ToolOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { JobEvent, ResearchJob } from '../../../api/types';
import { formatTime } from '../../../lib/format';
import { projectEvents, type StreamBlock } from '../stream';
import { StreamText } from '../StreamText';
import { IconParkFont } from '../IconParkFont';
import styles from './index.less';
import chrome from '../panel.module.css';

const toolNames: Record<string, string> = {
  read_quote: '读取行情快照',
  read_factors: '读取规则因子',
  read_risks: '检查风险边界',
  read_research: '检索研究证据',
  read_portfolio: '读取持仓条件',
};

function Block({
  block,
  active,
  mountedAt,
}: {
  block: StreamBlock;
  active: boolean;
  mountedAt: number;
}) {
  const animate =
    Date.parse(block.time) >= mountedAt &&
    !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const running = !block.done && !block.interrupted && active;
  const mark =
    block.error || block.interrupted || (!block.done && !active) ? (
      <CloseCircleOutlined />
    ) : running ? (
      <LoadingOutlined spin />
    ) : (
      <IconParkFont type="icon-danxuan" />
    );
  if (block.kind === 'step')
    return (
      <div className={styles.step} data-error={block.error}>
        {mark}
        <div>
          <strong>{block.title}</strong>
          {block.content && <p>{block.content}</p>}
        </div>
      </div>
    );
  if (block.kind === 'tool')
    return (
      <details className={styles.tool} open>
        <summary>
          {mark}
          <ToolOutlined />
          <strong>{toolNames[block.title] ?? block.title}</strong>
          <small>
            {running ? '调用中' : block.error ? '失败' : !block.done ? '已中断' : '已完成'}
          </small>
          <IconParkFont type="icon-xiajiantou_line" />
        </summary>
        <div className={styles.toolBody}>
          <code>{block.title}</code>
          <details>
            <summary>调用参数</summary>
            <pre>{JSON.stringify(block.arguments ?? {}, null, 2)}</pre>
          </details>
          {block.result !== undefined && (
            <details>
              <summary>查看完整工具结果</summary>
              <pre>{JSON.stringify(block.result, null, 2)}</pre>
            </details>
          )}
          {block.error && <p>{block.content}</p>}
        </div>
      </details>
    );
  return (
    <div className={styles.modelBlock}>
      <details className={styles.reasoning} open>
        <summary>
          <BulbOutlined />
          <span className={running ? styles.shimmer : ''}>
            {running ? '正在思考' : 'Agent 思考'}
          </span>
          <small>{block.done ? '已结束' : running ? '' : '已中断'}</small>
          <IconParkFont type="icon-xiajiantou_line" />
        </summary>
        <div className={styles.reasoningBody}>
          {block.reasoning ? (
            <StreamText text={block.reasoning} animate={animate} />
          ) : (
            <p className={styles.muted}>
              {running ? '等待模型返回思考内容…' : '本次模型未返回可展示的思考内容。'}
            </p>
          )}
        </div>
      </details>
      {block.content && (
        <div className={styles.content}>
          <StreamText text={block.content} animate={animate} />
        </div>
      )}
    </div>
  );
}

export function AgentStream({
  events,
  job,
  connection,
}: {
  events: JobEvent[];
  job: ResearchJob;
  connection: string;
}) {
  const { blocks } = useMemo(() => projectEvents(events), [events]);
  const [mountedAt] = useState(() => Date.now() - 1000);
  const [following, setFollowing] = useState(true);
  const [now, setNow] = useState(Date.now);
  const viewport = useRef<HTMLDivElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const active = ['queued', 'running'].includes(job.status);
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  useEffect(() => {
    if (!content.current) return;
    const observer = new ResizeObserver(() => {
      if (following && viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight;
    });
    observer.observe(content.current);
    return () => observer.disconnect();
  }, [following]);
  const elapsed = Math.max(
    0,
    Math.floor(((active ? now : Date.parse(job.updated_at)) - Date.parse(job.created_at)) / 1000),
  );
  return (
    <section className={styles.streamPanel} aria-label="Agent 分析过程">
      <header className={chrome.panelHeader}>
        <div className={styles.agentAvatar}>
          <IconParkFont type="icon-agent-linear" />
        </div>
        <div>
          <h2>研究 Agent</h2>
          <p>{job.model_name ?? '规则分析引擎'}</p>
        </div>
        <span className={styles.connection} data-live={connection === 'live'}>
          {connection === 'reconnecting'
            ? '正在重连'
            : connection === 'done'
              ? '记录已同步'
              : connection === 'live'
                ? '实时连接'
                : '连接中'}
        </span>
      </header>
      <div className={styles.runMeta}>
        <span>
          {active ? (
            <LoadingOutlined spin />
          ) : job.status === 'succeeded' ? (
            <IconParkFont type="icon-danxuan" />
          ) : (
            <CloseCircleOutlined />
          )}{' '}
          {active ? '处理中' : job.status === 'succeeded' ? '已完成' : '已停止'}
        </span>
        <span>
          {elapsed} 秒 · 第 {job.attempts} 次执行
        </span>
      </div>
      <div
        className={styles.streamViewport}
        ref={viewport}
        tabIndex={0}
        aria-label="分析过程内容"
        onScroll={() => {
          const el = viewport.current;
          if (el) setFollowing(el.scrollHeight - el.scrollTop - el.clientHeight < 50);
        }}
      >
        <div ref={content} className={styles.chain}>
          {blocks.map((block) => (
            <Block key={block.id} block={block} active={active} mountedAt={mountedAt} />
          ))}
          {!blocks.length && (
            <p className={styles.muted}>
              {connection === 'done' ? '该任务没有保存过程事件。' : '正在读取分析过程…'}
            </p>
          )}
          {job.mode === 'rules' && (
            <p className={styles.muted}>规则模式展示计算步骤与结果，无模型思考或模型工具调用。</p>
          )}
          {active && (
            <div className={styles.waiting}>
              <LoadingOutlined spin />
              <span className={styles.shimmer}>
                {job.status === 'queued' ? '等待研究任务开始' : 'Agent 正在继续分析'}
              </span>
            </div>
          )}
        </div>
      </div>
      <footer className={styles.streamFooter}>
        <span>{formatTime(job.created_at)}</span>
        <button
          type="button"
          onClick={() => {
            setFollowing(true);
            if (viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight;
          }}
        >
          {following ? '正在跟随最新内容' : '回到最新内容 ↓'}
        </button>
      </footer>
    </section>
  );
}
