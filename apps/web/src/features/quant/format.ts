export const pct = (value: number | null | undefined) =>
  value == null ? '未知' : (value * 100).toFixed(2) + '%';
export const decimal = (value: number | null | undefined) =>
  value == null ? '未知' : value.toFixed(4);
export const money = (value: number | null | undefined) =>
  value == null
    ? '未知'
    : new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(value);
export const statusNames = {
  queued: '排队中',
  running: '运行中',
  succeeded: '已完成',
  failed: '失败',
  cancelled: '已取消',
};
