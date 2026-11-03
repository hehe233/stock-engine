import type { CSSProperties } from 'react';

// Static paths from a2a-frontend's IconParkFont sprite. No remote JavaScript is executed.
type IconName =
  | 'icon-agent-linear'
  | 'icon-danxuan'
  | 'icon-xiajiantou_line'
  | 'icon-cebianchoutizhankaishouqi'
  | 'icon-fuwenben_fasongwenjian';

export function IconParkFont({
  type,
  className = '',
  style,
}: {
  type: IconName;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <span className={`anticon ${className}`} aria-hidden="true" style={style}>
      <svg
        width="1em"
        height="1em"
        fill="currentColor"
        focusable="false"
        style={{ display: 'inline-block', verticalAlign: '-0.125em' }}
      >
        <use href={`/icons/agent.svg#${type}`} />
      </svg>
    </span>
  );
}
