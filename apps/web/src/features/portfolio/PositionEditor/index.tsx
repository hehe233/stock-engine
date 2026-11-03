import { invalidatePortfolio } from '../queries';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Form, Input, InputNumber, Select } from 'antd';

import { portfolioApi } from '../../../api/portfolio';
import { shanghaiToday } from '../../../api/research';
import type { Position, PositionInput } from '../../../api/portfolio';

import { ErrorNotice } from '../../../components/ErrorNotice';

import layout from '../../../styles/Workbench.module.css';
import styles from './index.less';

import { useEffect } from 'react';
const emptyLot = (): PositionInput => ({
  symbol: '',
  name: '',
  asset_type: 'stock',
  quantity: 100,
  cost_price: '',
  acquired_on: shanghaiToday(),
  settlement: 'T1',
  note: '',
});
export function PositionEditor({
  editing,
  isDemo,
  onDone,
}: {
  editing: Position | null;
  isDemo?: boolean;
  onDone: () => void;
}) {
  const [form] = Form.useForm<PositionInput>();
  const client = useQueryClient();
  useEffect(() => {
    if (editing) form.setFieldsValue(editing);
    else form.resetFields();
  }, [editing, form]);
  const save = useMutation({
    mutationFn: async (row: PositionInput) => {
      if (editing) await portfolioApi.update(editing.id, row);
      else await portfolioApi.import([row]);
    },
    onSuccess: () => {
      onDone();
      form.resetFields();
      void invalidatePortfolio(client);
    },
  });
  return (
    <section className={`${layout.panel} ${layout.scopePanel}`}>
      {save.error && <ErrorNotice error={save.error} />}
      <h2>{editing ? '编辑持仓' : '添加持仓'}</h2>
      <Form<PositionInput>
        form={form}
        layout="vertical"
        initialValues={emptyLot()}
        onFinish={(v) => save.mutate(v)}
        className={styles.form}
      >
        <Form.Item label="证券代码" name="symbol" rules={[{ required: true }]}>
          <Input placeholder={isDemo ? 'DEMO001' : '600000.SH'} />
        </Form.Item>
        <Form.Item label="证券名称" name="name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="证券类型" name="asset_type">
          <Select
            options={[
              { value: 'stock', label: 'A 股' },
              { value: 'etf', label: 'ETF' },
            ]}
            onChange={(value) =>
              form.setFieldValue('settlement', value === 'stock' ? 'T1' : 'unknown')
            }
          />
        </Form.Item>
        <Form.Item label="剩余数量" name="quantity" rules={[{ required: true }]}>
          <InputNumber min={1} max={1000000000} precision={0} />
        </Form.Item>
        <Form.Item label="每份成本" name="cost_price" rules={[{ required: true }]}>
          <InputNumber stringMode min="0.0001" precision={4} />
        </Form.Item>
        <Form.Item label="买入日期" name="acquired_on" rules={[{ required: true }]}>
          <Input type="date" max={shanghaiToday()} />
        </Form.Item>
        <Form.Item label="确认交易制度" name="settlement">
          <Select
            options={[
              { value: 'T1', label: 'T+1' },
              { value: 'T0', label: 'T+0（仅适用已核验 ETF）' },
              { value: 'unknown', label: 'ETF 制度未知' },
            ]}
          />
        </Form.Item>
        <Form.Item label="备注" name="note">
          <Input maxLength={300} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          保存持仓
        </Button>
        {editing && (
          <Button
            onClick={() => {
              onDone();
              form.resetFields();
            }}
          >
            取消编辑
          </Button>
        )}
      </Form>
      {save.isSuccess && (
        <Alert
          type="success"
          title="持仓已保存；完全相同的重复行会跳过。"
          className={styles.notice}
        />
      )}
    </section>
  );
}
