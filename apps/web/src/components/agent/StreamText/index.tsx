import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import styles from './index.less';

export function StreamText({ text, animate = false }: { text: string; animate?: boolean }) {
  const [visible, setVisible] = useState(animate ? '' : text);
  const shown = useRef(animate ? '' : text);
  useEffect(() => {
    if (!animate) return;
    let timer: number;
    const tick = () => {
      const current = shown.current;
      const chars = Array.from(text.slice(current.length));
      const next = text.startsWith(current)
        ? current + chars.slice(0, Math.max(1, Math.ceil(chars.length / 45))).join('')
        : text;
      shown.current = next;
      setVisible(next);
      if (next !== text) timer = window.setTimeout(tick, 20);
    };
    timer = window.setTimeout(tick, 20);
    return () => window.clearTimeout(timer);
  }, [animate, text]);
  const value = animate ? visible : text;
  return (
    <div className={styles.markdown} data-streaming={animate && value !== text}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" />,
          // Model output cannot load tracking images or arbitrary remote resources.
          img: ({ alt }) => <span>{alt}</span>,
        }}
      >
        {value}
      </ReactMarkdown>
    </div>
  );
}
