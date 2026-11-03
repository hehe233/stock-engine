// 个人持仓按元显示，避免用行情资金的「亿元」单位把小额盈亏四舍五入为零。
const yuan = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' });
export const amount = (n: number | null) => (n == null ? '—' : yuan.format(n));
