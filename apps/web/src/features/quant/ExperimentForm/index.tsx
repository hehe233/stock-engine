import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Form, InputNumber } from 'antd';
import { useNavigate } from 'react-router-dom';
import { quantApi } from '../../../api/quant';
import type { ExperimentInput } from '../../../api/quant';
import { ErrorNotice } from '../../../components/ErrorNotice';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

const defaults = {
  train_days: 120,
  calibration_days: 60,
  test_days: 60,
  folds: 3,
  probability_threshold: 0.6,
  initial_cash: 100000,
  max_positions: 3,
  commission_bps: 3,
  slippage_bps: 10,
  participation: 0.01,
};
export function ExperimentForm({ selection }: { selection?: string }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [form] = Form.useForm<ExperimentInput>();
  const create = useMutation({
    mutationFn: quantApi.create,
    onSuccess: (run) => {
      void client.invalidateQueries({ queryKey: ['quant-runs'] });
      void navigate('/quant/' + run.id);
    },
  });
  return (
    <section className={`${layout.panel} ${layout.scopePanel}`}>
      <h2>2. 固定参数并创建实验</h2>
      {create.error && <ErrorNotice error={create.error} />}
      <p>
        每折按日期分为训练、校准、测试。训练和校准末尾的跨区间标签被剔除；下一折向前移动一个测试窗口。样本不足或任一类别过少会拒绝训练。
      </p>
      <Form<ExperimentInput>
        form={form}
        layout="vertical"
        initialValues={defaults}
        className={styles.form}
        onFinish={(v) => selection && create.mutate({ ...v, dataset_id: selection })}
      >
        {(
          [
            ['train_days', '训练区天数', 60, 1000],
            ['calibration_days', '校准区天数', 20, 250],
            ['test_days', '每折测试天数', 20, 250],
            ['folds', '滚动折数', 1, 6],
            ['probability_threshold', '交易概率阈值', 0.05, 0.95],
            ['initial_cash', '初始资金（元）', 10000, 100000000],
            ['max_positions', '最多同时持仓', 1, 10],
            ['commission_bps', '双边佣金（基点，另有最低 5 元）', 0, 100],
            ['slippage_bps', '单边滑点（基点）', 0, 100],
            ['participation', '整日成交量参与率上限', 0.0001, 0.1],
          ] as const
        ).map(([name, label, min, max]) => (
          <Form.Item key={name} name={name} label={label} rules={[{ required: true }]}>
            <InputNumber
              min={min}
              max={max}
              step={max <= 1 ? 0.01 : 1}
              className={styles.numberInput}
            />
          </Form.Item>
        ))}
        <Button type="primary" htmlType="submit" loading={create.isPending} disabled={!selection}>
          创建滚动实验
        </Button>
      </Form>
    </section>
  );
}
