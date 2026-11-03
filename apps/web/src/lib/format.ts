// 金融时间统一用上海时区展示，避免用户操作系统时区改变交易日期。
export function formatTime(value: string | null) {
  if (!value) return '源时间未知';
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value));
}

export function formatAmount(value: number | null) {
  if (value === null) return '未提供';
  return `${(value / 100_000_000).toFixed(2)} 亿`;
}

export function formatChange(value: number | null) {
  if (value === null) return '未提供';
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}
